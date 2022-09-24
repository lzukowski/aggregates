from __future__ import annotations

from enum import Enum
from uuid import uuid1

from event_sourcery.types.stream_id import StreamId


class IssueID(StreamId):
    @classmethod
    def new(cls) -> IssueID:
        return IssueID(str(uuid1()))


class InvalidTransition(Exception):
    pass


class State(Enum):
    OPEN = 'OPEN'
    CLOSED = 'CLOSED'
    IN_PROGRESS = 'IN_PROGRESS'
    REOPENED = 'REOPENED'
    RESOLVED = 'RESOLVED'
