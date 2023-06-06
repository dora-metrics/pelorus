APP_NAME_SEPARATOR = "/"


def format_app_name(name: str) -> str:
    """
    Format application name to follow standard of being surrounded by "/".

    It adds "/" between commas (",") and beginning and end of the name.

    >>> assert format_app_name("robotron") == "/robotron/"
    >>> assert format_app_name("/robotron") == "/robotron/"
    >>> assert format_app_name("robotron/") == "/robotron/"
    >>> assert format_app_name("robotron,rufus") == "/robotron/,/rufus/"
    >>> assert format_app_name("group/sub/robotron") == "/group/sub/robotron/"
    >>> assert format_app_name("group/robotron,other/rufus") == "/group/robotron/,/other/rufus/"
    >>> assert format_app_name("group/robotron/,/other/rufus") == "/group/robotron/,/other/rufus/"
    >>> assert format_app_name("G1/T1/A1,F1/A1,C1/S1/A1") == "/G1/T1/A1/,/F1/A1/,/C1/S1/A1/"

    Parameters
    ----------
    name : str
        Application name.

    Returns
    -------
    str
        Formatted application name.

    """
    name = name.replace(",", f"{APP_NAME_SEPARATOR},{APP_NAME_SEPARATOR}")
    if not name.startswith(APP_NAME_SEPARATOR):
        name = APP_NAME_SEPARATOR + name
    if not name.endswith(APP_NAME_SEPARATOR):
        name = name + APP_NAME_SEPARATOR
    return name.replace(APP_NAME_SEPARATOR * 2, APP_NAME_SEPARATOR)
