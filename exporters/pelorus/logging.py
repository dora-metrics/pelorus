import logging

from pelorus import NamespaceSpec


def log_namespaces(namespaces: NamespaceSpec):
    """Log the namespaces that have been passed, calling out how it defaults to all"""
    if not namespaces:
        logging.info("No namespaces specified, watching all namespaces")
    else:
        logging.info("Watching namespaces %s", namespaces)
