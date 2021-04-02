from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid1


class IssueID(UUID):
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
