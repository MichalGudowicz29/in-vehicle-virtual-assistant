import importlib
import json

from CarSystem.car_system import CarSystem
from assistant import Assistant
from session_report import SessionReport


def test_configurable_model_is_used_by_agent_and_report(monkeypatch, tmp_path):
    import config
    from langchain_ollama import ChatOllama
    monkeypatch.setattr(config, 'OLLAMA_MODEL', 'test-local-model:8b')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    captured = {}
    def create_agent(**kwargs):
        captured.update(kwargs)
        return object()
    monkeypatch.setattr('assistant.create_agent', create_agent)
    assistant = Assistant(CarSystem())
    model = captured['model']
    assert isinstance(model, ChatOllama)
    assert model.model == 'test-local-model:8b'
    assert model.base_url == 'http://127.0.0.1:11434'
    assert model.temperature == 0
    assert captured['checkpointer'] is assistant.checkpointer
    assert 'call_contact' in [tool.name for tool in captured['tools']]
    report = SessionReport()
    txt, data = report.save(tmp_path)
    assert json.loads(data.read_text())['models']['llm'] == model.model
    assert 'LLM: test-local-model:8b' in txt.read_text()
    assert 'gpt-4o-mini' not in txt.read_text()


def test_model_environment_variable_is_read_without_openai_key(monkeypatch):
    import config
    try:
        with monkeypatch.context() as environment:
            environment.setenv('OLLAMA_MODEL', 'another-local:4b')
            importlib.reload(config)
            assert config.OLLAMA_MODEL == 'another-local:4b'
    finally:
        importlib.reload(config)


def test_chatollama_executes_tools_and_reports_server_token_counts(monkeypatch, tmp_path):
    import httpx
    import config
    from langchain_ollama import ChatOllama

    monkeypatch.setattr(config, 'OLLAMA_MODEL', 'test-offline:8b')
    monkeypatch.setattr(config, 'LLM_GENERATION', {'num_ctx': 8192, 'num_predict': 128, 'reasoning': False})
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    requests = []
    def respond(request):
        assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
        body = json.loads(request.content)
        requests.append(body)
        assert body['model'] == 'test-offline:8b'
        assert body['options']['temperature'] == 0
        assert body['options']['num_ctx'] == 8192
        assert body['options']['num_predict'] == 128
        assert body['think'] is False
        assert 'get_track_list' in [tool['function']['name'] for tool in body['tools']]
        if len(requests) == 1:
            message = {'role': 'assistant', 'content': '', 'tool_calls': [
                {'function': {'name': 'get_track_list', 'arguments': {}}},
            ]}
        else:
            assert body['messages'][-1]['role'] == 'tool'
            message = {'role': 'assistant', 'content': 'Dostępne są trzy utwory.'}
        payload = {'model': body['model'], 'message': message, 'done': True,
                   'done_reason': 'stop', 'prompt_eval_count': 10, 'eval_count': 3}
        return httpx.Response(200, text=json.dumps(payload) + '\n')
    def local_model(**kwargs):
        return ChatOllama(**{**kwargs, 'client_kwargs': {
            **kwargs['client_kwargs'], 'transport': httpx.MockTransport(respond),
        }})
    monkeypatch.setattr('assistant.ChatOllama', local_model)
    assistant = Assistant(CarSystem())
    report = SessionReport()
    response = assistant.handle_text('Jakie masz utwory?', report=report, turn_id=report.begin_turn())
    assert response == 'Dostępne są trzy utwory.'
    assert len(requests) == 2
    data = report.snapshot()
    assert data['metrics']['Pojedyncze żądanie LLM']['n'] == 2
    assert data['metrics']['Narzędzie: get_track_list']['n'] == 1
    assert data['tokens'] == {'input_tokens': 20, 'output_tokens': 6, 'total_tokens': 26,
                              'known_requests': 2, 'missing_requests': 0}
    llm_start = next(event for event in data['events'] if event['type'] == 'llm_start')
    assert llm_start['generation_settings']['values']['num_ctx'] == 8192
    assert all(event['done_reason'] == 'stop' for event in data['events'] if event['type'] == 'llm_end')
    event = next(event for event in data['events'] if event['type'] == 'tool_end')
    assert event['success'] is True
    assert event['output'] == requests[1]['messages'][-1]['content']
    txt, json_path = report.save(tmp_path)
    saved_event = next(e for e in json.loads(json_path.read_text())['events'] if e['type'] == 'tool_end')
    assert saved_event['output'] == requests[1]['messages'][-1]['content']
    assert 'Wynik przekazany do LLM:' in txt.read_text()
    for track in json.loads(event['output'])['tracks']:
        assert track['title'] in txt.read_text()


