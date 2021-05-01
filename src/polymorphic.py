from __future__ import annotations

from datetime import datetime, timezone
from functools import singledispatchmethod
from typing import Protocol, Tuple, Type

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


class Issue(Protocol):
    def open(self) -> Issue:
        raise InvalidTransition('create')

    def start(self) -> Issue:
        raise InvalidTransition('start')

    def stop(self) -> Issue:
        raise InvalidTransition('stop')

    def close(self) -> Issue:
        raise InvalidTransition('close')

    def reopen(self) -> Issue:
        raise InvalidTransition('reopen')

    def resolve(self) -> Issue:
        raise InvalidTransition('resolve')


class Init(Issue):
    def open(self) -> Open:
        return Open()


class Open(Issue):
    def start(self) -> InProgress:
        return InProgress()

    def close(self) -> Closed:
        return Closed()

    def resolve(self) -> Resolved:
        return Resolved()


class InProgress(Issue):
    def stop(self) -> Open:
        return Open()

    def close(self) -> Closed:
        return Closed()

    def resolve(self) -> Resolved:
        return Resolved()


class Closed(Issue):
    def reopen(self) -> Open:
        return Open()


class Resolved(Issue):
    def close(self) -> Closed:
        return Closed()

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
        self._event_store.put(event)

    @singledispatchmethod
    def process(self, cmd: Command, issue: Issue) -> Type[Event]:
        ...

    @process.register
    def create(self, _: CreateIssue, issue: Issue) -> Type[Event]:
        issue.open()
        return IssueOpened

    @process.register
    def start(self, _: StartIssueProgress, issue: Issue) -> Type[Event]:
        issue.start()
        return IssueProgressStarted

    @process.register
    def stop(self, _: StopIssueProgress, issue: Issue) -> Type[Event]:
        issue.stop()
        return IssueProgressStopped

    @process.register
    def close(self, _: CloseIssue, issue: Issue) -> Type[Event]:
        issue.close()
        return IssueClosed

    @process.register
    def reopen(self, _: ReopenIssue, issue: Issue) -> Type[Event]:
        issue.reopen()
        return IssueReopened

    @process.register
    def resolve(self, _: ResolveIssue, issue: Issue) -> Type[Event]:
        issue.resolve()
        return IssueResolved

    def get_issue(self, issue_id: IssueID) -> Tuple[Issue, int]:
        issue = Init()
        version = 0
        for event in self._event_store.get(issue_id):
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
            version = event.originator_version
        return issue, version
