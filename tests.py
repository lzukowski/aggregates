from contextlib import contextmanager
from functools import partialmethod
from inspect import isclass
from typing import ContextManager, Type, Union

from pytest import fixture, raises

from app import Application
from project_management import InvalidTransition, IssueID
from project_management.commands import (
    CloseIssue,
    Command,
    CreateIssue,
    Handler,
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


def pytest_generate_tests(metafunc):
    handlers = []
    names = [h.__module__ for h in handlers]
    metafunc.parametrize('handler_cls', handlers, ids=names)


class TestScenarios:
    @fixture(autouse=True)
    def setup(self, handler_cls: Type[Handler]) -> None:
        application = Application(uri='sqlite:///:memory:')
        self.event_store = application.event_store
        self.issue_id = IssueID.new()
        self.handler = handler_cls(self.event_store)

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

    @contextmanager
    def assert_invalid_transition(self) -> ContextManager:
        with raises(InvalidTransition):
            yield

    def act(self, command: Union[Type[Command], Command]) -> None:
        command = command(self.issue_id) if isclass(command) else command
        self.handler(command)

    def arrange(self, *commands: Union[Type[Command], Command]) -> None:
        for command in commands:
            self.act(command)

    @contextmanager
    def assert_events(self, *expected_events: Type[Event]) -> None:
        scope = self.event_store.list_events(originator_id=self.issue_id)
        before = scope[-1].originator_version if scope else None
        yield
        actual_events = self.event_store.list_events(
            originator_id=self.issue_id, gt=before,
        )
        assert expected_events == tuple(type(e) for e in actual_events)

    assert_opened = partialmethod(assert_events, IssueOpened)
    assert_started = partialmethod(assert_events, IssueProgressStarted)
    assert_resolved = partialmethod(assert_events, IssueResolved)
    assert_closed = partialmethod(assert_events, IssueClosed)
    assert_stopped = partialmethod(assert_events, IssueProgressStopped)
    assert_reopened = partialmethod(assert_events, IssueReopened)
