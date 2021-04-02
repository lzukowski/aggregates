from .eventsourcing import Event


class IssueOpened(Event):
    pass


class IssueResolved(Event):
    pass


class IssueClosed(Event):
    pass


class IssueReopened(Event):
    pass


class IssueProgressStarted(Event):
    pass


class IssueProgressStopped(Event):
    pass
