from datetime import datetime

from attrs import field, frozen

from provider_common.openshift import convert_datetime


@frozen
class DeployTimeMetric:
    name: str
    namespace: str
    # WARNING: do not mutate the dict after hashing or things may break.
    labels: dict[str, str]
    deploy_time: datetime = field(converter=convert_datetime)
    image_sha: str

    @property
    def deploy_time_timestamp(self) -> float:
        return self.deploy_time.timestamp()

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
