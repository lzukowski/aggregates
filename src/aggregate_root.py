from functools import singledispatchmethod
from typing import Optional, Text

from event_sourcery import Event, EventStore, Repository
from event_sourcery.aggregate import Aggregate

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


class Issue(Aggregate):
    state: Optional[State] = None

    def create(self) -> None:
        if not self.can_create():
            raise InvalidTransition('create')
        self._event(IssueOpened)

    def start(self) -> None:
        if not self.can_start():
            raise InvalidTransition('start')
        self._event(IssueProgressStarted)

    def stop(self) -> None:
        if not self.can_stop():
            raise InvalidTransition('stop')
        self._event(IssueProgressStopped)

    def close(self) -> None:
        if not self.can_close():
            raise InvalidTransition('close')
        self._event(IssueClosed)

    def reopen(self) -> None:
        if not self.can_reopen():
            raise InvalidTransition('reopen')
        self._event(IssueReopened)

    def resolve(self) -> None:
        if not self.can_resolve():
            raise InvalidTransition('resolve')
        self._event(IssueResolved)

    def can_create(self) -> bool:
        return self.state != State.OPEN

    def can_start(self) -> bool:
        valid_states = [State.OPEN, State.REOPENED]
        return self.state in valid_states

    def can_close(self) -> bool:
        valid_states = [
            State.OPEN,
            State.IN_PROGRESS,
            State.REOPENED,
            State.RESOLVED,
        ]
        return self.state in valid_states

    def can_reopen(self) -> bool:
        valid_states = [State.CLOSED, State.RESOLVED]
        return self.state in valid_states

    def can_stop(self) -> bool:
        return self.state == State.IN_PROGRESS

    def can_resolve(self) -> bool:
        valid_states = [State.OPEN, State.REOPENED, State.IN_PROGRESS]
        return self.state in valid_states

    def _apply(self, event: Event) -> None:
        event_type = type(event)
        if event_type == IssueOpened:
            self.state = State.OPEN
        elif event_type == IssueProgressStarted:
            self.state = State.IN_PROGRESS
        elif event_type == IssueProgressStopped:
            self.state = State.OPEN
        elif event_type == IssueReopened:
            self.state = State.REOPENED
        elif event_type == IssueResolved:
            self.state = State.RESOLVED
        elif event_type == IssueClosed:
            self.state = State.CLOSED

    def __repr__(self) -> Text:
        return (
            f'<{self.__class__.__name__} '
            f'version={self.__version} '
            f'state={self.state and self.state.name}'
            f'>'
        )


class CommandHandler(Handler):
    def __init__(self, event_store: EventStore) -> None:
        super().__init__(event_store)
        self._repository = Repository[Issue](event_store, Issue)

    @singledispatchmethod
    def __call__(self, cmd: Command) -> None:
        ...

    @__call__.register
    def create(self, cmd: CreateIssue) -> None:
        with self._repository.aggregate(cmd.id) as issue:
            issue.create()

    @__call__.register
    def close(self, cmd: CloseIssue) -> None:
        with self._repository.aggregate(cmd.id) as issue:
            issue.close()

    @__call__.register
    def start(self, cmd: StartIssueProgress) -> None:
        with self._repository.aggregate(cmd.id) as issue:
            issue.start()

    @__call__.register
    def stop(self, cmd: StopIssueProgress) -> None:
        with self._repository.aggregate(cmd.id) as issue:
            issue.stop()

    @__call__.register
    def reopen(self, cmd: ReopenIssue) -> None:
        with self._repository.aggregate(cmd.id) as issue:
            issue.reopen()

    @__call__.register
    def resolve(self, cmd: ResolveIssue) -> None:
        with self._repository.aggregate(cmd.id) as issue:
            issue.resolve()
