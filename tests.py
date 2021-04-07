from contextlib import contextmanager
from functools import partialmethod
from inspect import isclass
from typing import Any, Callable, ContextManager, Protocol, Type, Union
from unittest import TestCase, expectedFailure

import aggregate_root
import exposed_queries
import extracted_state
from project_management import (
    Command,
    Event,
    Handler,
    InvalidTransition,
    IssueID,
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
from project_management.eventsourcing import EventStore


class ExperimentsTestBase(Protocol):
    event_store: EventStore
    handler: Handler
    issue_id: IssueID
    assertRaises: Callable[[Type[Exception]], ContextManager] = NotImplemented
    assertEqual: Callable[[Any, Any], None] = NotImplemented

    def test_create(self):
        with self.assert_opened():
            self.act(CreateIssue)

    def test_close(self):
        with self.assert_invalid_transition():
            self.act(CloseIssue)

    def test_resolve(self):
        with self.assert_invalid_transition():
            self.act(ResolveIssue)

    def test_start(self):
        with self.assert_invalid_transition():
            self.act(StartIssueProgress)

    def test_stop(self):
        with self.assert_invalid_transition():
            self.act(StopIssueProgress)

    def test_reopen(self):
        with self.assert_invalid_transition():
            self.act(ReopenIssue)

    def test_start_from_stopped(self):
        self.arrange(CreateIssue, StartIssueProgress, StopIssueProgress)
        with self.assert_started():
            self.act(StartIssueProgress)

    def test_create_from_open(self):
        self.arrange(CreateIssue)
        with self.assert_invalid_transition():
            self.act(CreateIssue)

    def test_resolve_from_opened(self):
        self.arrange(CreateIssue)
        with self.assert_resolved():
            self.act(ResolveIssue)

    def test_resolve_from_in_progress(self):
        self.arrange(CreateIssue, StartIssueProgress)
        with self.assert_resolved():
            self.act(ResolveIssue)

    def test_resolve_from_reopened(self):
        self.arrange(CreateIssue, CloseIssue, ReopenIssue)
        with self.assert_resolved():
            self.act(ResolveIssue)

    def test_resolve_from_resolved(self):
        self.arrange(CreateIssue, ResolveIssue)
        with self.assert_invalid_transition():
            self.act(ResolveIssue)

    def test_start_from_opened(self):
        self.arrange(CreateIssue)
        with self.assert_started():
            self.act(StartIssueProgress)

    def test_start_from_reopened(self):
        self.arrange(CreateIssue, CloseIssue, ReopenIssue)
        with self.assert_started():
            self.act(StartIssueProgress)

    def test_start_from_in_progress(self):
        self.arrange(CreateIssue, StartIssueProgress)
        with self.assert_invalid_transition():
            self.act(StartIssueProgress)

    def test_close_from_opened(self):
        self.arrange(CreateIssue)
        with self.assert_closed():
            self.act(CloseIssue)

    def test_close_from_resolved(self):
        self.arrange(CreateIssue, ResolveIssue)
        with self.assert_closed():
            self.act(CloseIssue)

    def test_close_from_started(self):
        self.arrange(CreateIssue, StartIssueProgress)
        with self.assert_closed():
            self.act(CloseIssue)

    def test_close_from_reopened(self):
        self.arrange(CreateIssue, CloseIssue, ReopenIssue)
        with self.assert_closed():
            self.act(CloseIssue)

    def test_close_from_closed(self):
        self.arrange(CreateIssue, CloseIssue)
        with self.assert_invalid_transition():
            self.act(CloseIssue)

    def test_stop_from_started(self):
        self.arrange(CreateIssue, StartIssueProgress)
        with self.assert_stopped():
            self.act(StopIssueProgress)

    def test_stop_from_open(self):
        self.arrange(CreateIssue)
        with self.assert_invalid_transition():
            self.act(StopIssueProgress)

    def test_reopen_from_closed(self):
        self.arrange(CreateIssue, CloseIssue)
        with self.assert_reopened():
            self.act(ReopenIssue)

    def test_reopen_from_resolved(self):
        self.arrange(CreateIssue, ResolveIssue)
        with self.assert_reopened():
            self.act(ReopenIssue)

    def test_reopen_from_reopened(self):
        self.arrange(CreateIssue, CloseIssue, ReopenIssue)
        with self.assert_invalid_transition():
            self.act(ReopenIssue)

    def test_close_from_create_start_resolved(self):
        self.arrange(CreateIssue, StartIssueProgress, ResolveIssue)
        with self.assert_closed():
            self.act(CloseIssue)

    def test_start_from_create_start_resolved_reopen(self):
        self.arrange(
            CreateIssue, StartIssueProgress, ResolveIssue, ReopenIssue,
        )
        with self.assert_started():
            self.act(StartIssueProgress)

    def test_start_from_create_start_resolved_closed(self):
        self.arrange(
            CreateIssue, StartIssueProgress, ResolveIssue, CloseIssue,
        )
        with self.assert_reopened():
            self.act(ReopenIssue)

    def test_start_from_create_start_closed(self):
        self.arrange(CreateIssue, StartIssueProgress, CloseIssue)
        with self.assert_reopened():
            self.act(ReopenIssue)

    def test_close_from_create_start_resolved_closed(self):
        self.arrange(
            CreateIssue, StartIssueProgress, ResolveIssue, CloseIssue,
        )
        with self.assert_invalid_transition():
            self.act(CloseIssue)

    def test_stream_isolation(self):
        self.arrange(CreateIssue, CreateIssue(IssueID.new()))
        with self.assert_resolved():
            self.act(ResolveIssue)

    def assert_invalid_transition(self) -> ContextManager:
        return self.assertRaises(InvalidTransition)

    def act(self, command: Union[Type[Command], Command]) -> None:
        command = command(self.issue_id) if isclass(command) else command
        self.handler(command)

    def arrange(self, *commands: Union[Type[Command], Command]) -> None:
        for command in commands:
            self.act(command)

    @contextmanager
    def assert_events(self, *expected_events: Type[Event]) -> None:
        old_version = self.event_store.actual_version(self.issue_id)
        yield
        emitted = self.event_store.get(self.issue_id, after_version=old_version)
        self.assertEqual(expected_events, tuple(type(e) for e in emitted))

    assert_opened = partialmethod(assert_events, IssueOpened)
    assert_started = partialmethod(assert_events, IssueProgressStarted)
    assert_resolved = partialmethod(assert_events, IssueResolved)
    assert_closed = partialmethod(assert_events, IssueClosed)
    assert_stopped = partialmethod(assert_events, IssueProgressStopped)
    assert_reopened = partialmethod(assert_events, IssueReopened)


class AggregateRootTest(TestCase, ExperimentsTestBase):
    def setUp(self) -> None:
        self.event_store = EventStore()
        self.handler = aggregate_root.CommandHandler(self.event_store)
        self.issue_id = IssueID.new()


class ExposedQueriesTest(TestCase, ExperimentsTestBase):
    def setUp(self) -> None:
        self.event_store = EventStore()
        self.handler = exposed_queries.CommandHandler(self.event_store)
        self.issue_id = IssueID.new()


@expectedFailure
class ExposedStateTest(TestCase, ExperimentsTestBase):
    def setUp(self) -> None:
        self.event_store = EventStore()
        self.handler = extracted_state.CommandHandler(self.event_store)
        self.issue_id = IssueID.new()
