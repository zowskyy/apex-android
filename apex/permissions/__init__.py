"""Permission intelligence package."""

from .catalog import load_catalog, lookup_permission
from .enrich import enrich_declared, enrich_with_grants, parse_granted_from_dumpsys
from .linkage import link_permissions_to_dex

__all__ = [
    "enrich_declared",
    "enrich_with_grants",
    "link_permissions_to_dex",
    "load_catalog",
    "lookup_permission",
    "parse_granted_from_dumpsys",
]
