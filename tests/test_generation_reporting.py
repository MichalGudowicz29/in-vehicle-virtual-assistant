import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, LLMResult

from session_callbacks import SessionCallbacks
from session_report import SessionReport


def test_requested_settings_are_saved_without_claiming_effective_server_defaults(tmp_path):
    report = SessionReport()
    settings = dict(num_ctx=None, num_predict=256, reasoning=False, temperature=0, recursion_limit=8)
    callback = SessionCallbacks(report, report.begin_turn(), generation_settings=settings)
    callback.on_chat_model_start({}, [[]], run_id=uuid4())
    settings['num_predict'] = 999
    text_path, json_path = report.save(tmp_path)
    event = json.loads(json_path.read_text())['events'][0]
    assert event['generation_settings'] == {
        'source': 'client_requested', 'effective': 'unknown',
        'values': dict(num_ctx=None, num_predict=256, reasoning=False, temperature=0, recursion_limit=8),
    }
    text = text_path.read_text()
    assert 'client_requested' in text
    assert 'unknown' in text
    assert '"num_ctx": null' in text
    assert '"num_predict": 256' in text
    assert '"reasoning": false' in text


@pytest.mark.parametrize('metadata', [{}, {'done_reason': 'length', 'eval_count': 1901, 'prompt_eval_count': 2195}])
def test_end_preserves_server_metadata_and_missing_reason_is_null(tmp_path, metadata):
    report = SessionReport()
    callback = SessionCallbacks(report, report.begin_turn())
    callback.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(
        content='', response_metadata=metadata,
        usage_metadata={'input_tokens': 2195, 'output_tokens': 1901, 'total_tokens': 4096},
    ))]]), run_id=uuid4())
    text_path, json_path = report.save(tmp_path)
    event = json.loads(json_path.read_text())['events'][0]
    assert event['response_metadata'] == metadata
    assert event['done_reason'] == metadata.get('done_reason')
    assert event['usage']['total_tokens'] == 4096
    assert f"done_reason: {json.dumps(metadata.get('done_reason'))}" in text_path.read_text()
    assert 'response_metadata:' in text_path.read_text()


@pytest.mark.parametrize('partial', [False, True])
def test_error_preserves_available_partial_metadata_without_inventing_reason(partial):
    report = SessionReport()
    callback = SessionCallbacks(report, report.begin_turn())
    kwargs = {}
    if partial:
        kwargs['response'] = LLMResult(generations=[[ChatGenerationChunk(message=AIMessageChunk(
            content='<tool_call>', response_metadata={'model': 'local'},
            usage_metadata={'input_tokens': 10, 'output_tokens': 2, 'total_tokens': 12},
        ))]])
    callback.on_llm_error(ValueError('invalid XML'), run_id=uuid4(), **kwargs)
    event = report.snapshot()['events'][-1]
    assert event['success'] is False
    assert event['error'] == 'invalid XML'
    assert event['done_reason'] is None
    assert event['response_metadata'] == ({'model': 'local'} if partial else {})
    assert event['usage'] == ({'input_tokens': 10, 'output_tokens': 2, 'total_tokens': 12} if partial else None)


def test_old_callback_constructor_still_records_unknown_requested_settings():
    report = SessionReport()
    callback = SessionCallbacks(report, report.begin_turn())
    callback.on_chat_model_start({}, [[]], run_id=uuid4())
    assert report.snapshot()['events'][-1]['generation_settings'] == {
        'source': 'client_requested', 'effective': 'unknown', 'values': {},
    }


def test_error_keeps_partial_generation_info_when_error_generation_has_no_metadata():
    report = SessionReport()
    callback = SessionCallbacks(report, report.begin_turn())
    callback.on_llm_error(ValueError('interrupted'), run_id=uuid4(), response=LLMResult(generations=[
        [ChatGenerationChunk(message=AIMessageChunk(content=''),
                             generation_info={'done_reason': 'length', 'eval_count': 128})],
        [ChatGeneration(message=AIMessage(content=''))],
    ]))
    event = report.snapshot()['events'][-1]
    assert event['response_metadata'] == {'done_reason': 'length', 'eval_count': 128}
    assert event['done_reason'] == 'length'


@pytest.mark.parametrize('content, additional_kwargs, content_chars, reasoning_chars', [
    ('', {}, 0, None),
    ('Gotowe', {'reasoning_content': ''}, 6, 0),
    ('Gotowe', {'reasoning_content': 'private thinking'}, 6, 16),
])
def test_content_lengths_do_not_save_reasoning_text(tmp_path, content, additional_kwargs, content_chars, reasoning_chars):
    report = SessionReport()
    callback = SessionCallbacks(report, report.begin_turn())
    callback.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(
        content=content, additional_kwargs=additional_kwargs,
    ))]]), run_id=uuid4())
    text_path, json_path = report.save(tmp_path)
    event = json.loads(json_path.read_text())['events'][0]
    assert event['content_chars'] == content_chars
    assert event['reasoning_content_chars'] == reasoning_chars
    assert 'content_chars:' in text_path.read_text()
    assert 'przechwycenie nieznane' in text_path.read_text()
    assert 'private thinking' not in json_path.read_text()
    assert 'private thinking' not in text_path.read_text()


def test_error_without_partial_message_has_unknown_content_lengths():
    report = SessionReport()
    callback = SessionCallbacks(report, report.begin_turn())
    callback.on_llm_error(ValueError('invalid XML'), run_id=uuid4())
    event = report.snapshot()['events'][-1]
    assert event['content_chars'] is None
    assert event['reasoning_content_chars'] is None
