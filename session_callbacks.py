"""Measure actual model/tool executions, including tools that bypass the HMI graph."""

import json
from threading import Lock

from langchain_core.callbacks import BaseCallbackHandler


class SessionCallbacks(BaseCallbackHandler):
    run_inline = True

    def __init__(self, report, turn_id):
        self.report = report
        self.turn_id = turn_id
        self._tools = {}
        self._lock = Lock()

    def _emit(self, event, run_id, **data):
        self.report.emit(event, turn_id=self.turn_id, run_id=str(run_id), **data)

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._emit('llm_start', run_id)

    def on_llm_end(self, response, *, run_id, **kwargs):
        messages = [getattr(generation, 'message', None)
                    for batch in response.generations for generation in batch]
        usage = None
        tools = []
        for message in messages:
            tools.extend(call['name'] for call in getattr(message, 'tool_calls', []))
            metadata = getattr(message, 'usage_metadata', None)
            if metadata is not None:
                usage = {key: metadata[key] for key in ('input_tokens', 'output_tokens', 'total_tokens')}
        self._emit('llm_end', run_id, success=True, tools=tools, usage=usage)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._emit('llm_end', run_id, success=False, error=str(error), usage=None)

    def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs):
        name = (serialized or {}).get('name', 'unknown')
        with self._lock:
            self._tools[run_id] = name
        self._emit('tool_start', run_id, name=name,
                   arguments=inputs if inputs is not None else input_str)

    def on_tool_end(self, output, *, run_id, **kwargs):
        result = getattr(output, 'content', output)
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (ValueError, TypeError):
                result = None
        success = result.get('success') if isinstance(result, dict) else None
        if getattr(output, 'status', None) == 'error':
            success = False
        with self._lock:
            name = self._tools.pop(run_id, 'unknown')
        self._emit('tool_end', run_id, name=name, success=success)

    def on_tool_error(self, error, *, run_id, **kwargs):
        with self._lock:
            name = self._tools.pop(run_id, 'unknown')
        self._emit('tool_end', run_id, name=name, success=False, error=str(error))
