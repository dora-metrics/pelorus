# override's attrs.NOTHING's type in a way that's nicer for type checking.
import enum
from typing import Callable, Generic, TypeVar, Union

class _NothingType(enum.Enum):
    NOTHING = enum.auto()

NOTHING = _NothingType.NOTHING

DefaultType = TypeVar("DefaultType")

class Factory(Generic[DefaultType]):
    def __init__(
        self,
        factory: Callable[[], DefaultType],
        takes_self=False,
    ): ...
    factory: Callable[[], DefaultType]
    takes_self: bool
