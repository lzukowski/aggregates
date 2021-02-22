from eventsourcing.application.sqlalchemy import SQLAlchemyApplication

from project_management import IssueRecord


class Application(SQLAlchemyApplication):
    tracking_record_class = IssueRecord
