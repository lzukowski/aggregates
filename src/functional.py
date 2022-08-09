from datetime import datetime, timezone
from functools import singledispatchmethod
from typing import Optional, Text, Type
from uuid import UUID

from event_sourcery import Event

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


class IssueState:
    id: UUID
    version: int = 0

    def __init__(self, issue_id: UUID) -> None:
        self.id: UUID = issue_id
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
        self.version += 1

    def __repr__(self) -> Text:
        return (
            f'<'
            f'{self.__class__.__name__} '
            f'id={self.id} '
            f'version={self.version} '
            f'status={self._status.name}'
            f'>'
        )

    def __str__(self) -> Text:
        return f'{self._status and self._status.name}'


class Create:
    def __call__(self, state: IssueState) -> Type[Event]:
        if not self.can_create(state):
            raise InvalidTransition('create', state.id)
        return IssueOpened

    @staticmethod
    def can_create(state: IssueState) -> bool:
        return not state.open


class Start:
    def __call__(self, state: IssueState) -> Type[Event]:
        if not self.can_start(state):
            raise InvalidTransition('start', state.id)
        return IssueProgressStarted

    @staticmethod
    def can_start(state: IssueState) -> bool:
        return state.open or state.reopened


class Stop:
    def __call__(self, state: IssueState) -> Type[Event]:
        if not self.can_stop(state):
            raise InvalidTransition('stop', state.id)
        return IssueProgressStopped

    @staticmethod
    def can_stop(state: IssueState) -> bool:
        return state.in_progress


class Close:
    def __call__(self, state: IssueState) -> Type[Event]:
        if not self.can_close(state):
            raise InvalidTransition('close', state.id, state)
        return IssueClosed

    @staticmethod
    def can_close(state: IssueState) -> bool:
        return (
            state.open
            or state.in_progress
            or state.reopened
            or state.resolved
        )


class Reopen:
    def __call__(self, state: IssueState) -> Type[Event]:
        if not self.can_reopen(state):
            raise InvalidTransition('reopen', state.id)
        return IssueReopened

    @staticmethod
    def can_reopen(state: IssueState) -> bool:
        return state.closed or state.resolved


class Resolve:
    def __call__(self, state: IssueState) -> Type[Event]:
        if not self.can_resolve(state):
            raise InvalidTransition('resolve', state.id)
        return IssueResolved

    @staticmethod
    def can_resolve(state: IssueState) -> bool:
        return state.open or state.reopened or state.in_progress


class CommandHandler(Handler):
    def __call__(self, cmd: Command) -> None:
        state = self.get_state(cmd.id)
        event = self.process(cmd, state)
        self._trigger_event(state, event)

    @singledispatchmethod
    def process(self, cmd: Command, state: IssueState) -> Type[Event]:
        ...

    @process.register
    def create(self, _: CreateIssue, state: IssueState) -> Type[Event]:
        return Create()(state)

    @process.register
    def start(self, _: StartIssueProgress, state: IssueState) -> Type[Event]:
        return Start()(state)

    @process.register
    def stop(self, _: StopIssueProgress, state: IssueState) -> Type[Event]:
        return Stop()(state)

    @process.register
    def close(self, _: CloseIssue, state: IssueState) -> Type[Event]:
        return Close()(state)

    @process.register
    def reopen(self, _: ReopenIssue, state: IssueState) -> Type[Event]:
        return Reopen()(state)

    @process.register
    def resolve(self, _: ResolveIssue, state: IssueState) -> Type[Event]:
        return Resolve()(state)

    def get_state(self, issue_id: IssueID) -> IssueState:
        state = IssueState(issue_id)
        for event in self._event_store.iter(issue_id):
            state.apply(event)
        return state

    def _trigger_event(
            self, state: IssueState, event_class: Type[Event],
    ) -> None:
        event = event_class(
            originator_id=state.id,
            originator_version=state.version + 1,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self._event_store.publish(
            state.id, [event], expected_version=state.version + 1,
        )