def test_empty_model_name_is_rejected_and_cloud_tracing_is_disabled(monkeypatch):
    import os
    import pytest
    import config
    try:
        with monkeypatch.context() as environment:
            environment.setenv('OLLAMA_MODEL', '   ')
            environment.setenv('LANGSMITH_TRACING', 'true')
            environment.setenv('LANGCHAIN_TRACING_V2', 'true')
            with pytest.raises(ValueError, match='OLLAMA_MODEL'):
                importlib.reload(config)
            assert os.environ['LANGSMITH_TRACING'] == 'false'
            assert os.environ['LANGCHAIN_TRACING_V2'] == 'false'
    finally:
        importlib.reload(config)


def test_missing_ollama_model_is_reported_without_cloud_fallback(monkeypatch):
    import httpx
    import pytest
    from ollama import ResponseError
    from langchain_ollama import ChatOllama
    requests = []
    def not_found(request):
        requests.append(str(request.url))
        return httpx.Response(404, json={'error': 'model not found'})
    def local_model(**kwargs):
        return ChatOllama(**{**kwargs, 'client_kwargs': {
            **kwargs['client_kwargs'], 'transport': httpx.MockTransport(not_found),
        }})
    monkeypatch.setattr('assistant.ChatOllama', local_model)
    assistant = Assistant(CarSystem())
    report = SessionReport()
    with pytest.raises(ResponseError, match='model not found'):
        assistant.handle_text('Włącz muzykę', report=report, turn_id=report.begin_turn())
    assert requests == ['http://127.0.0.1:11434/api/chat']
    assert report.snapshot()['events'][-1]['success'] is False


def test_music_library_authorization_expires_between_real_agent_turns(monkeypatch, qt_call):
    import httpx
    from langchain_ollama import ChatOllama

    responses = iter([
        {'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': 'set_action_plan', 'arguments': {'actions': ['select_track']}}}]},
        {'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': 'get_track_list', 'arguments': {}}}]},
        {'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': 'select_track', 'arguments': {'title': 'Chill song'}}}]},
        {'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': 'select_track', 'arguments': {'title': 'Christmas Eve'}}}]},
        {'role': 'assistant', 'content': 'Nie wybrano utworu.'},
    ])

    def respond(request):
        message = next(responses)
        return httpx.Response(200, text=json.dumps({
            'model': 'test-local-default:2b', 'message': message, 'done': True,
        }) + '\n')

    def local_model(**kwargs):
        return ChatOllama(**{**kwargs, 'client_kwargs': {
            **kwargs['client_kwargs'], 'transport': httpx.MockTransport(respond),
        }})

    monkeypatch.setattr('assistant.ChatOllama', local_model)
    car = CarSystem()
    assistant = Assistant(car)
    report = SessionReport()
    turn = report.begin_turn()
    assert qt_call(lambda: assistant.handle_text('Włącz coś spokojnego', report=report, turn_id=turn)) == ''
    assert car.music.currentTrackIndex == 1
    assert car.music.isPlaying is True
    report.end_turn(turn, 'completed')
    turn = report.begin_turn()
    qt_call(lambda: assistant.handle_text('Włącz Christmas Eve', report=report, turn_id=turn))
    assert car.music.currentTrackIndex == 1
    assert car.music.isPlaying is True
    selected = [event for event in report.snapshot()['events']
                if event['type'] == 'tool_end' and event['name'] == 'select_track']
    assert [event['success'] for event in selected] == [True, False]


def test_music_cannot_be_selected_in_same_model_response_as_library_request(monkeypatch, qt_call):
    import httpx
    from langchain_ollama import ChatOllama

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        message = {'role': 'assistant', 'content': 'Nie wybrano utworu.'}
        if len(requests) == 1:
            message['tool_calls'] = [
                {'function': {'name': 'get_track_list', 'arguments': {}}},
                {'function': {'name': 'select_track', 'arguments': {'title': 'Chill song'}}},
            ]
        return httpx.Response(200, text=json.dumps({
            'model': 'test-local-default:2b', 'message': message, 'done': True,
        }) + '\n')

    def local_model(**kwargs):
        return ChatOllama(**{**kwargs, 'client_kwargs': {
            **kwargs['client_kwargs'], 'transport': httpx.MockTransport(respond),
        }})

    monkeypatch.setattr('assistant.ChatOllama', local_model)
    car = CarSystem()
    assistant = Assistant(car)
    qt_call(lambda: assistant.handle_text('Włącz coś spokojnego'))
    assert car.music.currentTrackIndex == 0
    assert car.music.isPlaying is False
    # The last tool result is the rejected selection, after the library result.
    assert json.loads(requests[1]['messages'][-1]['content'])['success'] is False
