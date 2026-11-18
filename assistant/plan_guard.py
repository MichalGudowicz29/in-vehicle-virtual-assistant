"""Deterministic guard between the LLM and the car: effects run only as declared in the plan.

A small local model may repeat, reorder or invent actions. The guard keeps one turn's state:
the immutable plan, how many planned actions already succeeded, which effects ran, and the
first reason an action was refused. The LLM decides *what* to do; the guard decides *whether*
a requested effect may reach a controller.
"""

import json
from threading import RLock
from typing import Callable, Literal

from pydantic import BaseModel


ActionName = Literal['call_contact', 'navigate_to', 'select_track', 'add_stop',
                     'pause_music', 'resume_music', 'next_track', 'previous_track']

# Effects that must not be repeated within one turn (e.g. a second phone call).
ONCE_PER_TURN = frozenset({'call_contact', 'navigate_to', 'select_track', 'add_stop'})


class IncompleteExecutionError(RuntimeError):
    """The model did not produce an executable plan or a completed response."""


class ExecutionPlan(BaseModel):
    actions: list[ActionName]
    answer_required: bool = False


class PlanGuard:
    def __init__(self):
        self._lock = RLock()
        self.reset()

    def reset(self):
        """Start a new turn."""
        self.actions: list[str] | None = None
        self.answer_required = False
        self.next_index = 0
        self.completed: dict[tuple, dict] = {}
        self.failed: set[tuple] = set()          # effects that already failed with these arguments
        self.response_tools: set[str] = set()   # tools requested in the latest model response
        self.blocked_reason: str | None = None
        self.listed_track_titles: set[str] = set()

    @property
    def plan_done(self) -> bool:
        return self.actions is not None and self.next_index == len(self.actions)

    @property
    def finished_silently(self) -> bool:
        """Every requested effect succeeded and the user asked no question: end without speech."""
        return bool(self.actions) and self.plan_done and not self.answer_required

    def set_plan(self, actions: list[str], answer_required: bool) -> dict:
        with self._lock:
            if self.actions is not None:
                return {'success': False, 'reason': 'invalid_or_locked_plan',
                        'message': 'Plan można ustalić tylko raz w turze.'}
            self.actions = list(actions)
            self.answer_required = answer_required
            return {'success': True, 'actions': self.actions, 'answer_required': answer_required}

    def execute(self, name: str, action: str, payload: dict, effect: Callable[[], dict]) -> dict:
        """Run `effect` only if `name` is the next planned action; record the outcome."""
        key = (name, json.dumps(payload, sort_keys=True, ensure_ascii=False))
        with self._lock:
            reason = self._refusal(name, key)
            if reason:
                self.blocked_reason = reason
                return {'success': False, 'action': action, 'blocked': True, 'reason': reason,
                        'message': 'Akcja zablokowana: wykonana wcześniej albo niezgodna z bieżącym planem.'}
            result = effect()
            if result.get('success') is True:
                self.completed[key] = result
                self.next_index += 1
            else:
                self.failed.add(key)
            return result

    def _refusal(self, name, key) -> str | None:
        if self.blocked_reason is not None:
            return self.blocked_reason            # one violation stops the rest of the turn
        if 'set_action_plan' in self.response_tools:
            return 'plan_not_observed'            # plan and effect in the same model response
        if key in self.completed and name in ONCE_PER_TURN:
            return 'duplicate_action'
        if key in self.failed:
            return 'repeated_failure'             # same arguments cannot succeed now; stop the loop
        if self.actions is None:
            return 'missing_plan'
        if self.next_index >= len(self.actions) or self.actions[self.next_index] != name:
            return 'unplanned_action'
        return None
