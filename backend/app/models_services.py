"""Compatibility shim for the service opportunity model.

The repository previously defined two conflicting ServiceOpportunity mappings for the
same table. Both the raw-lead and canonical-lead pipelines rely on this table, so we
keep a single authoritative model in backend.app.models and re-export it here.
"""

from backend.app.database import Base
from backend.app.models import ServiceOpportunity

__all__ = ["Base", "ServiceOpportunity"]
