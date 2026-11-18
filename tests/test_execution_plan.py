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
        monkeypatch.setattr('assistant.agent.ChatOllama', lambda **kwargs: model)
        car = CarSystem()
        assistant = Assistant(car)
        report = SessionReport()
        return assistant, car, model, report
    return create


@pytest.mark.parametrize('name, arguments', [
    ('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'}),
    ('navigate_to', {'address': 'Żołnierska 47'}),
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
        tool_response(('navigate_to', {'address': 'Żołnierska 47'})),
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
    import assistant.tools as tools

    calls = []
    original = tools.perform

    def perform(car, action, payload):
        calls.append(action)
        return original(car, action, payload)

    monkeypatch.setattr(tools, 'perform', perform)
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
        tool_response(('pause_music', {})),
        tool_response(('navigate_to', {'address': 'Żołnierska 47'})),
    )
    with pytest.raises(RuntimeError, match='unplanned_action'):
        qt_call(lambda: assistant.handle_text('Włącz utwór i ustaw trasę', report=report,
                                            turn_id=report.begin_turn()))
    assert car.music.isPlaying is True
    event = next(event for event in report.snapshot()['events']
                 if event['type'] == 'tool_end' and event['name'] == 'pause_music')
    assert json.loads(event['output'])['reason'] == 'unplanned_action'
    assert model.requests == 4
    assert car.navigation.destination == ''


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
    assert tools['set_action_plan'].invoke({'actions': ['select_track', 'pause_music']})['success'] is True
    assert tools['set_action_plan'].invoke({'actions': ['select_track']})['success'] is False
    tools['get_track_list'].invoke({})
    assert tools['select_track'].invoke({'title': 'Christmas Eve'})['success'] is True
    assert tools['pause_music'].invoke({})['success'] is True
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
    with pytest.raises(RuntimeError, match='ustalić planu'):
        qt_call(lambda: assistant.handle_text('Ustaw trasę', report=report, turn_id=report.begin_turn()))
    assert report.snapshot()['events'][-1]['success'] is False


def test_direct_action_in_plan_response_becomes_plan_and_runs_later(execution, qt_call):
    """Small models often skip the JSON plan ("Zadzwoń do Roberta" -> call_contact)."""
    assistant, car, model, report = execution(
        tool_response(('call_contact', {'name': 'Roberta'})),
        tool_response(('call_contact', {'name': 'Roberta'})),
    )
    assert qt_call(lambda: assistant.handle_text('Zadzwoń do Roberta', report=report,
                                                turn_id=report.begin_turn())) == ''
    ends = [e for e in report.snapshot()['events'] if e['type'] == 'tool_end' and e['name'] == 'call_contact']
    assert len(ends) == 1                         # the call in the planning reply itself never ran
    assert car.contacts.currentContactName == 'Robert Lewandowski'
    assert model.requests == 2


def test_small_talk_in_plan_response_is_answered_not_rejected(execution, qt_call):
    assistant, car, model, report = execution(AIMessage(content='Proszę bardzo.'), AIMessage(content='Proszę.'))
    assert qt_call(lambda: assistant.handle_text('Dziękuję', report=report, turn_id=report.begin_turn())) == 'Proszę.'


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
        tool_response(('set_action_plan', {'actions': ['select_track', 'pause_music']})),
        tool_response(('get_track_list', {})),
        tool_response(('select_track', {'title': 'Christmas Eve'}), ('pause_music', {})),
    )
    pause_started = Event()
    import assistant.tools as tools

    original = tools.perform

    def delayed_selection(car, action, payload):
        if action == 'select_track':
            pause_started.wait(timeout=0.2)
        else:
            pause_started.set()
        return original(car, action, payload)

    monkeypatch.setattr(tools, 'perform', delayed_selection)
    qt_call(lambda: assistant.handle_text('Wybierz i zapauzuj utwór', report=report,
                                        turn_id=report.begin_turn()))
    assert car.music.isPlaying is False
    assert model.requests == 3


