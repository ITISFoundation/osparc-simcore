from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_repos import transaction_context

from .dag import reverse_subdag
from .models import DagTemplate, DbDesiredState, DbDirection, DbRunKind, RunId
from .repository import ServicesSchedulerRepository
from .templates import get_apply_template, get_teardown_template


class ServicesSchedulerEngine:
    """High-level orchestration API for the dynamic services scheduler.

    This class coordinates multiple repository calls into larger, atomic actions
    (e.g. start APPLY/TEARDOWN runs). It is intentionally small: the repository
    remains the single source of truth for persistence, and the worker is
    responsible for actually executing steps.
    """

    def __init__(self, repo: ServicesSchedulerRepository) -> None:
        self._repo = repo

    async def request_apply(self, *, node_id: NodeID, desired_spec: dict) -> str:
        """Request that a node converges to the PRESENT state.

        Intended usage:
        - Called by an API/controller when a user/system requests a dynamic service
          to be started/ensured.
        - Creates a new APPLY run, marks it active on the node, and materializes the
          DO-direction DAG into step rows.

        Important semantics:
        - Runs are persisted in Postgres; execution happens asynchronously via workers
          that claim runnable steps.
        - This method is transactional: node lock + desired update + run creation + DAG
          materialization happen atomically.

        Returns:
            The created `run_id`.
        """
        async with transaction_context(self._repo.engine) as conn:
            await self._repo.lock_node(node_id, connection=conn)

            generation = await self._repo.set_node_desired(
                node_id=node_id,
                desired_state=DbDesiredState.PRESENT,
                desired_spec=desired_spec,
                connection=conn,
            )

            run_id = await self._repo.create_run(
                node_id=node_id,
                generation=generation,
                kind=DbRunKind.APPLY,
                connection=conn,
            )
            await self._repo.set_active_run(node_id=node_id, run_id=run_id, connection=conn)

            template = get_apply_template()
            await self._repo.insert_steps(
                run_id=run_id,
                direction=DbDirection.DO,
                template=template,
                connection=conn,
            )
            await self._repo.insert_deps(
                run_id=run_id,
                direction=DbDirection.DO,
                template=template,
                connection=conn,
            )

        return run_id

    async def request_teardown(self, *, node_id: NodeID, reason: str | None = None) -> str:
        """Request that a node converges to the ABSENT state (teardown).

        Intended usage:
        - Called by an API/controller when a node must be removed/stopped.
        - Creates a new TEARDOWN run, marks it active on the node, and materializes the
          UNDO-direction DAG.

        Notes:
        - `reason` is currently not persisted; it's accepted so higher layers can provide
          context (future: store it on the run for audit/UI).

        Returns:
            The created `run_id`.
        """
        _ = reason

        async with transaction_context(self._repo.engine) as conn:
            await self._repo.lock_node(node_id, connection=conn)

            generation = await self._repo.set_node_desired(
                node_id=node_id,
                desired_state=DbDesiredState.ABSENT,
                desired_spec={},
                connection=conn,
            )

            run_id = await self._repo.create_run(
                node_id=node_id,
                generation=generation,
                kind=DbRunKind.TEARDOWN,
                connection=conn,
            )
            await self._repo.set_active_run(node_id=node_id, run_id=run_id, connection=conn)

            template = get_teardown_template()
            await self._repo.insert_steps(
                run_id=run_id,
                direction=DbDirection.UNDO,
                template=template,
                connection=conn,
            )
            await self._repo.insert_deps(
                run_id=run_id,
                direction=DbDirection.UNDO,
                template=template,
                connection=conn,
            )

        return run_id

    async def request_cancel(self, *, run_id: RunId) -> None:
        """Cooperatively request cancellation of a run.

        Intended usage:
        - Called by an API/controller when the user asks to stop an APPLY.

        Semantics:
        - This sets the run state to `CANCEL_REQUESTED`.
        - Workers/engine should observe this and stop making further DO progress.
          (How to react is policy; TEARDOWN is typically treated as non-cancellable.)
        """
        await self._repo.mark_run_cancel_requested(run_id=run_id)

    async def build_undo_subdag(self, *, do_template: DagTemplate, undo_nodes: set[str]) -> DagTemplate:
        """Build an UNDO DAG (subgraph) from a DO DAG.

        Intended usage:
        - When an APPLY run needs compensation, callers can choose a subset of DO steps
          that must be undone and derive an UNDO DAG for them.
        - The returned template can be materialized with
          `repo.insert_steps(..., direction=DbDirection.UNDO, ...)` and
          `repo.insert_deps(..., direction=DbDirection.UNDO, ...)`.

        Important:
        - This is a pure transformation; it does not touch the DB.
        """
        return reverse_subdag(do_template, nodes_subset=undo_nodes, workflow_id=f"{do_template.workflow_id}_undo")
