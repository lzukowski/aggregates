from functools import singledispatchmethod
from typing import ContextManager, Text

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
from project_management.eventsourcing import Aggregate, EventStore, Repository


class Issue(Aggregate):
    state: State = None

    def create(self) -> None:
        if not self.can_create():
            raise InvalidTransition('create', self.id)
        self._trigger_event(IssueOpened)

    def start(self) -> None:
        if not self.can_start():
            raise InvalidTransition('start', self.id)
        self._trigger_event(IssueProgressStarted)

    def stop(self) -> None:
        if not self.can_stop():
            raise InvalidTransition('stop', self.id)
        self._trigger_event(IssueProgressStopped)

    def close(self) -> None:
        if not self.can_close():
            raise InvalidTransition('close', self.id)
        self._trigger_event(IssueClosed)

    def reopen(self) -> None:
        if not self.can_reopen():
            raise InvalidTransition('reopen', self.id)
        self._trigger_event(IssueReopened)

    def resolve(self) -> None:
        if not self.can_resolve():
            raise InvalidTransition('resolve', self.id)
        self._trigger_event(IssueResolved)

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

    def apply(self, event: Event) -> None:
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
        super().apply(event)

    def __repr__(self) -> Text:
        return (
            f'<{self.__class__.__name__} '
            f'id={self.id!s} '
            f'version={self.version} '
            f'state={self.state and self.state.name}'
            f'>'
        )


class CommandHandler(Handler):
    def __init__(self, event_store: EventStore) -> None:
        super().__init__(event_store)
        self._repository = Repository[Issue](event_store=event_store)

    @singledispatchmethod
    def __call__(self, cmd: Command) -> None:
        ...

    @__call__.register
    def _(self, cmd: CreateIssue) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.create()

    @__call__.register
    def _(self, cmd: CloseIssue) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.close()

    @__call__.register
    def _(self, cmd: StartIssueProgress) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.start()

    @__call__.register
    def _(self, cmd: StopIssueProgress) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.stop()

    @__call__.register
    def _(self, cmd: ReopenIssue) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.reopen()

    @__call__.register
    def _(self, cmd: ResolveIssue) -> None:
        with self.aggregate(cmd.id) as issue:
            issue.resolve()

    def aggregate(self, issue_id: IssueID) -> ContextManager[Issue]:
        return self._repository.aggregate(Issue(issue_id))
