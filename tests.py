from contextlib import contextmanager
from functools import partialmethod, lru_cache
from inspect import isclass
from typing import Any, Callable, ContextManager, Protocol, Type, Union
from unittest import TestCase

import sqlalchemy.orm
from event_sourcery import get_event_store, Event, EventStore

import aggregate_root
import duck_typing
import exposed_queries
import extracted_state
import functional
import polymorphic
import repository
from project_management import (
    db,
    Command,
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


class ExperimentsTestBase(Protocol):
    handler_cls: Type[Handler]
    assertRaises: Callable[[Type[Exception]], ContextManager] = NotImplemented
    assertEqual: Callable[[Any, Any], None] = NotImplemented

    @property
    @lru_cache
    def event_store(self) -> EventStore:
        return get_event_store(sqlalchemy.orm.Session(bind=db.engine))

    @property
    def handler(self) -> Handler:
        return self.handler_cls(self.event_store)

    @property
    @lru_cache
    def issue_id(self) -> IssueID:
        return IssueID.new()

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
        old_events = self.event_store.load_stream(self.issue_id)
        yield
        start = old_events[-1].version + 1 if old_events else 0
        emitted = self.event_store.load_stream(self.issue_id, start=start)
        self.assertEqual(expected_events, tuple(type(e) for e in emitted))

    assert_opened = partialmethod(assert_events, IssueOpened)
    assert_started = partialmethod(assert_events, IssueProgressStarted)
    assert_resolved = partialmethod(assert_events, IssueResolved)
    assert_closed = partialmethod(assert_events, IssueClosed)
    assert_stopped = partialmethod(assert_events, IssueProgressStopped)
    assert_reopened = partialmethod(assert_events, IssueReopened)


class AggregateRootTest(TestCase, ExperimentsTestBase):
    handler_cls = aggregate_root.CommandHandler


class ExposedQueriesTest(TestCase, ExperimentsTestBase):
    handler_cls = exposed_queries.CommandHandler


class ExposedStateTest(TestCase, ExperimentsTestBase):
    handler_cls = extracted_state.CommandHandler


class FunctionalAggregateTest(TestCase, ExperimentsTestBase):
    handler_cls = functional.CommandHandler


class PolymorphicTest(TestCase, ExperimentsTestBase):
    handler_cls = polymorphic.CommandHandler


class DuckTypingTest(TestCase, ExperimentsTestBase):
    handler_cls = duck_typing.CommandHandler


class RepositoryBasedAggregateTest(TestCase, ExperimentsTestBase):
    handler_cls = repository.CommandHandler
