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
from app.dal.repository.seed_examples import (
    EXAMPLE_PACKAGE, EXAMPLE_PACKAGE_KEY, EXAMPLE_WORKFLOW_KEY,
    example_workflow,
)
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
            # Sent as one script: splitting on ";" would cut inside comments
            # and string literals, which is not something SQL text guarantees.
            connection.execute(SCHEMA)
            connection.execute(
                "DELETE FROM conversations WHERE expires_at <= NOW()"
            )
            connection.commit()
        self._seed_agent_content(SEED_CONTENT)
        self._seed_examples()

    def _seed_examples(self) -> None:
        """Create the worked example tool and workflow, once.

        Keyed on existence rather than on a flag, matching how Skills are
        seeded: an FDE who deletes the examples does not get them back on the
        next restart, which is what makes deleting them a real choice. Each is
        checked independently, so deleting only the workflow leaves the tool
        alone.
        """
        if not self._package_key_exists(EXAMPLE_PACKAGE_KEY):
            self.create_package(dict(EXAMPLE_PACKAGE))
        if self._workflow_key_exists(EXAMPLE_WORKFLOW_KEY):
            return
        # The workflow's step pins a tool row, so it can only be built against
        # a tool that exists. If the FDE deleted the example tool but kept the
        # workflow deleted too, there is nothing to point at and the example
        # workflow is simply skipped.
        tools = self._all(
            "SELECT id FROM summary_packages WHERE package_key=%s",
            (EXAMPLE_PACKAGE_KEY,),
        )
        if tools:
            self.create_workflow(example_workflow(tools[0]["id"]))

    def _package_key_exists(self, package_key: str) -> bool:
        return bool(self._all(
            "SELECT id FROM summary_packages WHERE package_key=%s LIMIT 1",
            (package_key,),
        ))

    def _workflow_key_exists(self, workflow_key: str) -> bool:
        return bool(self._all(
            "SELECT id FROM summary_workflows WHERE workflow_key=%s LIMIT 1",
            (workflow_key,),
        ))
