from contextlib import contextmanager
from datetime import datetime, timezone
from functools import singledispatchmethod
from typing import ContextManager, List, Optional, Tuple, Type

from event_sourcery import Event, EventStore

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

Events = List[Event]
Version = int


class Issue:
    state: Optional[State] = None
    version: Version
    changes: Events

    def __init__(
            self, issue_id: IssueID, events: Events, version: Version,
    ) -> None:
        self.id = issue_id
        self.version = version

        self.changes = []
        self._load(events)
        self.changes.clear()

    def create(self) -> None:
        if not self.can_create():
            raise InvalidTransition('create', self.id)
        self.state = State.OPEN
        self._register_event(IssueOpened)

    def start(self) -> None:
        if not self.can_start():
            raise InvalidTransition('start', self.id)
        self.state = State.IN_PROGRESS
        self._register_event(IssueProgressStarted)

    def stop(self) -> None:
        if not self.can_stop():
            raise InvalidTransition('stop', self.id)
        self.state = State.OPEN
        self._register_event(IssueProgressStopped)

    def close(self) -> None:
        if not self.can_close():
            raise InvalidTransition('close', self.id)
        self.state = State.CLOSED
        self._register_event(IssueClosed)

    def reopen(self) -> None:
        if not self.can_reopen():
            raise InvalidTransition('reopen', self.id)
        self.state = State.REOPENED
        self._register_event(IssueReopened)

    def resolve(self) -> None:
        if not self.can_resolve():
            raise InvalidTransition('resolve', self.id)
        self.state = State.RESOLVED
        self._register_event(IssueResolved)

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

    def _load(self, events: Events) -> None:
        for event in events:
            event_type = type(event)
            if event_type == IssueOpened:
                self.create()
            elif event_type == IssueProgressStarted:
                self.start()
            elif event_type == IssueProgressStopped:
                self.stop()
            elif event_type == IssueReopened:
                self.reopen()
            elif event_type == IssueResolved:
                self.resolve()
            elif event_type == IssueClosed:
                self.close()

    def _register_event(self, event_class: Type[Event]) -> None:
        self.changes.append(
            event_class(
                originator_id=self.id,
                version=self.version + 1,
                timestamp=datetime.now(tz=timezone.utc),
            )
        )


class Repository:
    def __init__(self, event_store: EventStore) -> None:
        self._store = event_store

    def load(self, issue_id: IssueID) -> Tuple[Events, Version]:
        events = list(self._store.iter(issue_id))
        return events, len(events)

    def save(self, issue_id: IssueID, changes: Events) -> None:
        self._store.publish(
            issue_id, changes, expected_version=changes[-1].version,
        )


class CommandHandler(Handler):
    def __init__(self, event_store: EventStore) -> None:
        super().__init__(event_store)
        self._repository = Repository(event_store=event_store)

    def __call__(self, cmd: Command) -> None:
        with self.aggregate(cmd.id) as issue:
            self.process(cmd, issue)

    @singledispatchmethod
    def process(self, cmd: Command, issue: Issue) -> None:
        raise NotImplementedError

    @process.register
    def create(self, _: CreateIssue, issue: Issue) -> None:
        issue.create()

    @process.register
    def close(self, _: CloseIssue, issue: Issue) -> None:
        issue.close()

    @process.register
    def start(self, _: StartIssueProgress, issue: Issue) -> None:
        issue.start()

    @process.register
    def stop(self, _: StopIssueProgress, issue: Issue) -> None:
        issue.stop()

    @process.register
    def reopen(self, _: ReopenIssue, issue: Issue) -> None:
        issue.reopen()

    @process.register
    def resolve(self, _: ResolveIssue, issue: Issue) -> None:
        issue.resolve()

    @contextmanager
    def aggregate(self, issue_id: IssueID) -> ContextManager[Issue]:
        events, current_version = self._repository.load(issue_id)
        issue = Issue(issue_id, events, current_version)
        yield issue
        self._repository.save(issue_id, issue.changes)
