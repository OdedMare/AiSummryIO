"""Public repository composed from focused persistence modules."""

from app.dal.database.postgres import connect, ensure_schema
from app.dal.repository.base import RepositoryBase
from app.dal.repository.content import ContentRepository
from app.dal.repository.conversations import ConversationRepository
from app.dal.repository.feedback import FeedbackRepository
from app.dal.repository.packages import PackageRepository
from app.dal.repository.runs import RunRepository
from app.dal.repository.schema import SCHEMA
from app.dal.repository.seed_content import SEED_CONTENT
from app.dal.repository.workflows import WorkflowRepository


class Repository(
    RepositoryBase,
    PackageRepository,
    WorkflowRepository,
    ContentRepository,
    ConversationRepository,
    RunRepository,
    FeedbackRepository,
):
    """Stable façade; each parent owns one persistence concern."""

    def initialize(self) -> None:
        ensure_schema(self._store)
        with connect(self._store) as connection:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    connection.execute(statement)
            connection.execute(
                "DELETE FROM conversations WHERE expires_at <= NOW()"
            )
            connection.commit()
        self._seed_agent_content(SEED_CONTENT)
