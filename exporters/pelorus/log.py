import logging

from pelorus import NamespaceSpec


def log_namespaces(namespaces: NamespaceSpec):
    """Log the namespaces that have been passed, calling out how it defaults to all

    Assume that None means that no namespaces were specified and no filter for all namespaces given.
    Assume that empty list means that a filter for all namespaces was given and that filter
    resulted in an empty list of namespaces so default to watching no namespaces.
    """
    if namespaces is None:
        logging.info("No namespaces specified, watching all namespaces")
    else:
        logging.info("Watching namespaces %s", namespaces)
