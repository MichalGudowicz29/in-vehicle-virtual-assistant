"""Measure actual model/tool executions, including tools that bypass the HMI graph."""

import json
from copy import deepcopy
from threading import Lock

from langchain_core.callbacks import BaseCallbackHandler


class SessionCallbacks(BaseCallbackHandler):
    run_inline = True

    def __init__(self, report, turn_id, *, generation_settings=None):
        self.report = report
        self.turn_id = turn_id
        self.generation_settings = deepcopy(generation_settings or {})
        self._tools = {}
        self._lock = Lock()

    def _emit(self, event, run_id, **data):
        self.report.emit(event, turn_id=self.turn_id, run_id=str(run_id), **data)

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._emit('llm_start', run_id, generation_settings={
            'source': 'client_requested', 'effective': 'unknown',
            'values': self.generation_settings,
        })

    def on_llm_end(self, response, *, run_id, **kwargs):
        self._emit('llm_end', run_id, success=True, **self._response_data(response))

    @staticmethod
    def _response_data(response):
        usage = None
        tools = []
        response_metadata = {}
        content_chars = None
        reasoning_content_chars = None
        for batch in getattr(response, 'generations', []):
            for generation in batch:
                message = getattr(generation, 'message', None)
                content = getattr(message, 'content', None)
                if isinstance(content, str):
                    content_chars = (content_chars or 0) + len(content)
                reasoning = getattr(message, 'additional_kwargs', {}).get('reasoning_content')
                if isinstance(reasoning, str):
                    reasoning_content_chars = (reasoning_content_chars or 0) + len(reasoning)
                tools.extend(call['name'] for call in getattr(message, 'tool_calls', []))
                metadata = getattr(message, 'usage_metadata', None)
                if metadata is not None:
                    usage = {key: metadata[key] for key in ('input_tokens', 'output_tokens', 'total_tokens')}
                response_metadata.update(getattr(generation, 'generation_info', None) or {})
                response_metadata.update(getattr(message, 'response_metadata', None) or {})
        return dict(tools=tools, usage=usage, response_metadata=response_metadata,
                    done_reason=response_metadata.get('done_reason'),
                    content_chars=content_chars, reasoning_content_chars=reasoning_content_chars)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._emit('llm_end', run_id, success=False, error=str(error),
                   **self._response_data(kwargs.get('response')))

    def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs):
        name = (serialized or {}).get('name', 'unknown')
        with self._lock:
            self._tools[run_id] = name
        self._emit('tool_start', run_id, name=name,
                   arguments=inputs if inputs is not None else input_str)

    def on_tool_end(self, output, *, run_id, **kwargs):
        content = getattr(output, 'content', output)
        result = content
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
        self._emit('tool_end', run_id, name=name, success=success,
                   output=content, tool_call_id=getattr(output, 'tool_call_id', None))

    def on_tool_error(self, error, *, run_id, **kwargs):
        with self._lock:
            name = self._tools.pop(run_id, 'unknown')
        self._emit('tool_end', run_id, name=name, success=False, error=str(error))
