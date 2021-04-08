import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import singledispatchmethod
from typing import Callable, Optional, Text, Type

from project_management import (
    Command,
    Handler,
    InvalidTransition,
    IssueID,
    State,
)
from project_management.commands import (
    CloseIssue,
    CreateIssue,
    ReopenIssue,
    ResolveIssue,
    StartIssueProgress,
    StopIssueProgress,
)
from project_management.events import (
    IssueClosed,
    IssueOpened,
    IssueProgressStarted,
    IssueProgressStopped,
    IssueReopened,
    IssueResolved,
)
from project_management.eventsourcing import Event, EventStore, TEvent


@dataclass
class Issue:
    id: IssueID
    version: int = 0
    _state: Optional[State] = None

    def create(self) -> None:
        self._state = State.OPEN

    def start(self) -> None:
        self._state = State.IN_PROGRESS

    def stop(self) -> None:
        self._state = State.OPEN

    def close(self) -> None:
        self._state = State.CLOSED

    def reopen(self) -> None:
        self._state = State.REOPENED

    def resolve(self) -> None:
        self._state = State.RESOLVED

    def can_create(self) -> bool:
        return self._state != State.OPEN

    def can_start(self) -> bool:
        valid_states = [State.OPEN, State.REOPENED]
        return self._state in valid_states

    def can_close(self) -> bool:
        valid_states = [
            State.OPEN,
            State.IN_PROGRESS,
            State.REOPENED,
            State.RESOLVED,
        ]
        return self._state in valid_states

    def can_reopen(self) -> bool:
        valid_states = [State.CLOSED, State.RESOLVED]
        return self._state in valid_states

    def can_stop(self) -> bool:
        return self._state == State.IN_PROGRESS

    def can_resolve(self) -> bool:
        valid_states = [State.OPEN, State.REOPENED, State.IN_PROGRESS]
        return self._state in valid_states

    def __repr__(self) -> Text:
        return (
            f'<{self.__class__.__name__} '
            f'id={self.id!s} '
            f'version={self.version} '
            f'state={self._state and self._state.name}'
            f'>'
        )


class IssueProjection:
    def __init__(self, event_store: EventStore) -> None:
        self.event_store = event_store

    def __call__(self, issue: Issue) -> Issue:
        for event in self.event_store.get(issue.id):
            self.apply(event, issue)
            issue.version = event.originator_version
        return issue

    def apply(self, event: Event, issue: Issue) -> None:
        event_type = type(event)
        if event_type == IssueOpened:
            issue.create()
        elif event_type == IssueProgressStarted:
            issue.start()
        elif event_type == IssueProgressStopped:
            issue.stop()
        elif event_type == IssueReopened:
            issue.reopen()
        elif event_type == IssueResolved:
            issue.resolve()
        elif event_type == IssueClosed:
            issue.close()


class CommandHandler(Handler):
    def __call__(self, cmd: Command) -> None:
        projection = IssueProjection(self._event_store)
        issue = projection(Issue(cmd.id))
        event = self.process(cmd, issue)
        self._trigger_event(issue, event)

    @singledispatchmethod
    def process(self, cmd: Command, issue: Issue) -> Type[Event]:
        ...

    @process.register
    def create(self, _: CreateIssue, issue: Issue) -> Type[Event]:
        self.raise_invalid_transition(unless=issue.can_create)
        return IssueOpened

    @process.register
    def start(self, _: StartIssueProgress, issue: Issue) -> Type[Event]:
        self.raise_invalid_transition(unless=issue.can_start)
        return IssueProgressStarted

    @process.register
    def stop(self, _: StopIssueProgress, issue: Issue) -> Type[Event]:
        self.raise_invalid_transition(unless=issue.can_stop)
        return IssueProgressStopped

    @process.register
    def close(self, _: CloseIssue, issue: Issue) -> Type[Event]:
        self.raise_invalid_transition(unless=issue.can_close)
        return IssueClosed

    @process.register
    def reopen(self, _: ReopenIssue, issue: Issue) -> Type[Event]:
        self.raise_invalid_transition(unless=issue.can_reopen)
        return IssueReopened

    @process.register
    def resolve(self, _: ResolveIssue, issue: Issue) -> Type[Event]:
        self.raise_invalid_transition(unless=issue.can_resolve)
        return IssueResolved

    def raise_invalid_transition(self, unless: Callable[[], bool]) -> None:
        assert inspect.ismethod(unless)
        issue: Issue = inspect.getcallargs(unless)['self']
        if unless():
            return
        raise InvalidTransition(issue.id)

    def _trigger_event(self, issue: Issue, event_class: Type[TEvent]) -> None:
        event = event_class(
            originator_id=issue.id,
            originator_version=issue.version + 1,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self._event_store.put(event)
