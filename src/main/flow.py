from enum import Enum

class Flow(Enum):
    NONE = "none"
    REBUILD = "rebuild"
    PATCH_NEW = "patch_new"
    PATCH_NEW_REMOVE_ONLY = "patch_new_remove_only"

    @property
    def redoing(self) -> bool:
        return self is not Flow.NONE

    @property
    def patch_new(self) -> bool:
        return self in (Flow.PATCH_NEW, Flow.PATCH_NEW_REMOVE_ONLY)

    @property
    def only_remove(self) -> bool:
        return self is Flow.PATCH_NEW_REMOVE_ONLY