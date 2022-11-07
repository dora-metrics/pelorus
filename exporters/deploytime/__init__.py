from attrs import frozen


@frozen
class DeployTimeMetric:
    """
    While it is called image_sha for backwards compatibility,
    it could also refer to the release hash for a github release.
    """

    name: str
    namespace: str
    # WARNING: do not mutate the dict after hashing or things may break.
    labels: dict[str, str]
    deploy_time: object
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
