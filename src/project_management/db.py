import sqlalchemy.orm
from event_sourcery_sqlalchemy.models import configure_models


@sqlalchemy.orm.as_declarative()
class Base:
    pass


configure_models(Base)
engine = sqlalchemy.create_engine("sqlite:///")
Base.metadata.create_all(bind=engine)