def test_host_sets_plan_from_json_before_requested_call(execution, qt_call):
    assistant, car, model, report = execution(
        AIMessage(content='{"actions":["call_contact"]}'),
        tool_response(('get_contacts', {})),
        tool_response(('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'})),
    )
    assert qt_call(lambda: assistant.handle_text('Zadzwoń do Roberta', report=report,
                                                turn_id=report.begin_turn())) == ''
    assert car.contacts.currentContactName == 'Robert Lewandowski'
    assert model.requests == 3


def test_empty_information_plan_does_not_end_before_answer(execution, qt_call):
    assistant, car, model, report = execution(
        AIMessage(content='{"actions":[]}'),
        tool_response(('get_track_list', {})),
        AIMessage(content='Dostępne są trzy utwory.'),
    )
    assert qt_call(lambda: assistant.handle_text('Jakie masz utwory?', report=report,
                                                turn_id=report.begin_turn())) == 'Dostępne są trzy utwory.'
    assert model.requests == 3


def test_invalid_json_plan_cannot_reach_controller(execution, qt_call):
    assistant, car, model, report = execution(AIMessage(content='{"actions":["unknown"]}'))
    with pytest.raises(RuntimeError, match='ustalić planu'):
        qt_call(lambda: assistant.handle_text('Zadzwoń', report=report, turn_id=report.begin_turn()))
    assert car.contacts.currentContactName == ''


def test_empty_plan_cannot_loop_through_side_effects(execution, qt_call):
    assistant, car, model, report = execution(
        AIMessage(content='{"actions":[]}'),
        tool_response(('get_contacts', {})),
        tool_response(('get_track_list', {})),
        tool_response(('select_track', {'title': 'Christmas Eve'})),
        tool_response(('pause_music', {})),
    )
    with pytest.raises(RuntimeError, match='unplanned_action'):
        qt_call(lambda: assistant.handle_text('Niezrozumiałe wejście', report=report,
                                            turn_id=report.begin_turn()))
    assert model.requests == 4
    assert car.music.isPlaying is False
    ends = [event for event in report.snapshot()['events'] if event['type'] == 'tool_end']
    assert ends[-1]['name'] == 'select_track'
    assert json.loads(ends[-1]['output'])['reason'] == 'unplanned_action'
    assert report.snapshot()['events'][-1]['success'] is False


def test_new_turn_recovers_real_agent_checkpoint_after_blocked_action(execution, qt_call):
    call = ('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'})
    assistant, car, model, report = execution(
        AIMessage(content='{"actions":[]}'), tool_response(call),
        AIMessage(content='{"actions":["call_contact"]}'), tool_response(call),
    )
    turn = report.begin_turn()
    with pytest.raises(RuntimeError, match='unplanned_action'):
        qt_call(lambda: assistant.handle_text('Niezrozumiałe wejście', report=report, turn_id=turn))
    report.end_turn(turn, 'failed')
    turn = report.begin_turn()
    assert qt_call(lambda: assistant.handle_text('Zadzwoń do Roberta', report=report, turn_id=turn)) == ''
    report.end_turn(turn, 'completed')
    assert model.requests == 4
    assert car.contacts.currentContactName == 'Robert Lewandowski'
    assert report.snapshot()['counts'] == {'completed': 1, 'failed': 1, 'interrupted': 0}


def test_blocked_action_stops_remaining_effects_in_same_batch(execution, qt_call):
    assistant, car, model, report = execution(
        AIMessage(content='{"actions":["call_contact"]}'),
        tool_response(('pause_music', {}),
                      ('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'})),
    )
    with pytest.raises(RuntimeError, match='unplanned_action'):
        qt_call(lambda: assistant.handle_text('Zadzwoń', report=report, turn_id=report.begin_turn()))
    assert car.contacts.currentContactName == ''
    assert car.music.isPlaying is False
    assert model.requests == 2


