from typing import Any, Generic, Optional, Sequence, TypeVar

import attr


@attr.define
class OwnerRef:
    kind: str
    name: str


@attr.define
class Metadata:
    name: Optional[str] = None
    namespace: Optional[str] = None
    ownerReferences: list[OwnerRef] = attr.Factory(list)
    labels: dict[str, str] = attr.Factory(dict)
    creationTimestamp: Any = None


@attr.define
class Container:
    image: str


@attr.define
class PodSpec:
    containers: list[Container]


@attr.define
class Pod:
    metadata: Metadata
    spec: PodSpec


@attr.define
class Replicator:
    "Represents a ReplicationController or a ReplicaSet"
    kind: str
    metadata: Metadata

    def ref(self) -> OwnerRef:
        return OwnerRef(kind=self.kind, name=self.metadata.name)


Item = TypeVar("Item")


@attr.define
class ResourceGetResponse(Generic[Item]):
    items: Sequence[Item] = attr.Factory(list)

    @classmethod
    def of(cls, *items: Item):
        """Puts all arguments into the items list"""
        return cls(items)
