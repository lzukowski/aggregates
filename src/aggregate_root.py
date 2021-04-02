from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from functools import singledispatchmethod
from typing import ContextManager, Text

from project_management import Handler, InvalidTransition, IssueID
from project_management.commands import (
    CloseIssue,
    Command,
    CreateIssue,
    ReopenIssue,
    ResolveIssue,
    StartIssueProgress,
    StopIssueProgress,
)
from project_management.events import (
    Event,
    IssueClosed,
    IssueOpened,
    IssueProgressStarted,
    IssueProgressStopped,
    IssueReopened,
    IssueResolved,
)
from project_management.eventsourcing import Aggregate, EventStore, Repository


class Issue(Aggregate):
    class State(Enum):
        OPEN = 'OPEN'
        CLOSED = 'CLOSED'
        IN_PROGRESS = 'IN_PROGRESS'
        REOPENED = 'REOPENED'
        RESOLVED = 'RESOLVED'

    state: State = None

    def create(self) -> None:
        if not self.can_create():
            raise InvalidTransition('create', self.id)
        self.trigger_event(IssueOpened)

    def start(self) -> None:
        if not self.can_start():
            raise InvalidTransition('start', self.id)
        self.trigger_event(IssueProgressStarted)

    def stop(self) -> None:
        if not self.can_stop():
            raise InvalidTransition('stop', self.id)
        self.trigger_event(IssueProgressStopped)

    def close(self) -> None:
        if not self.can_close():
            raise InvalidTransition('close', self.id)
        self.trigger_event(IssueClosed)

    def reopen(self) -> None:
        if not self.can_reopen():
            raise InvalidTransition('reopen', self.id)
        self.trigger_event(IssueReopened)

    def resolve(self) -> None:
        if not self.can_resolve():
            raise InvalidTransition('resolve', self.id)
        self.trigger_event(IssueResolved)

    def can_create(self) -> bool:
        return self.state != Issue.State.OPEN

    def can_start(self) -> bool:
        valid_states = [Issue.State.OPEN, Issue.State.REOPENED]
        return self.state in valid_states

    def can_close(self) -> bool:
        valid_states = [
            Issue.State.OPEN,
            Issue.State.IN_PROGRESS,
            Issue.State.REOPENED,
            Issue.State.RESOLVED,
        ]
        return self.state in valid_states

    def can_reopen(self) -> bool:
        valid_states = [Issue.State.CLOSED, Issue.State.RESOLVED]
        return self.state in valid_states

    def can_stop(self) -> bool:
        return self.state == Issue.State.IN_PROGRESS

    def can_resolve(self) -> bool:
        valid_states = [
            Issue.State.OPEN, Issue.State.REOPENED, Issue.State.IN_PROGRESS,
        ]
        return self.state in valid_states

    def apply(self, event: Event) -> None:
        event_type = type(event)
        if event_type == IssueOpened:
            self.state = Issue.State.OPEN
        elif event_type == IssueProgressStarted:
            self.state = Issue.State.IN_PROGRESS
        elif event_type == IssueProgressStopped:
            self.state = Issue.State.OPEN
        elif event_type == IssueReopened:
            self.state = Issue.State.REOPENED
        elif event_type == IssueResolved:
            self.state = Issue.State.RESOLVED
        elif event_type == IssueClosed:
            self.state = Issue.State.CLOSED
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
        with self._aggregate(cmd.id) as issue:
            issue.create()

    @__call__.register
    def _(self, cmd: CloseIssue) -> None:
        with self._aggregate(cmd.id) as issue:
            issue.close()

    @__call__.register
    def _(self, cmd: StartIssueProgress) -> None:
        with self._aggregate(cmd.id) as issue:
            issue.start()

    @__call__.register
    def _(self, cmd: StopIssueProgress) -> None:
        with self._aggregate(cmd.id) as issue:
            issue.stop()

    @__call__.register
    def _(self, cmd: ReopenIssue) -> None:
        with self._aggregate(cmd.id) as issue:
            issue.reopen()

    @__call__.register
    def _(self, cmd: ResolveIssue) -> None:
        with self._aggregate(cmd.id) as issue:
            issue.resolve()

    @contextmanager
    def _aggregate(self, issue_id: IssueID) -> ContextManager[Issue]:
        issue = Issue(issue_id)
        self._repository.get(issue)
        yield issue
        self._repository.save(issue)