def test_mixed_action_and_question_finishes_only_after_answer(execution, qt_call):
    assistant, car, model, report = execution(
        AIMessage(content='{"actions":["call_contact"],"answer_required":true}'),
        tool_response(('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'})),
        tool_response(('get_track_list', {})),
        AIMessage(content='Masz Christmas Eve, Chill song i Dynamic music.'),
    )
    answer = qt_call(lambda: assistant.handle_text('Zadzwoń do Roberta i powiedz, jakie mam utwory.',
                                                  report=report, turn_id=report.begin_turn()))
    assert answer == 'Masz Christmas Eve, Chill song i Dynamic music.'
    assert car.contacts.currentContactName == 'Robert Lewandowski'
    assert model.requests == 4
    assert report.snapshot()['events'][-1]['answer_required'] is True


@pytest.mark.parametrize('answer', ['', ' ', '\n'])
def test_requested_answer_cannot_be_replaced_with_silence(execution, qt_call, answer):
    assistant, car, model, report = execution(
        AIMessage(content='{"actions":["call_contact"],"answer_required":true}'),
        tool_response(('call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'})),
        AIMessage(content=answer),
    )
    with pytest.raises(RuntimeError, match='bez komunikatu'):
        qt_call(lambda: assistant.handle_text('Zadzwoń i podaj listę utworów.',
                                            report=report, turn_id=report.begin_turn()))
    assert model.requests == 3


@pytest.mark.parametrize('name, initially_playing, expected', [
    ('pause_music', False, False), ('pause_music', True, False),
    ('resume_music', False, True), ('resume_music', True, True),
])
def test_voice_playback_sets_requested_state(execution, qt_call, name, initially_playing, expected):
    assistant, car, model, report = execution(
        AIMessage(content=json.dumps({'actions': [name]})), tool_response((name, {})),
    )
    car.music.set_playback(initially_playing)
    assert qt_call(lambda: assistant.handle_text('Pauza lub wznów zgodnie z poleceniem.',
                                                report=report, turn_id=report.begin_turn())) == ''
    assert car.music.isPlaying is expected
    assert model.requests == 2
    assert 'play_pause' not in {tool.name for tool in assistant.build_tools()}


def test_identical_retry_of_failed_action_stops_turn_without_controller_call(execution, qt_call, monkeypatch):
    import assistant.tools as tools
    from assistant import IncompleteExecutionError

    unknown = {'address': 'Żołnierska 1, Warszawa'}
    assistant, car, model, report = execution(
        tool_response(('set_action_plan', {'actions': ['navigate_to']})),
        tool_response(('navigate_to', unknown)),
        tool_response(('navigate_to', unknown)),
    )
    calls = []
    original = tools.perform
    monkeypatch.setattr(tools, 'perform', lambda car, action, payload: calls.append(action) or original(car, action, payload))
    with pytest.raises(IncompleteExecutionError, match='repeated_failure'):
        qt_call(lambda: assistant.handle_text('Ustaw nawigację na Żołnierską', report=report,
                                            turn_id=report.begin_turn()))
    assert calls == ['set_destination']          # second identical attempt never reached the car
    assert model.requests == 3                    # no further LLM request after the refusal
    blocked = [json.loads(e['output']) for e in report.snapshot()['events']
               if e['type'] == 'tool_end' and e['name'] == 'navigate_to' and 'blocked' in e['output']]
    assert blocked[0]['reason'] == 'repeated_failure'


def test_failed_action_may_be_retried_with_corrected_arguments(execution, qt_call):
    assistant, car, model, report = execution(
        tool_response(('set_action_plan', {'actions': ['navigate_to']})),
        tool_response(('navigate_to', {'address': 'Żołnierska 1, Warszawa'})),
        tool_response(('get_places_list', {})),
        tool_response(('navigate_to', {'address': 'Żołnierska 47'})),
    )
    assert qt_call(lambda: assistant.handle_text('Ustaw nawigację na Żołnierską', report=report,
                                                turn_id=report.begin_turn())) == ''
    assert car.navigation.destination == 'ul. Żołnierska 47, Szczecin'
