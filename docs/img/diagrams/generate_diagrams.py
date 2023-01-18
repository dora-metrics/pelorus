import html
import textwrap

from diagrams import Cluster, Diagram, Node
from diagrams.custom import Custom
from diagrams.onprem.client import Users
from diagrams.onprem.monitoring import Grafana, Prometheus


# Overridden diagrams.c4.Container
def CustomContainer(name, technology="", description=""):
    return C4Node(name, technology=technology, description=description)


def C4Node(name, description="", **kwargs):
    node_attributes = {
        "label": _format_node_label(name, description),
        "labelloc": "c",
        "shape": "rect",
        "width": "2.6",
        "height": "1.6",
        "fixedsize": "true",
        "style": "filled",
        "fillcolor": "dodgerblue3",
        "fontcolor": "white",
    }
    if not description:
        node_attributes.update({"width": "2", "height": "1"})
    node_attributes.update(kwargs)
    return Node(**node_attributes)


def _format_node_label(name, description):
    title = f'<font point-size="12"><b>{html.escape(name)}</b></font><br/>'
    text = (
        f'<br/><font point-size="10">{_format_description(description)}</font>'
        if description
        else ""
    )
    return f"<{title}{text}>"


def _format_description(description):
    wrapper = textwrap.TextWrapper(width=40, max_lines=3)
    lines = [html.escape(line) for line in wrapper.wrap(description)]
    lines += [""] * (3 - len(lines))
    return "<br/>".join(lines)


graph_attr = {
    "bgcolor": "transparent",
    "fontsize": "20",
    "fontcolor": "#787878",
    "pad": "0",
}

pelorus_icon = "../Icon-Pelorus-A-Standard-RGB_smaller.png"


with Diagram("Pelorus Deployment steps", show=False, graph_attr=graph_attr):
    with Cluster("OpenShift Cluster"):
        users = Users("See measures")
        pelorus_operator = Custom("Install\nPelorus Operator", pelorus_icon)

        with Cluster("Create Pelorus instance"):
            (
                pelorus_operator
                >> CustomContainer("Configure")
                >> [
                    CustomContainer("Failure Exporter"),
                    CustomContainer("Commit time Exporter"),
                    CustomContainer("Deploy time Exporter"),
                    CustomContainer("Pelorus Core"),
                ]
                >> users
            )


with Diagram("Pelorus Overview", show=False, direction="TB", graph_attr=graph_attr):
    with Cluster("Pelorus"):
        with Cluster("Pelorus Core"):
            core = Grafana("Grafana") << Prometheus("Prometheus")

        with Cluster("Pelorus Exporters"):
            core << [
                Custom("Commit time\nexporter", pelorus_icon),
                Custom("Failure\nexporter", pelorus_icon),
                Custom("Deploy time\nexporter", pelorus_icon),
            ]
