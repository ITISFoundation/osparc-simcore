from models_library.users import GroupID, UserID

from .base import BaseRepository


class PaymentsUsersRepo(BaseRepository):
    # NOTE:
    # Currently linked to `users` but expected to be linked to `payments_users`
    # when databases are separated. The latter will be a subset copy of the former.
    #
    async def get_primary_group_id(self, user_id: UserID) -> GroupID:
        raise NotImplementedError

    async def get_billing_address(self, user_id: UserID):
        raise NotImplementedError
