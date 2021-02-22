from typing import Text

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_utils import UUIDType

DBBase = declarative_base()


class IssueRecord(DBBase):
    __tablename__ = 'issue_events'
    __table_args__ = sa.Index('id', 'sequence_id', 'position', unique=True),

    id = sa.Column(
        sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True,
    )
    sequence_id = sa.Column(UUIDType(), nullable=False)
    position = sa.Column(sa.BigInteger(), nullable=False)
    topic = sa.Column(sa.String(255))
    state = sa.Column(sa.Text())

    def __repr__(self) -> Text:
        return (
            f'<{self.__class__.__name__} '
            f'id={self.id} '
            f'sequence_id={self.sequence_id} '
            f'position={self.position} '
            f'topic={self.topic} '
            f'state={self.state}'
            f'>'
        )
