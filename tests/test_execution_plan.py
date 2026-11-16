import json

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from assistant import Assistant
from CarSystem.car_system import CarSystem
from session_report import SessionReport


class ScriptedModel(BaseChatModel):
    responses: list[AIMessage]
    requests: int = 0

    @property
    def _llm_type(self):
        return 'scripted-execution-test'

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests += 1
        assert self.responses, 'Unexpected LLM request after completed action plan'
        message = self.responses.pop(0).model_copy(deep=True, update={'id': None})
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_response(*calls):
    return AIMessage(content='', tool_calls=[
        {'name': name, 'args': arguments, 'id': f'call-{index}-{name}'}
        for index, (name, arguments) in enumerate(calls)
    ])


@pytest.fixture
def execution(monkeypatch):
    def create(*responses):
        model = ScriptedModel(responses=list(responses))
        monkeypatch.setattr('assistant.ChatOllama', lambda **kwargs: model)
        car = CarSystem()
        assistant = Assistant(car)
        report = SessionReport()
        return assistant, car, model, report
    return create


@pytest.mark.parametrize('name, arguments', [
    ('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'}),
    ('navigate_to', {'street': 'Żołnierska', 'city': 'Szczecin', 'number': '47'}),
    ('select_track', {'title': 'Christmas Eve'}),
])
def test_success_finishes_without_another_llm_request(execution, qt_call, name, arguments):
    responses = [tool_response(('set_action_plan', {'actions': [name]}))]
    if name == 'select_track':
        responses.append(tool_response(('get_track_list', {})))
    responses.append(tool_response((name, arguments)))
    assistant, car, model, report = execution(*responses)
    assert qt_call(lambda: assistant.handle_text('Wykonaj polecenie', report=report,
                                                turn_id=report.begin_turn())) == ''
    assert model.requests == len(responses)
    assert report.snapshot()['events'][-1]['completion_reason'] == 'plan_completed'


def test_compound_command_continues_until_every_action_succeeds(execution, qt_call):
    assistant, car, model, report = execution(
        tool_response(('set_action_plan', {'actions': ['navigate_to', 'call_contact']})),
        tool_response(('get_contacts', {})),
        tool_response(('navigate_to', {'street': 'Żołnierska', 'city': 'Szczecin', 'number': '47'})),
        tool_response(('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'})),
    )
    assert qt_call(lambda: assistant.handle_text('Ustaw trasę i zadzwoń', report=report,
                                                turn_id=report.begin_turn())) == ''
    assert model.requests == 4
    assert car.navigation.destination == 'ul. Żołnierska 47, Szczecin'
    assert car.contacts.currentContactName == 'Robert Lewandowski'


def test_duplicate_parallel_call_is_recorded_but_controller_runs_once(execution, qt_call, monkeypatch):
    arguments = {'name': 'Robert Lewandowski', 'number_type': 'mobile'}
    assistant, car, model, report = execution(
        tool_response(('set_action_plan', {'actions': ['call_contact']})),
        tool_response(('call_contact', arguments), ('call_contact', arguments)),
    )
    calls = []
    original = assistant.graph.invoke

    def invoke(state):
        calls.append(state)
        return original(state)

    monkeypatch.setattr(assistant.graph, 'invoke', invoke)
    qt_call(lambda: assistant.handle_text('Zadzwoń', report=report, turn_id=report.begin_turn()))
    assert len(calls) == 1
    ends = [event for event in report.snapshot()['events']
            if event['type'] == 'tool_end' and event['name'] == 'call_contact']
    assert len(ends) == 2
    blocked = [json.loads(event['output']) for event in ends if event['success'] is False]
    assert blocked[0]['reason'] == 'duplicate_action'


def test_unrequested_toggle_after_selection_is_blocked(execution, qt_call):
    assistant, car, model, report = execution(
        tool_response(('set_action_plan', {'actions': ['select_track', 'navigate_to']})),
        tool_response(('get_track_list', {})),
        tool_response(('select_track', {'title': 'Christmas Eve'})),
        tool_response(('play_pause', {})),
        tool_response(('navigate_to', {'street': 'Żołnierska', 'city': 'Szczecin', 'number': '47'})),
    )
    qt_call(lambda: assistant.handle_text('Włącz utwór i ustaw trasę', report=report,
                                        turn_id=report.begin_turn()))
    assert car.music.isPlaying is True
    event = next(event for event in report.snapshot()['events']
                 if event['type'] == 'tool_end' and event['name'] == 'play_pause')
    assert json.loads(event['output'])['reason'] == 'unplanned_action'


