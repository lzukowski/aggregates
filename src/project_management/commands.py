from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .eventsourcing import EventStore
from .issue import IssueID


@dataclass(frozen=True)
class CreateIssue:
    id: IssueID


@dataclass(frozen=True)
class ResolveIssue:
    id: IssueID


@dataclass(frozen=True)
class CloseIssue:
    id: IssueID


@dataclass(frozen=True)
class ReopenIssue:
    id: IssueID


@dataclass(frozen=True)
class StartIssueProgress:
    id: IssueID


@dataclass(frozen=True)
class StopIssueProgress:
    id: IssueID


Command = Union[
    CreateIssue,
    ResolveIssue,
    CloseIssue,
    ReopenIssue,
    StartIssueProgress,
    StopIssueProgress,
]


class Handler:
    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    def __call__(self, cmd: Command) -> None:
        ...
