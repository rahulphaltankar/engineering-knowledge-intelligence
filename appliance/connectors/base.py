"""The universal connector contract.

This abstraction is what makes the appliance enterprise-independent. A PLM, ALM
or QMS connector implements exactly these methods against a customer system and
nothing above the connector changes.

Two rules matter more than they look:

1. READ-ONLY IS STRUCTURAL. There is no write, create, update or delete method on
   this class at all. It is not a configuration flag someone can flip, and
   `tests/test_connector_contract.py` asserts its absence.

2. "CANNOT ANSWER" IS NOT "THE ANSWER IS NOTHING". A connector that does not
   support an operation must declare that in `capabilities()` and raise
   NotSupportedError. Returning an empty result instead makes the appliance
   report a false evidence gap, which is worse than an error because it looks
   like a finding.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from ..core.entities import EngineeringEntity, Relationship
from ..core.errors import NotSupportedError
from ..core.provenance import Provenance


class ConnectorState(str, Enum):
    NOT_CONFIGURED = "not_configured"      # no adapter implemented, or unconfigured
    CONFIGURED = "configured"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


CANONICAL_OPERATIONS = (
    "get_requirement", "get_component", "get_change", "get_fmea", "get_test",
    "get_test_result", "get_quality_issue", "get_supplier", "get_evidence",
    "get_standard", "get_document", "get_measurement", "get_failure_mode",
    "get_risk", "search_engineering_context", "neighbours", "list_by_type",
)


class Connector(ABC):
    """Read-only access to one engineering source."""

    connector_id: str = "abstract"
    connector_name: str = "Abstract Connector"
    category: str = "generic"
    mode: str = "read_only"
    write_capable: bool = False

    # -- lifecycle ---------------------------------------------------------
    @abstractmethod
    def configure(self, config: dict) -> None: ...

    @abstractmethod
    def test_connection(self) -> dict:
        """Structured diagnosis, never a bare boolean.

        'Connection failed' is useless to an operator. 'Authenticated but the
        service account lacks read permission on the requirements module' is
        actionable.
        """

    @abstractmethod
    def status(self) -> dict: ...

    @abstractmethod
    def capabilities(self) -> dict:
        """Which operations and entity types this connector actually supports."""

    def close(self) -> None:
        return None

    # -- canonical reads ---------------------------------------------------
    def _unsupported(self, operation: str):
        raise NotSupportedError(
            f"{self.connector_id} does not support {operation}",
            connector=self.connector_id, operation=operation)

    def get_entity(self, entity_id: str) -> EngineeringEntity | None:
        return self._unsupported("get_entity")

    def get_requirement(self, entity_id: str): return self._typed(entity_id, "Requirement")
    def get_component(self, entity_id: str): return self._typed(entity_id, "Component")
    def get_change(self, entity_id: str): return self._typed(entity_id, "EngineeringChange")
    def get_fmea(self, entity_id: str): return self._typed(entity_id, "FMEA")
    def get_test(self, entity_id: str): return self._typed(entity_id, "TestCase")
    def get_test_result(self, entity_id: str): return self._typed(entity_id, "TestResult")
    def get_quality_issue(self, entity_id: str): return self._typed(entity_id, "QualityIssue")
    def get_supplier(self, entity_id: str): return self._typed(entity_id, "Supplier")
    def get_evidence(self, entity_id: str): return self._typed(entity_id, "Evidence")
    def get_standard(self, entity_id: str): return self._typed(entity_id, "Standard")
    def get_document(self, entity_id: str): return self._typed(entity_id, "Document")
    def get_measurement(self, entity_id: str): return self._typed(entity_id, "Measurement")
    def get_failure_mode(self, entity_id: str): return self._typed(entity_id, "FailureMode")
    def get_risk(self, entity_id: str): return self._typed(entity_id, "Risk")

    def _typed(self, entity_id: str, entity_type: str) -> EngineeringEntity | None:
        """Type-safe read. Returning the wrong entity type would let an agent
        build a chain of reasoning on a category error."""
        entity = self.get_entity(entity_id)
        if entity is None or entity.entity_type != entity_type:
            return None
        return entity

    def list_by_type(self, entity_type: str) -> list[EngineeringEntity]:
        return self._unsupported("list_by_type")

    def search_engineering_context(self, query: str, entity_type: str | None = None,
                                   limit: int = 40) -> list[dict]:
        return self._unsupported("search_engineering_context")

    def relationships_for(self, entity_id: str) -> list[Relationship]:
        return self._unsupported("relationships_for")

    def all_relationships(self) -> list[Relationship]:
        return self._unsupported("all_relationships")

    # -- provenance --------------------------------------------------------
    def stamp(self, entity_id: str, **extra: Any) -> Provenance:
        """Provenance is stamped by the base class so an adapter author cannot
        forget it."""
        return Provenance(connector_id=self.connector_id,
                          source_system=self.connector_name,
                          source_object_id=entity_id, **extra)