def test_failed_action_does_not_complete_plan(execution, qt_call):
    assistant, car, model, report = execution(
        tool_response(('set_action_plan', {'actions': ['call_contact']})),
        tool_response(('call_contact', {'name': 'Nieznany', 'number_type': 'mobile'})),
        AIMessage(content='Nie ma takiego kontaktu.'),
    )
    assert qt_call(lambda: assistant.handle_text('Zadzwoń', report=report,
                                                turn_id=report.begin_turn())) == 'Nie ma takiego kontaktu.'
    assert model.requests == 3


def test_plan_cannot_be_shortened_and_explicit_pause_is_allowed(execution):
    assistant, car, model, report = execution()
    tools = {tool.name: tool for tool in assistant.build_tools()}
    assert tools['set_action_plan'].invoke({'actions': []})['success'] is False
    assert tools['set_action_plan'].invoke({'actions': ['select_track', 'play_pause']})['success'] is True
    assert tools['set_action_plan'].invoke({'actions': ['select_track']})['success'] is False
    tools['get_track_list'].invoke({})
    assert tools['select_track'].invoke({'title': 'Christmas Eve'})['success'] is True
    assert tools['play_pause'].invoke({})['success'] is True
    assert car.music.isPlaying is False


def test_unplanned_side_effect_is_rejected(execution):
    assistant, car, model, report = execution()
    tools = {tool.name: tool for tool in assistant.build_tools()}
    result = tools['call_contact'].invoke({'name': 'Robert Lewandowski', 'number_type': 'mobile'})
    assert result['success'] is False
    assert result['reason'] == 'missing_plan'
    assert car.contacts.currentContactName == ''


def test_empty_response_without_execution_is_an_error(execution, qt_call):
    assistant, car, model, report = execution(AIMessage(
        content='', response_metadata={'done_reason': 'length'},
        usage_metadata={'input_tokens': 2195, 'output_tokens': 1901, 'total_tokens': 4096},
    ))
    with pytest.raises(RuntimeError, match='bez wykonania planu'):
        qt_call(lambda: assistant.handle_text('Ustaw trasę', report=report, turn_id=report.begin_turn()))
    assert report.snapshot()['events'][-1]['success'] is False


def test_plan_and_side_effect_in_same_response_do_not_execute_together(execution, qt_call):
    arguments = {'name': 'Robert Lewandowski', 'number_type': 'mobile'}
    assistant, car, model, report = execution(
        tool_response(('set_action_plan', {'actions': ['call_contact']}), ('call_contact', arguments)),
        tool_response(('call_contact', arguments)),
    )
    qt_call(lambda: assistant.handle_text('Zadzwoń', report=report, turn_id=report.begin_turn()))
    ends = [event for event in report.snapshot()['events']
            if event['type'] == 'tool_end' and event['name'] == 'call_contact']
    assert [event['success'] for event in ends] == [False, True]
    assert model.requests == 2


def test_success_ledger_is_reset_for_next_user_turn(execution, qt_call):
    plan = tool_response(('set_action_plan', {'actions': ['call_contact']}))
    call = tool_response(('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'}))
    assistant, car, model, report = execution(plan, call, plan, call)
    for _ in range(2):
        turn = report.begin_turn()
        qt_call(lambda: assistant.handle_text('Zadzwoń', report=report, turn_id=turn))
        report.end_turn(turn, 'completed')
    assert model.requests == 4
    ends = [event for event in report.snapshot()['events']
            if event['type'] == 'tool_end' and event['name'] == 'call_contact']
    assert [event['success'] for event in ends] == [True, True]


def test_planned_selection_then_pause_preserves_order_in_one_tool_batch(execution, qt_call, monkeypatch):
    from threading import Event

    assistant, car, model, report = execution(
        tool_response(('set_action_plan', {'actions': ['select_track', 'play_pause']})),
        tool_response(('get_track_list', {})),
        tool_response(('select_track', {'title': 'Christmas Eve'}), ('play_pause', {})),
    )
    pause_started = Event()
    original = assistant._execute_graph_action

    def delayed_selection(intent, action, payload):
        if action == 'select_track':
            pause_started.wait(timeout=0.2)
        else:
            pause_started.set()
        return original(intent, action, payload)

    monkeypatch.setattr(assistant, '_execute_graph_action', delayed_selection)
    qt_call(lambda: assistant.handle_text('Wybierz i zapauzuj utwór', report=report,
                                        turn_id=report.begin_turn()))
    assert car.music.isPlaying is False
    assert model.requests == 3
