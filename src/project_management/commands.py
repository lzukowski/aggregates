from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .eventsourcing import EventStore
from .issue import IssueID


@dataclass
class CreateIssue:
    id: IssueID


@dataclass
class ResolveIssue:
    id: IssueID


@dataclass
class CloseIssue:
    id: IssueID


@dataclass
class ReopenIssue:
    id: IssueID


@dataclass
class StartIssueProgress:
    id: IssueID


@dataclass
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
