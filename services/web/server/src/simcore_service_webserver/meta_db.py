import logging
from types import SimpleNamespace
from typing import List, Optional

from aiopg.sa.result import RowProxy
from models_library.projects import ProjectIDStr

from .version_control_changes import compute_workbench_checksum
from .version_control_db import VersionControlRepository
from .version_control_errors import UserUndefined
from .version_control_models import CommitID, ProjectDict, TagProxy
from .version_control_tags import (
    compose_wcopy_project_id,
    compose_wcopy_project_tag_name,
)

log = logging.getLogger(__name__)


class VersionControlForMetaModeling(VersionControlRepository):

    # TODO: eval inheritace vs composition?

    async def get_wcopy_project_id(
        self, repo_id: int, commit_id: Optional[int] = None
    ) -> ProjectIDStr:
        async with self.engine.acquire() as conn:
            if commit_id is None:
                commit = await self._get_HEAD_commit(repo_id, conn)
                assert commit  # nosec
                commit_id = commit.id
                assert commit_id

            return await self._fetch_wcopy_project_id(repo_id, commit_id, conn)

    async def get_wcopy_project(self, repo_id: int, commit_id: int) -> ProjectDict:
        async with self.engine.acquire() as conn:
            project_id = await self._fetch_wcopy_project_id(repo_id, commit_id, conn)
            project = await self.ProjectsOrm(conn).set_filter(uuid=project_id).fetch()
            assert project  # nosec
            return dict(project.items())

    async def get_project(self, project_id: ProjectIDStr) -> ProjectDict:
        async with self.engine.acquire() as conn:
            if self.user_id is None:
                # TODO: add message
                raise UserUndefined
            project = (
                await self.ProjectsOrm(conn)
                .set_filter(uuid=str(project_id), prj_owner=self.user_id)
                .fetch(
                    [
                        "type",
                        "uuid",
                        "name",
                        "description",
                        "thumbnail",
                        "prj_owner",
                        "access_rights",
                        "workbench",
                        "ui",
                        "classifiers",
                        "dev",
                        "quality",
                        "published",
                        "hidden",
                    ]
                )
            )
            assert project  # nosec
            return dict(project.items())

    async def force_branch_and_wcopy(
        self,
        repo_id: int,
        start_commit_id: int,
        project: ProjectDict,
        branch_name: str,
        tag_name: str,
        tag_message: str,
    ) -> CommitID:
        """Forces a new branch with an explicit working copy 'project' on 'start_commit_id'

        For internal operation
        """
        IS_INTERNAL_OPERATION = True

        async with self.engine.acquire() as conn:
            # existance check prevents errors later
            if tag := await self.TagsOrm(conn).set_filter(name=tag_name).fetch():
                return tag.commit_id

            # get wcopy for start_commit_id and update with 'project'
            repo = (
                await self.ReposOrm(conn).set_filter(id=repo_id).fetch("project_uuid")
            )
            assert repo  # nosec

            async with conn.begin():

                # take snapshot of forced project
                snapshot_checksum = compute_workbench_checksum(project["workbench"])

                # TODO: check snapshot in parent_commit_id != snapshot_checksum
                await self._upsert_snapshot(
                    snapshot_checksum, SimpleNamespace(**project), conn
                )

                # commit new snapshot in history
                commit_id = await self.CommitsOrm(conn).insert(
                    repo_id=repo_id,
                    parent_commit_id=start_commit_id,
                    message=tag_message,
                    snapshot_checksum=snapshot_checksum,
                )
                assert commit_id  # nosec
                assert isinstance(commit_id, int)  # nosec

                # creates unique identifier for variant
                project["uuid"] = compose_wcopy_project_id(repo.project_uuid, commit_id)

                # FIXME: File-picker takes project uuid. replace!
                project["hidden"] = True

                # creates runnable version in project
                # raises ?? if same uuid
                await self.ProjectsOrm(conn).insert(**project)

                # create branch and set head to last commit_id
                branch = await self.BranchesOrm(conn).insert(
                    returning_cols="id head_commit_id",
                    repo_id=repo_id,
                    head_commit_id=commit_id,
                    name=branch_name,
                )
                assert isinstance(branch, RowProxy)  # nosec

                for tag in [tag_name, compose_wcopy_project_tag_name(project["uuid"])]:
                    await self.TagsOrm(conn).insert(
                        repo_id=repo_id,
                        commit_id=commit_id,
                        name=tag,
                        message=tag_message if tag == tag_name else None,
                        hidden=IS_INTERNAL_OPERATION,
                    )

                return branch.head_commit_id

    async def get_children_tags(
        self, repo_id: int, commit_id: int
    ) -> List[List[TagProxy]]:
        async with self.engine.acquire() as conn:
            commits = (
                await self.CommitsOrm(conn)
                .set_filter(repo_id=repo_id, parent_commit_id=commit_id)
                .fetch_all(returning_cols="id")
            )
            # TODO: single query for this loop
            tags = []
            for commit in commits:
                tags_in_commit = (
                    await self.TagsOrm(conn).set_filter(commit_id=commit.id).fetch_all()
                )
                tags.append(tags_in_commit)
            return tags
