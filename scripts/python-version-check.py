from sys import argv, exit, version_info

PYTHON_VER_MIN = (3, 9)
PYTHON_VER_MAX = (3, 10)

SYS_PYTHON_VER = (version_info.major, version_info.minor)

if not PYTHON_VER_MIN <= SYS_PYTHON_VER <= PYTHON_VER_MAX:
    print(
        "{} needs to be between {}.{} and {}.{}, but was {}.{}".format(
            argv[1], *PYTHON_VER_MIN, *PYTHON_VER_MAX, *SYS_PYTHON_VER
        )
    )
    exit(1)
