from typing import Any

from attrs import frozen


@frozen
class DeployTimeMetric:
    name: str
    namespace: str
    # WARNING: do not mutate the dict after hashing or things may break.
    labels: dict[str, str]
    deploy_time: Any
    image_sha: str

    def __hash__(self):
        return hash(
            (
                self.name,
                self.namespace,
                hash(tuple(self.labels.items())),
                self.deploy_time,
                self.image_sha,
            )
        )


__all__ = ["DeployTimeMetric"]
