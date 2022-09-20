from datetime import datetime
from typing import Union

from attrs import field, frozen

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _datetime_converter(dt: Union[str, datetime]) -> datetime:
    if isinstance(dt, datetime):
        return dt
    else:
        return datetime.strptime(dt, DATETIME_FORMAT)


@frozen
class DeployTimeMetric:
    name: str
    namespace: str
    # WARNING: do not mutate the dict after hashing or things may break.
    labels: dict[str, str]
    deploy_time: datetime = field(converter=_datetime_converter)
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
