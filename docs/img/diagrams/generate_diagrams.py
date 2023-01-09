import html
import textwrap

from diagrams import Cluster, Diagram, Node
from diagrams.custom import Custom
from diagrams.generic.os import RedHat
from diagrams.onprem.client import Users
from diagrams.onprem.monitoring import Grafana, Prometheus


def _format_node_label(name, description):
    """Create a graphviz label string for a C4 node"""
    title = f'<font point-size="12"><b>{html.escape(name)}</b></font><br/>'
    text = (
        f'<br/><font point-size="10">{_format_description(description)}</font>'
        if description
        else ""
    )
    return f"<{title}{text}>"


def _format_description(description):
    """
    Formats the description string so it fits into the C4 nodes.

    It line-breaks the description so it fits onto exactly three lines. If there are more
    than three lines, all further lines are discarded and "..." inserted on the last line to
    indicate that it was shortened. This will also html-escape the description so it can
    safely be included in a HTML label.
    """
    wrapper = textwrap.TextWrapper(width=40, max_lines=3)
    lines = [html.escape(line) for line in wrapper.wrap(description)]
    lines += [""] * (3 - len(lines))  # fill up with empty lines so it is always three
    return "<br/>".join(lines)


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
    # collapse boxes to a smaller form if they don't have a description
    if not description:
        node_attributes.update({"width": "2", "height": "1"})
    node_attributes.update(kwargs)
    return Node(**node_attributes)


def CustomContainer(name, technology="", description="", **kwargs):
    return C4Node(name, technology=technology, description=description)


graph_attr = {
    "bgcolor": "transparent",
    "fontsize": "20",
    "fontcolor": "#787878",
    "pad": "0.2",
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
        (
            Grafana("Grafana")
            << Prometheus("Prometheus")
            << [
                Custom("Commit time\nexporter", pelorus_icon),
                Custom("Failure\nexporter", pelorus_icon),
                Custom("Deploy time\nexporter", pelorus_icon),
            ]
        )


with Diagram("Pelorus Overview2", show=False, graph_attr=graph_attr):
    git_provider = CustomContainer("Git Provider(s)")
    issue_tracker = CustomContainer("Issue Tracker(s)")
    with Cluster("OpenShift Cluster"):
        namespaces = RedHat("OpenShift\nNamespace(s)")
        with Cluster("Pelorus"):
            with Cluster("Pelorus Exporters"):
                commit = Custom("Commit time\nexporter(s)", pelorus_icon)
                failure = Custom("Failure\nexporter(s)", pelorus_icon)
                deploy = Custom("Deploy time\nexporter(s)", pelorus_icon)
                exporters = [
                    commit,
                    failure,
                    deploy,
                ]

            with Cluster("Pelorus Core"):
                (Grafana("Grafana") << Prometheus("Prometheus") << exporters)
        commit << namespaces
        deploy << namespaces
        commit << git_provider
        failure << issue_tracker


with Diagram(
    "Pelorus pipeline configuration for Bitbucket & Jira",
    show=False,
    graph_attr=graph_attr,
):
    with Cluster("OpenShift Cluster"):
        pelorus_operator = Custom("Install\nPelorus Operator", pelorus_icon)
        with Cluster("Create Pelorus instances configuration"):
            with Cluster("Commit time exporter"):
                (
                    CustomContainer(
                        "Git provider",
                        description="Set VCS as Bitbucket with GIT_PROVIDE=bitbucket",
                    )
                    >> CustomContainer(
                        "Credentials",
                        description="Set Credentials with API_USER=<bitbucket_username> and TOKEN=<bitbucket_token> (even public??)",
                    )
                    >> CustomContainer(
                        "Namespace",
                        description="Set the Namespace(s) the exporter will monitor with NAMESPACES=<namespace1,namespace2>",
                    )
                )

            with Cluster("Failure exporter configuration"):
                (
                    pelorus_operator
                    >> CustomContainer(
                        "Provider",
                        description="There is no need to set ITS as Jira with PROVIDER=jira, because it is the default",
                    )
                    >> CustomContainer(
                        "Server URL",
                        description="Set Jira server URL with SERVER=<url>",
                    )
                    >> CustomContainer(
                        "Credentials",
                        description="Set Credentials with API_USER=<jira_username> and TOKEN=<jira_token> (even public??)",
                    )
                    >> CustomContainer(
                        "Project(s) name(s)",
                        description="Set the Jira projects to be monitored with PROJECTS=<project1,project2>",
                    )
                    >> CustomContainer(
                        "Issues discovery",
                        description="Add label to issues or use Jira query language (JQL)...",
                    )
                )

            with Cluster("Deploy time exporter configuration"):
                (CustomContainer("Deployment type(?)") >> CustomContainer("Namespace"))


with Diagram("Jira Failure exporter configuration", show=False, graph_attr=graph_attr):
    main = (
        CustomContainer("PROVIDER=jira")
        >> CustomContainer("SERVER=<url>")
        >> CustomContainer("API_USER=<jira_username>")
        >> CustomContainer("TOKEN=<jira_token>")
        >> CustomContainer("PROJECTS=<project1,project2>")
    )
    main >> CustomContainer("Add labels to Issues")
    (
        main
        >> CustomContainer("JIRA_JQL_SEARCH_QUERY")
        >> CustomContainer("JIRA_RESOLVED_STATUS")
    )
