#!/usr/bin/env python3
"""Update Project documentation index file."""

import argparse
import sys
from pathlib import Path

TAB = " " * 4
PROJECT_ROOT = Path(__file__).parent.parent
README_FILE = PROJECT_ROOT / "README.md"
DOC_INDEX_FILE = PROJECT_ROOT / "docs/index.md"


def update_doc_index(check: bool = False) -> None:
    """
    Update Project documentation index file.

    Check if the content of docs/index.md file, until the *Prior Knowledge*
    section, is up to date with the content of the README.md file, until the
    *Documentation* section.

    Parameters
    ----------
    check : bool
        Just check if there is content to update, by default False.

    Raises
    ------
    SystemExit
        If there is content to update, when just checking.

    """
    update_content = []
    with open(README_FILE, encoding="utf-8") as readme_file:
        for line in readme_file:
            if line.strip() == "## Documentation":
                break
            update_content.append(line.replace("(docs/img/", "(img/"))

    with open(DOC_INDEX_FILE, encoding="utf-8") as index_file:
        previous_lines = index_file.readlines()

    start = previous_lines.index(update_content[0])
    end = previous_lines.index("## Prior Knowledge\n")

    is_updated = previous_lines[start:end] == update_content
    if check and not is_updated:
        print(
            f"{TAB}{DOC_INDEX_FILE.relative_to(PROJECT_ROOT)} is not up to date.",
            file=sys.stderr,
        )
        print(f"{TAB}Run `make doc-update` to update it.", file=sys.stderr)
        raise SystemExit(1)
    if is_updated:
        print(f"{TAB}{DOC_INDEX_FILE.relative_to(PROJECT_ROOT)} is up to date.")
        return
    previous_lines[start:end] = update_content

    with open(DOC_INDEX_FILE, mode="w", encoding="utf-8") as index_file:
        index_file.writelines(previous_lines)

    print(f"{TAB}{DOC_INDEX_FILE.relative_to(PROJECT_ROOT)} updated successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    update_doc_index(parser.parse_args().check)
