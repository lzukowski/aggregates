from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID


@dataclass
class Event:
    originator_id: UUID
    originator_version: int
    timestamp: datetime


TEvent = TypeVar("TEvent", bound=Event)


class Aggregate:
    def __init__(self, originator_id: UUID) -> None:
        self._id = originator_id
        self._version = 0
        self._pending_events: List[Event] = []

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def version(self) -> int:
        return self._version

    @property
    def pending_events(self) -> List[Event]:
        return self._pending_events

    def apply(self, event: TEvent) -> None:
        self._version = event.originator_version

    def trigger_event(self, event_class: Type[TEvent], **kwargs: Any) -> None:
        new_event = event_class(
            originator_id=self.id,
            originator_version=self.version + 1,
            timestamp=datetime.now(tz=timezone.utc),
            **kwargs,
        )

        self.apply(new_event)
        self._pending_events.append(new_event)


TAggregate = TypeVar("TAggregate", bound=Aggregate)


class EventStore(Generic[TEvent]):
    def __init__(self) -> None:
        self._in_memory: Dict[UUID, List[TEvent]] = defaultdict(list)

    def put(self, events: List[TEvent]) -> None:
        for event in events:
            self._in_memory[event.originator_id].append(event)

    def get(
            self,
            originator_id: UUID,
            after_version: Optional[int] = None,
            to_version: Optional[int] = None,
            desc: bool = False,
            limit: Optional[int] = None,
    ) -> List[TEvent]:
        def event_is_valid(event: TEvent) -> bool:
            version = event.originator_version
            if after_version and not (version > after_version):
                return False
            if to_version and not (version <= to_version):
                return False
            return True

        valid_events = filter(event_is_valid, self._in_memory[originator_id])
        return sorted(
            valid_events, reverse=desc, key=lambda e: e.originator_version,
        )[:limit]


class Repository(Generic[TAggregate]):
    def __init__(self, event_store: EventStore[TEvent]) -> None:
        self.event_store = event_store

    def get(self, aggregate: TAggregate, version: Optional[int] = None) -> None:
        events = self.event_store.get(
            originator_id=aggregate.id, to_version=version,
        )
        for event in events:
            aggregate.apply(event)

    def save(self, aggregate: TAggregate) -> None:
        self.event_store.put(aggregate.pending_events)