from datetime import datetime
from typing import Union

from pelorus.timeutil import parse_assuming_utc

# https://docs.openshift.com/container-platform/4.10/rest_api/objects/index.html#io.k8s.apimachinery.pkg.apis.meta.v1.ObjectMeta
_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_datetime(dt_str: str) -> datetime:
    return parse_assuming_utc(dt_str, _DATETIME_FORMAT)


def convert_datetime(dt: Union[str, datetime]) -> datetime:
    """
    For use with attrs.
    """
    if isinstance(dt, datetime):
        return dt
    else:
        return parse_datetime(dt)
