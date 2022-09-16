#!/usr/bin/env python3
import json
from pathlib import Path

import yaml

grafana_dashboard_path = (
    Path(__file__) / "../../charts/pelorus/templates" / "dashboard-sdp.yaml"
).resolve()


with grafana_dashboard_path.open("r") as f:
    chart_yaml = yaml.load(f, yaml.SafeLoader)

grafana_dashboard_contents = json.loads(chart_yaml["spec"]["json"])
panels = grafana_dashboard_contents["panels"]

for panel in panels:
    title = panel["title"]

    if (targets := panel.get("targets")) is None:
        continue

    assert len(targets) == 1

    expr: str = targets[0]["expr"]

    print(title)
    for line in expr.splitlines():
        print("\t" + line)
