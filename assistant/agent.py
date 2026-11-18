"""One voice command = one agent turn: plan → guarded execution → (optional) answer.

1. Planning: the first model request gets only PLAN_PROMPT and no tools; the JSON plan is
   stored by the application (PlanGuard), not trusted to a tool call.
2. Execution: the model calls HMI tools; PlanGuard lets through only the planned effects.
3. Completion: once every planned effect succeeded the turn ends without another LLM
   request (silent success), unless the user also asked a question (ANSWER_PROMPT).
"""

from typing import get_args
from uuid import uuid4

from httpx import ConnectError
from langchain.agents import create_agent  # type: ignore
from langchain.agents.middleware import wrap_model_call
from langchain.agents.middleware.types import InputAgentState
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import merge_configs
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

import config
from session_callbacks import SessionCallbacks

from .plan_guard import ActionName, ExecutionPlan, IncompleteExecutionError, PlanGuard
from .prompts import ANSWER_PROMPT, PLAN_PROMPT, SYSTEM_PROMPT
from .tools import LOOKUP_TOOLS, build_tools

OLLAMA_URL = "http://127.0.0.1:11434"
ACTION_NAMES = set(get_args(ActionName))


class Assistant:
    def __init__(self, car, thread_id: str = "user_session_1"):
        self.car = car
        self.checkpointer = InMemorySaver()   # conversation memory for clarifying questions
        self.thread_config: RunnableConfig = {
            "configurable": {"thread_id": thread_id},
            "max_concurrency": 1,   # tools run one by one, in plan order
            # Compound plans need lookup and execution rounds; the guard prevents repeated effects.
            "recursion_limit": 24,
        }
        self.agent = create_agent(
            model=ChatOllama(model=config.OLLAMA_MODEL, base_url=OLLAMA_URL, temperature=0,
                             **config.LLM_GENERATION, client_kwargs={"trust_env": False}),
            system_prompt=SYSTEM_PROMPT,
            tools=self.build_tools(),
            checkpointer=self.checkpointer,
            middleware=[wrap_model_call(self._model_call, name='finish_completed_plan')],
        )

    def build_tools(self):
        self.guard = PlanGuard()
        return build_tools(self.car, self.guard)

    def _model_call(self, request, handler):
        guard = self.guard
        if guard.finished_silently:
            return AIMessage(content='')
        if guard.blocked_reason is not None:
            raise IncompleteExecutionError(
                f'Przerwano wykonanie po zablokowanej akcji: {guard.blocked_reason}. Powtórz polecenie.')
        planning = guard.actions is None
        if planning:
            request = request.override(system_message=SystemMessage(content=PLAN_PROMPT), tools=[])
        elif guard.plan_done and guard.answer_required:
            request = request.override(
                tools=[tool for tool in request.tools if tool.name in LOOKUP_TOOLS],
                system_message=SystemMessage(content=ANSWER_PROMPT))
        response = handler(request)
        if planning:
            message = response.result[-1]
            # Accept an explicit plan from a tool-capable model as well as JSON.
            if not (len(message.tool_calls) == 1 and message.tool_calls[0]['name'] == 'set_action_plan'):
                response.result = [AIMessage(content='', tool_calls=[{
                    'name': 'set_action_plan', 'args': self._plan_from(message).model_dump(),
                    'id': f'plan-{uuid4()}'}])]
        guard.response_tools = {call['name'] for message in response.result
                                for call in getattr(message, 'tool_calls', [])}
        return response

    @staticmethod
    def _plan_from(message) -> ExecutionPlan:
        """Plan from the planning reply. A small model sometimes skips the JSON and calls
        an action directly ("Zadzwoń do Roberta" -> call_contact) or just chats ("Dziękuję");
        the intent is still clear, so derive the plan instead of rejecting the command."""
        try:
            return ExecutionPlan.model_validate_json(message.text)
        except ValidationError:
            pass
        actions = [call['name'] for call in message.tool_calls if call['name'] in ACTION_NAMES]
        if actions:
            return ExecutionPlan(actions=actions)            # direct action call: its effects run later
        text = message.text.strip()
        if text and not text.startswith('{') and not message.tool_calls:
            return ExecutionPlan(actions=[], answer_required=True)   # small talk / question: just answer
        # Empty reply (e.g. cut off at the token limit) or a malformed plan: no usable intent.
        raise IncompleteExecutionError('Nie udało się ustalić planu polecenia. Powtórz polecenie.')

    def handle_text(self, text: str, *, report=None, turn_id=None) -> str:
        """Run one command; returns text to speak ('' = silent success)."""
        self.guard.reset()
        run_config = self.thread_config
        if report is not None:
            settings = {**config.LLM_GENERATION, 'temperature': 0,
                        'recursion_limit': self.thread_config.get('recursion_limit')}
            run_config = merge_configs(run_config, {"callbacks": [
                SessionCallbacks(report, turn_id, generation_settings=settings)]})
            report.emit("agent_start", turn_id=turn_id)
        input_data: InputAgentState = {"messages": [{"role": "user", "content": text}]}
        try:
            final_text = self._run(input_data, run_config)
            if not final_text.strip() and not self.guard.finished_silently:
                raise IncompleteExecutionError('Model zakończył turę bez wykonania planu i bez komunikatu dla użytkownika.')
        except Exception as error:
            # A failed turn leaves unfinished tool calls in memory; start the next command clean.
            self.thread_config = {**self.thread_config,
                                  "configurable": {"thread_id": f"user_session_{uuid4().hex[:8]}"}}
            message = str(error)
            if isinstance(error, ConnectError):
                message = (f"Nie można połączyć się z Ollamą pod {OLLAMA_URL}. "
                           "Uruchom aplikację Ollama lub polecenie 'ollama serve', "
                           "a następnie ponownie uruchom asystenta.")
            if report is not None:
                report.emit("agent_end", turn_id=turn_id, success=False, error=message)
            if isinstance(error, ConnectError):
                raise ConnectionError(message) from error
            raise
        if report is not None:
            guard = self.guard
            report.emit("agent_end", turn_id=turn_id, success=True, text=final_text,
                        completion_reason='plan_completed' if guard.actions and guard.plan_done else 'model_response',
                        planned_actions=guard.actions, completed_action_count=guard.next_index,
                        answer_required=guard.answer_required)
        return final_text

    def _run(self, input_data, run_config) -> str:
        """Stream the agent and return the last model text that is not a tool call."""
        final_text = ""
        for chunk in self.agent.stream(input_data, config=run_config, stream_mode="updates", version="v2"):
            data = chunk.get("data") if isinstance(chunk, dict) else None
            if not isinstance(data, dict):
                continue
            for update in data.values():
                messages = update.get("messages", []) if isinstance(update, dict) else []
                for message in messages if isinstance(messages, list) else []:
                    if isinstance(message, AIMessage) and not message.tool_calls:
                        final_text = message.text
        return final_text
