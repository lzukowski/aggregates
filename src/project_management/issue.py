from __future__ import annotations

from uuid import UUID, uuid1


class IssueID(UUID):
    @classmethod
    def new(cls) -> IssueID:
        return IssueID(str(uuid1()))


class InvalidTransition(Exception):
    pass
