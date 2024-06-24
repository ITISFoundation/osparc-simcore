from ..db.repositories.services import ServicesRepository


async def list_services_with_history(
    services_repo: ServicesRepository,
    limit: int | None = None,
    offset: int | None = None,
):
    # TODO: add access-rights needed

    # user_id
    items = await services_repo.list_services_with_history(limit=limit, offset=offset)
    # TODO: add more info on latest version!
