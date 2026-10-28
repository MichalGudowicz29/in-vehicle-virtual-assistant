from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from assistant import Assistant
from session_report import SessionReport
from session_callbacks import SessionCallbacks


def test_callbacks_pair_runs_capture_usage_and_decode_tool_message():
    report = SessionReport()
    turn = report.begin_turn()
    cb = SessionCallbacks(report, turn)
    a, b, tool = uuid4(), uuid4(), uuid4()
    cb.on_chat_model_start({}, [[]], run_id=a)
    cb.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(content='', tool_calls=[{'name': 'get_contacts', 'args': {}, 'id': 'call1'}], usage_metadata={'input_tokens': 12, 'output_tokens': 3, 'total_tokens': 15}))]]), run_id=a)
    cb.on_tool_start({'name': 'get_contacts'}, '{}', run_id=tool, inputs={})
    cb.on_tool_end(ToolMessage(content='{"success": true, "contacts": []}', tool_call_id='call1'), run_id=tool)
    cb.on_chat_model_start({}, [[]], run_id=b)
    cb.on_llm_error(RuntimeError('offline'), run_id=b)
    data = report.snapshot()
    assert data['tokens']['total_tokens'] == 15
    assert data['tokens']['missing_requests'] == 1
    assert data['metrics']['Pojedyncze żądanie LLM']['n'] == 2
    end = next(e for e in data['events'] if e['type'] == 'tool_end')
    assert end['success'] is True
    assert end['name'] == 'get_contacts'
    assert not any('contacts' in e for e in data['events'])


def test_failed_tool_result_is_not_a_successful_execution():
    report = SessionReport()
    cb = SessionCallbacks(report, report.begin_turn())
    run = uuid4()
    cb.on_tool_start({'name': 'select_track'}, '{}', run_id=run)
    cb.on_tool_end({'success': False}, run_id=run)
    assert report.snapshot()['events'][-1]['success'] is False


def test_agent_logs_final_ai_text_and_does_not_return_tool_json():
    report = SessionReport()
    turn = report.begin_turn()
    class Agent:
        def stream(self, inputs, **kwargs):
            cb = kwargs['config']['callbacks'][0]
            run = uuid4()
            cb.on_chat_model_start({}, [[]], run_id=run)
            cb.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(content='Gotowe'))]]), run_id=run)
            yield {'data': {'tools': {'messages': [ToolMessage(content='{"success": true}', tool_call_id='t')]}}}
            yield {'data': {'model': {'messages': [AIMessage(content='Gotowe')]}}}
    assistant = Assistant.__new__(Assistant)
    assistant.thread_config = {}
    assistant.agent = Agent()
    assert assistant.handle_text('dalej', report=report, turn_id=turn) == 'Gotowe'
    assert report.snapshot()['events'][-1]['text'] == 'Gotowe'
    assert report.snapshot()['events'][-1]['type'] == 'agent_end'


def test_agent_error_has_end_marker_and_is_propagated():
    class Agent:
        def stream(self, *args, **kwargs):
            raise RuntimeError('offline')
    assistant = Assistant.__new__(Assistant)
    assistant.thread_config = {}
    assistant.agent = Agent()
    report = SessionReport()
    with pytest.raises(RuntimeError, match='offline'):
        assistant.handle_text('test', report=report, turn_id=report.begin_turn())
    assert report.snapshot()['events'][-1]['success'] is False


def test_real_langchain_agent_propagates_callbacks_to_model_and_parallel_tools():
    from langchain.agents import create_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.outputs import ChatResult
    from langchain_core.tools import tool

    class LocalModel(BaseChatModel):
        responses: list[AIMessage]
        @property
        def _llm_type(self):
            return 'local-test-model'
        def bind_tools(self, tools, **kwargs):
            return self
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])

    @tool
    def get_contacts() -> dict:
        """Get test contacts without networking."""
        return {'success': True, 'contacts': ['Anna']}

    assistant = Assistant.__new__(Assistant)
    assistant.thread_config = {}
    assistant.agent = create_agent(model=LocalModel(responses=[
        AIMessage(content='', tool_calls=[
            {'name': 'get_contacts', 'args': {}, 'id': 'a'},
            {'name': 'get_contacts', 'args': {}, 'id': 'b'},
        ], usage_metadata={'input_tokens': 10, 'output_tokens': 4, 'total_tokens': 14}),
        AIMessage(content='Mobilny czy służbowy?', usage_metadata={'input_tokens': 20, 'output_tokens': 5, 'total_tokens': 25}),
    ]), tools=[get_contacts])
    report = SessionReport()
    assert assistant.handle_text('Zadzwoń do Anny', report=report, turn_id=report.begin_turn()) == 'Mobilny czy służbowy?'
    data = report.snapshot()
    assert data['metrics']['Pojedyncze żądanie LLM']['n'] == 2
    assert data['metrics']['Narzędzie: get_contacts']['n'] == 2
    assert data['tokens']['total_tokens'] == 39
    assert data['tokens']['known_requests'] == 2
    assert all(e['success'] is True for e in data['events'] if e['type'] == 'tool_end')


@pytest.mark.parametrize('callbacks', [None, 'manager'])
def test_agent_preserves_callback_configuration_supported_by_langchain(callbacks):
    from langchain_core.callbacks import BaseCallbackHandler, CallbackManager
    existing = BaseCallbackHandler()
    if callbacks == 'manager':
        callbacks = CallbackManager([existing])
    class Agent:
        def stream(self, inputs, *, config, **kwargs):
            handlers = config['callbacks']
            if isinstance(handlers, CallbackManager):
                handlers = handlers.handlers
            assert any(isinstance(handler, SessionCallbacks) for handler in handlers)
            if callbacks is not None:
                assert existing in handlers
            yield {'data': {'model': {'messages': [AIMessage(content='Gotowe')]}}}
    assistant = Assistant.__new__(Assistant)
    assistant.thread_config = {'callbacks': callbacks}
    assistant.agent = Agent()
    report = SessionReport()
    assert assistant.handle_text('test', report=report, turn_id=report.begin_turn()) == 'Gotowe'
