APP_NAME_SEPARATOR = "/"


def format_app_name(name: str) -> str:
    """
    Format application name to follow standard of being surrounded by "/".

    >>> assert format_app_name("robotron") == "/robotron/"
    >>> assert format_app_name("/robotron") == "/robotron/"
    >>> assert format_app_name("robotron/") == "/robotron/"
    >>> assert format_app_name("group/sub/robotron") == "/group/sub/robotron/"

    Parameters
    ----------
    name : str
        Application name.

    Returns
    -------
    str
        Formatted application name.

    """
    if not name.startswith(APP_NAME_SEPARATOR):
        name = APP_NAME_SEPARATOR + name
    if not name.endswith(APP_NAME_SEPARATOR):
        name = name + APP_NAME_SEPARATOR
    return name
