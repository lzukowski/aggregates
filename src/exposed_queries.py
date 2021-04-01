from project_management import Command, Handler
from project_management.eventsourcing import EventStore


class CommandHandler(Handler):
    def __init__(self, event_store: EventStore) -> None:
        super().__init__(event_store)

    def __call__(self, cmd: Command) -> None:
        raise NotImplementedError
