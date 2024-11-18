""" Demo script: retrieves results of all user's meta-study using osparc_webapi's client

"""

from collections import defaultdict
from uuid import UUID

import httpx
import pandas as pd
from osparc_webapi import (
    CheckPoint,
    Envelope,
    ProjectIterationResultItem,
    ProjectRepo,
    iter_checkpoints,
    iter_items,
    iter_project_iteration,
    iter_repos,
    query_if_invalid_config,
    setup_client,
)


def print_checkpoints(client: httpx.Client):

    repos: list[ProjectRepo] = list(iter_repos(client))
    project_id = repos[0].project_uuid

    for checkpoint in iter_checkpoints(client, project_id):
        print(checkpoint.model_dump_json(exclude_unset=True, indent=1))


def print_iterations(client: httpx.Client, project_id: UUID, checkpoint: CheckPoint):
    # print-iterations
    print("Metaproject at", f"{project_id=}", f"{checkpoint=}")
    for project_iteration in iter_project_iteration(client, project_id, checkpoint.id):
        print(project_iteration.model_dump_json(exclude_unset=True, indent=1))


def select_project_head(client: httpx.Client, project_id: UUID):
    # get head
    r = client.get(f"/repos/projects/{project_id}/checkpoints/HEAD")
    head = Envelope[CheckPoint].model_validate(r.json()).data
    assert head  # nosec

    return project_id, head


def fetch_data(client: httpx.Client, project_id: UUID, checkpoint: CheckPoint):
    #  results
    data = defaultdict(list)
    index = []

    for row in iter_items(
        client,
        f"/projects/{project_id}/checkpoint/{checkpoint.id}/iterations/-/results",
        ProjectIterationResultItem,
    ):
        # projects/*/checkpoints/*/iterations/*
        print(
            row.iteration_index,
            "->",
            f"/projects/{project_id}/checkpoints/{checkpoint.id}/iterations/{row.iteration_index}",
        )

        index.append(row.iteration_index)

        data["progress"].append(
            sum(row.results.progress.values()) / len(row.results.progress)
        )

        for node_id, label in row.results.labels.items():
            for port_name, value in row.results.values[node_id].items():
                data[f"{label}[{port_name}]"].append(value)

    df = pd.DataFrame(data, index=pd.Series(index))
    # TODO: add metadata?
    return df


def process_data(df: pd.DataFrame):
    print(end="\n" * 2)
    print(df.head())
    print(end="\n" * 2)
    print(df.describe())
    # print(df.sort_values(by="f2(X)"))


def main():
    query_if_invalid_config()

    with setup_client() as client:
        print_checkpoints(client)

        # find a meta-project
        first_repo = next(iter_repos(client))
        project_id = first_repo.project_uuid

        project_id, head = select_project_head(client, project_id)
        print_iterations(client, project_id, head)

        df = fetch_data(client, project_id, head)

    df.to_csv(f"projects_{project_id}_checkpoint_{head.id}.ignore.csv")
    df.to_markdown(f"projects_{project_id}_checkpoint_{head.id}.ignore.md")
    process_data(df)


if __name__ == "__main__":
    main()
