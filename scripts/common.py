from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "scripts/config.yaml"


def read_yaml_file(yaml_file: Path) -> Any:
    with open(yaml_file, "r", encoding="utf-8") as file:
        content = yaml.safe_load(file)
    return content


def read_key(key: str) -> str:
    config = read_yaml_file(CONFIG_FILE)
    # TODO break gracefully
    return config[key]


def update_key(key: str, value: Any) -> None:
    config = read_yaml_file(CONFIG_FILE)
    # TODO break gracefully
    config[key] = value
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        file.write(yaml.dump(config))
