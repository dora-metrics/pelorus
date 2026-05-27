import functools

__all__ = ["format_app_name", "APP_NAME_SEPARATOR"]

APP_NAME_SEPARATOR = "/"


@functools.lru_cache(maxsize=1024)
def format_app_name(name: str) -> str:
    """
    Format application name so each comma-separated part is wrapped in "/".

    Ensures each segment starts and ends with "/" and normalizes double slashes.

    >>> assert format_app_name("robotron") == "/robotron/"
    >>> assert format_app_name("/robotron") == "/robotron/"
    >>> assert format_app_name("robotron/") == "/robotron/"
    >>> assert format_app_name("robotron,rufus") == "/robotron/,/rufus/"
    >>> assert format_app_name("group/sub/robotron") == "/group/sub/robotron/"
    >>> assert format_app_name("group/robotron,other/rufus") == "/group/robotron/,/other/rufus/"
    >>> assert format_app_name("group/robotron/,/other/rufus") == "/group/robotron/,/other/rufus/"
    >>> assert format_app_name("G1/T1/A1,F1/A1,C1/S1/A1") == "/G1/T1/A1/,/F1/A1/,/C1/S1/A1/"
    """
    name = name.replace(",", f"{APP_NAME_SEPARATOR},{APP_NAME_SEPARATOR}")
    if not name.startswith(APP_NAME_SEPARATOR):
        name = APP_NAME_SEPARATOR + name
    if not name.endswith(APP_NAME_SEPARATOR):
        name = name + APP_NAME_SEPARATOR
    return name.replace(APP_NAME_SEPARATOR * 2, APP_NAME_SEPARATOR)
