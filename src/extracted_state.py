from contextlib import contextmanager
from datetime import datetime, timezone
from functools import singledispatchmethod
from typing import Iterator, List, Optional, Text, Type
from uuid import UUID

from project_management import (
    Command,
    Event,
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
from project_management.eventsourcing import TEvent


class IssueState:
    id: UUID
    version: int

    def __init__(self, issue_id: UUID) -> None:
        self.id: UUID = issue_id
        self.version = 0
        self._status: Optional[State] = None

    @property
    def open(self) -> bool:
        return self._status == State.OPEN

    @property
    def closed(self) -> bool:
        return self._status == State.CLOSED

    @property
    def in_progress(self) -> bool:
        return self._status == State.IN_PROGRESS

    @property
    def reopened(self) -> bool:
        return self._status == State.REOPENED

    @property
    def resolved(self) -> bool:
        return self._status == State.RESOLVED

    def apply(self, event: Event) -> None:
        event_type = type(event)
        if event_type == IssueOpened:
            self._status = State.OPEN
        elif event_type == IssueProgressStarted:
            self._status = State.IN_PROGRESS
        elif event_type == IssueProgressStopped:
            self._status = State.OPEN
        elif event_type == IssueReopened:
            self._status = State.REOPENED
        elif event_type == IssueResolved:
            self._status = State.RESOLVED
        elif event_type == IssueClosed:
            self._status = State.CLOSED
        self.version = event.originator_version

    def __repr__(self) -> Text:
        return (
            f'<{self.__class__.__name__} id={self.id} version={self.version}>'
        )

    def __str__(self) -> Text:
        return f'{self._status and self._status.name}'


class Issue:
    def __init__(self, state: IssueState) -> None:
        self._state = state
        self._changes: List[Event] = []

    @property
    def changes(self) -> Iterator[Event]:
        return iter(self._changes)

    def create(self) -> None:
        if not self.can_create:
            raise InvalidTransition('create', self._state.id)
        self._trigger_event(IssueOpened)

    def start(self) -> None:
        if not self.can_start:
            raise InvalidTransition('start', self._state.id)
        self._trigger_event(IssueProgressStarted)

    def stop(self) -> None:
        if not self.can_stop:
            raise InvalidTransition('stop', self._state.id)
        self._trigger_event(IssueProgressStopped)

    def close(self) -> None:
        if not self.can_close:
            raise InvalidTransition('close', self._state.id)
        self._trigger_event(IssueClosed)

    def reopen(self) -> None:
        if not self.can_reopen:
            raise InvalidTransition('reopen', self._state.id)
        self._trigger_event(IssueReopened)

    def resolve(self) -> None:
        if not self.can_resolve:
            raise InvalidTransition('resolve', self._state.id)
        self._trigger_event(IssueResolved)

    @property
    def can_create(self) -> bool:
        return not self._state.open

    @property
    def can_start(self) -> bool:
        return self._state.open or self._state.reopened

    @property
    def can_close(self) -> bool:
        return (
            self._state.open
            or self._state.in_progress
            or self._state.reopened
            or self._state.resolved
        )

    @property
    def can_reopen(self) -> bool:
        return self._state.closed or self._state.resolved

    @property
    def can_stop(self) -> bool:
        return self._state.in_progress

    @property
    def can_resolve(self) -> bool:
        return (
            self._state.open
            or self._state.reopened
            or self._state.in_progress
        )

    def _trigger_event(self, event_class: Type[TEvent]) -> None:
        new_event = event_class(
            originator_id=self._state.id,
            originator_version=self._state.version + 1,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self._state.apply(new_event)
        self._changes.append(new_event)

    def __repr__(self) -> Text:
        return (
            f'<{self.__class__.__name__} '
            f'id={self._state.id!s} '
            f'version={self._state.version} '
            f'state={self._state!s}'
            f'>'
        )


class CommandHandler(Handler):
    @singledispatchmethod
    def __call__(self, cmd: Command) -> None:
        ...

    @__call__.register
    def create(self, cmd: CreateIssue) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.create()

    @__call__.register
    def close(self, cmd: CloseIssue) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.close()

    @__call__.register
    def start(self, cmd: StartIssueProgress) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.start()

    @__call__.register
    def stop(self, cmd: StopIssueProgress) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.stop()

    @__call__.register
    def reopen(self, cmd: ReopenIssue) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.reopen()

    @__call__.register
    def resolve(self, cmd: ResolveIssue) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.resolve()

    @contextmanager
    def aggregate(self, issue_id: IssueID) -> Iterator[Issue]:
        state = IssueState(issue_id)
        for event in self._event_store.get(issue_id):
            state.apply(event)
        issue = Issue(state)
        yield issue
        self._event_store.put(*issue.changes)
