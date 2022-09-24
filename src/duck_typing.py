from __future__ import annotations

from datetime import datetime, timezone
from functools import singledispatchmethod
from inspect import ismethod
from typing import Text, Tuple, Type, Union

from event_sourcery import Event

from project_management import (
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


class Issue:
    def open(self) -> Open:
        return Open()


class Open:
    def start(self) -> InProgress:
        return InProgress()

    def resolve(self) -> Resolved:
        return Resolved()

    def close(self) -> Closed:
        return Closed()


class InProgress:
    def stop(self) -> Open:
        return Open()

    def resolve(self) -> Resolved:
        return Resolved()

    def close(self) -> Closed:
        return Closed()


class Resolved:
    def close(self) -> Closed:
        return Closed()

    def reopen(self) -> Open:
        return Open()


class Closed:
    def reopen(self) -> Open:
        return Open()


class CommandHandler(Handler):
    def __call__(self, cmd: Command) -> None:
        issue, version = self.get_issue(cmd.id)
        event = self.process(cmd, issue)(
            originator_id=cmd.id,
            originator_version=version + 1,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self._event_store.publish(cmd.id, [event], expected_version=version + 1)

    @singledispatchmethod
    def process(self, cmd: Command, issue) -> Type[Event]:
        ...

    @process.register
    def create(self, _: CreateIssue, issue) -> Type[Event]:
        self.raise_invalid_unless_respond_to(issue, 'open')
        issue.open()
        return IssueOpened

    @process.register
    def start(self, _: StartIssueProgress, issue) -> Type[Event]:
        self.raise_invalid_unless_respond_to(issue, 'start')
        issue.start()
        return IssueProgressStarted

    @process.register
    def stop(self, _: StopIssueProgress, issue) -> Type[Event]:
        self.raise_invalid_unless_respond_to(issue, 'stop')
        issue.stop()
        return IssueProgressStopped

    @process.register
    def close(self, _: CloseIssue, issue) -> Type[Event]:
        self.raise_invalid_unless_respond_to(issue, 'close')
        issue.close()
        return IssueClosed

    @process.register
    def reopen(self, _: ReopenIssue, issue) -> Type[Event]:
        self.raise_invalid_unless_respond_to(issue, 'reopen')
        issue.reopen()
        return IssueReopened

    @process.register
    def resolve(self, _: ResolveIssue, issue) -> Type[Event]:
        self.raise_invalid_unless_respond_to(issue, 'resolve')
        issue.resolve()
        return IssueResolved

    def raise_invalid_unless_respond_to(self, issue, method: Text) -> None:
        if not ismethod(getattr(issue, method, None)):
            raise InvalidTransition(method)

    def get_issue(
            self, issue_id: IssueID
    ) -> Tuple[Union[Issue, Open, InProgress, Resolved, Closed], int]:
        issue = Issue()
        version = 0
        for version, event in enumerate(self._event_store.iter(issue_id), 1):
            event_type = type(event)
            if event_type == IssueOpened:
                issue = issue.open()
            elif event_type == IssueProgressStarted:
                issue = issue.start()
            elif event_type == IssueProgressStopped:
                issue = issue.stop()
            elif event_type == IssueReopened:
                issue = issue.reopen()
            elif event_type == IssueResolved:
                issue = issue.resolve()
            elif event_type == IssueClosed:
                issue = issue.close()
        return issue, version
