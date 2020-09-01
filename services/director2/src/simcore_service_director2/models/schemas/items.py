from ..domains.items import Item, ItemBase


class ItemCreate(ItemBase):
    # Used to create and replace
    pass


class ItemUpdate(ItemBase):
    # As create but NO required values!
    pass


class ItemOverview(ItemBase):
    # short version -> add redirections to details?
    pass


class ItemDetailed(Item):
    # long version
    pass
