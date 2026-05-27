from __future__ import annotations


class TrackerIssue:
    __slots__ = ("issue_number", "creationdate", "resolutiondate", "app")

    def __init__(
        self,
        issue_number: str,
        creationdate: str | float | int,
        resolutiondate: str | float | int | None,
        app: str,
    ):
        self.creationdate = creationdate
        self.resolutiondate = resolutiondate
        self.issue_number = issue_number
        self.app = app


class FailureMetric:
    __slots__ = ("time_stamp", "is_resolution", "labels")

    def __init__(
        self, time_stamp: str | float | int, is_resolution=False, labels=None
    ):
        if labels is None:
            labels = []
        self.time_stamp = time_stamp
        self.is_resolution = is_resolution
        self.labels = labels


__all__ = ["TrackerIssue", "FailureMetric"]
