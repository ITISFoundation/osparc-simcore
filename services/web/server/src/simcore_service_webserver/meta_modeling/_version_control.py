""" Access to the to version_control add-on

"""

import logging
from types import SimpleNamespace

from aiopg.sa.result import RowProxy
from models_library.projects import ProjectIDStr
from models_library.utils.fastapi_encoders import jsonable_encoder

from ..projects.models import ProjectDict
from ..version_control.db import VersionControlRepository
from ..version_control.errors import UserUndefinedError
from ..version_control.models import CommitID, TagProxy
from ..version_control.vc_changes import (
    compute_workbench_checksum,
    eval_workcopy_project_id,
)
from ..version_control.vc_tags import compose_workcopy_project_tag_name

_logger = logging.getLogger(__name__)


class VersionControlForMetaModeling(VersionControlRepository):
    async def get_workcopy_project_id(
        self, repo_id: int, commit_id: int | None = None
    ) -> ProjectIDStr:
        async with self.engine.acquire() as conn:
            if commit_id is None:
                commit = await self._get_HEAD_commit(repo_id, conn)
                assert commit  # nosec
                commit_id = commit.id
                assert commit_id

            return await self._fetch_workcopy_project_id(repo_id, commit_id, conn)

    async def get_workcopy_project(self, repo_id: int, commit_id: int) -> ProjectDict:
        async with self.engine.acquire() as conn:
            project_id = await self._fetch_workcopy_project_id(repo_id, commit_id, conn)
            project = await self.ProjectsOrm(conn).set_filter(uuid=project_id).fetch()
            assert project  # nosec
            return dict(project.items())

    async def get_project(
        self, project_id: ProjectIDStr, *, include: list[str] | None = None
    ) -> ProjectDict:
        async with self.engine.acquire() as conn:
            if self.user_id is None:
                raise UserUndefinedError

            if include is None:
                include = [
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

            project = (
                await self.ProjectsOrm(conn)
                .set_filter(uuid=f"{project_id}", prj_owner=self.user_id)
                .fetch(include)
            )
            assert project  # nosec
            project_as_dict = dict(project.items())

            # -------------
            # NOTE: hack to avoid validation error. Revisit when models_library.utils.pydantic_models_factory is
            # used to create a reliable project's model to validate http API
            if "thumbnail" in project_as_dict:
                project_as_dict["thumbnail"] = project_as_dict["thumbnail"] or ""
            # ---------------
            return project_as_dict

    async def create_workcopy_and_branch_from_commit(
        self,
        repo_id: int,
        start_commit_id: int,
        project: ProjectDict,
        branch_name: str,
        tag_name: str,
        tag_message: str,
    ) -> CommitID:
        """Creates a new branch with an explicit working copy 'project' on 'start_commit_id'"""
        IS_INTERNAL_OPERATION = True

        # NOTE: this avoid having non-compatible types embedded in the dict that
        # make operations with the db to fail
        # SEE https://fastapi.tiangolo.com/tutorial/encoder/
        project = jsonable_encoder(project, sqlalchemy_safe=True)

        commit_id: CommitID

        async with self.engine.acquire() as conn:
            # existance check prevents errors later
            if tag := await self.TagsOrm(conn).set_filter(name=tag_name).fetch():
                commit_id = tag.commit_id
                return commit_id

            # get workcopy for start_commit_id and update with 'project'
            repo = (
                await self.ReposOrm(conn).set_filter(id=repo_id).fetch("project_uuid")
            )
            assert repo  # nosec

            async with conn.begin():
                # take snapshot of forced project
                snapshot_checksum = compute_workbench_checksum(project["workbench"])

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
                project["uuid"] = eval_workcopy_project_id(
                    repo.project_uuid, snapshot_checksum
                )
                project["hidden"] = True

                # creates runnable version in project
                await self.ProjectsOrm(conn).insert(**project)

                # create branch and set head to last commit_id
                branch = await self.BranchesOrm(conn).insert(
                    returning_cols="id head_commit_id",
                    repo_id=repo_id,
                    head_commit_id=commit_id,
                    name=branch_name,
                )
                assert isinstance(branch, RowProxy)  # nosec

                for tag in [
                    tag_name,
                    compose_workcopy_project_tag_name(project["uuid"]),
                ]:
                    await self.TagsOrm(conn).insert(
                        repo_id=repo_id,
                        commit_id=commit_id,
                        name=tag,
                        message=tag_message if tag == tag_name else None,
                        hidden=IS_INTERNAL_OPERATION,
                    )

                commit_id = branch.head_commit_id
                return commit_id

    async def get_children_tags(
        self, repo_id: int, commit_id: int
    ) -> list[list[TagProxy]]:
        async with self.engine.acquire() as conn:
            commits = (
                await self.CommitsOrm(conn)
                .set_filter(repo_id=repo_id, parent_commit_id=commit_id)
                .fetch_all(returning_cols="id")
            )
            tags = []
            for commit in commits:
                tags_in_commit = (
                    await self.TagsOrm(conn).set_filter(commit_id=commit.id).fetch_all()
                )
                tags.append(tags_in_commit)
            return tags
