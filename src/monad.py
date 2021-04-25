from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial, singledispatch
from typing import List, Type

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
from project_management.eventsourcing import TEvent


@dataclass
class Issue:
    id: IssueID
    version: int = 0
    changes: List[Event] = field(default_factory=list)


class Invalid(Issue): pass
class Init(Issue): pass
class Open(Issue): pass
class Closed(Issue): pass
class InProgress(Issue): pass
class Reopened(Issue): pass
class Resolved(Issue): pass


def apply(event: Event, issue: Issue) -> Issue:
    event_type = type(event)
    issue_type = Init
    if event_type == IssueOpened:
        issue_type = Open
    elif event_type == IssueProgressStarted:
        issue_type = InProgress
    elif event_type == IssueProgressStopped:
        issue_type = Open
    elif event_type == IssueReopened:
        issue_type = Reopened
    elif event_type == IssueResolved:
        issue_type = Resolved
    elif event_type == IssueClosed:
        issue_type = Closed
    return issue_type(
        id=issue.id,
        changes=issue.changes,
        version=event.originator_version,
    )


def trigger_event(event_class: Type[TEvent], issue: Issue) -> Issue:
    event = event_class(
        originator_id=issue.id,
        originator_version=issue.version + 1,
        timestamp=datetime.now(tz=timezone.utc),
    )
    issue.changes += [event]
    return apply(event, issue)


def invalid_transition(issue: Issue) -> Issue:
    return Invalid(issue.id, version=-1)


create = singledispatch(invalid_transition)
create.register(Init)(partial(trigger_event, IssueOpened))

start = singledispatch(invalid_transition)
process_start = partial(trigger_event, IssueProgressStarted)
start.register(Open, process_start)
start.register(Reopened, process_start)

stop = singledispatch(invalid_transition)
stop.register(InProgress, partial(trigger_event, IssueProgressStopped))

close = singledispatch(invalid_transition)
process_close = partial(trigger_event, IssueClosed)
close.register(Open, process_close)
close.register(InProgress, process_close)
close.register(Reopened, process_close)
close.register(Resolved, process_close)

reopen = singledispatch(invalid_transition)
process_reopen = partial(trigger_event, IssueReopened)
reopen.register(Closed, process_reopen)
reopen.register(Resolved, process_reopen)

resolve = singledispatch(invalid_transition)
process_resolve = partial(trigger_event, IssueResolved)
resolve.register(Open, process_resolve)
resolve.register(Reopened, process_resolve)
resolve.register(InProgress, process_resolve)


def process(issue: Issue, cmd: Command) -> Issue:
    command_type = type(cmd)
    if command_type == CreateIssue:
        issue = create(issue)
    elif command_type == ResolveIssue:
        issue = resolve(issue)
    elif command_type == CloseIssue:
        issue = close(issue)
    elif command_type == ReopenIssue:
        issue = reopen(issue)
    elif command_type == StartIssueProgress:
        issue = start(issue)
    elif command_type == StopIssueProgress:
        issue = stop(issue)
    return issue


class CommandHandler(Handler):
    def __call__(self, cmd: Command) -> None:
        issue = self.get_issue(cmd.id)
        issue = process(issue, cmd)
        if isinstance(issue, Invalid):
            raise InvalidTransition(cmd)
        self._event_store.put(*issue.changes)

    def get_issue(self, issue_id: IssueID) -> Issue:
        issue = Init(issue_id)
        for event in self._event_store.get(issue_id):
            issue = apply(event, issue)
        return issue
