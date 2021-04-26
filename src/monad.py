from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial, wraps
from typing import (
    Callable,
    Iterator, List,
    NamedTuple,
    Optional,
    Set,
    Type,
    Union,
)

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
from project_management.eventsourcing import TEvent


class Issue(NamedTuple):
    id: IssueID
    state: Optional[State]
    version: int
    pending: List[Event]


class Failure:
    def __eq__(self, other: Failure) -> bool:
        return isinstance(other, Failure)


IssueMonad = Union[Failure, Issue]


def apply(event: Event, issue: Issue) -> Issue:
    state = None
    event_type = type(event)
    if event_type == IssueOpened:
        state = State.OPEN
    elif event_type == IssueProgressStarted:
        state = State.IN_PROGRESS
    elif event_type == IssueProgressStopped:
        state = State.OPEN
    elif event_type == IssueReopened:
        state = State.REOPENED
    elif event_type == IssueResolved:
        state = State.RESOLVED
    elif event_type == IssueClosed:
        state = State.CLOSED
    return Issue(issue.id, state, event.originator_version, issue.pending)


def trigger_event(event_class: Type[TEvent], issue: Issue) -> Issue:
    event = event_class(
        originator_id=issue.id,
        originator_version=issue.version + 1,
        timestamp=datetime.now(tz=timezone.utc),
    )
    issue.pending.append(event)
    return apply(event, issue)


trigger_opened = partial(trigger_event, IssueOpened)
trigger_started = partial(trigger_event, IssueProgressStarted)
trigger_stopped = partial(trigger_event, IssueProgressStopped)
trigger_closed = partial(trigger_event, IssueClosed)
trigger_reopened = partial(trigger_event, IssueReopened)
trigger_resolved = partial(trigger_event, IssueResolved)


MonadFunction = Callable[[IssueMonad], IssueMonad]


def bind(func: MonadFunction) -> MonadFunction:
    valid: Set[State] = set()

    @wraps(func)
    def operation(monad: IssueMonad) -> IssueMonad:
        is_failure = monad == Failure() or monad.state not in valid
        return Failure() if is_failure else func(monad)

    def to_state(state: State) -> MonadFunction:
        valid.add(state)
        return operation
    operation.to_state = to_state

    return operation


create = bind(trigger_opened).to_state(None)
start = bind(trigger_started).to_state(State.OPEN).to_state(State.REOPENED)
stop = bind(trigger_stopped).to_state(State.IN_PROGRESS)
close = (
    bind(trigger_closed)
    .to_state(State.OPEN)
    .to_state(State.IN_PROGRESS)
    .to_state(State.REOPENED)
    .to_state(State.RESOLVED)
)
reopen = bind(trigger_reopened).to_state(State.CLOSED).to_state(State.RESOLVED)
resolve = (
    bind(trigger_resolved)
    .to_state(State.OPEN)
    .to_state(State.REOPENED)
    .to_state(State.IN_PROGRESS)
)


class CommandHandler(Handler):
    def __call__(self, cmd: Command) -> None:
        with self.aggregate(cmd.id) as issue:
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

            if issue == Failure():
                raise InvalidTransition(cmd)

    def get_issue(self, issue_id: IssueID) -> Issue:
        issue = Issue(issue_id, None, 0, [])
        for event in self._event_store.get(issue_id):
            issue = apply(event, issue)
        return issue

    @contextmanager
    def aggregate(self, issue_id: IssueID) -> Iterator[Issue]:
        pending = []
        issue = Issue(issue_id, None, 0, pending)
        for event in self._event_store.get(issue_id):
            issue = apply(event, issue)
        yield issue
        self._event_store.put(*pending)
