"""Connector registry and router.

Manages the universal catalogue, per-connector state, runtime enable/disable and
capability-aware fan-out across every enabled connector.

Two properties are demonstrated live and so are enforced here rather than by
convention:

- Enable/disable takes effect immediately, with no restart and no image rebuild.
- A disabled connector is STRUCTURALLY unreachable: it is not returned from any
  lookup, and `tests/test_architecture.py` proves it cannot be invoked.
"""
from __future__ import annotations

from ..core.entities import EngineeringEntity, Relationship
from ..core.errors import ConnectorDisabledError, ConnectorError, NotSupportedError
from .base import Connector, ConnectorState
from .catalogue import CATALOGUE


class ConnectorRegistry:
    def __init__(self) -> None:
        self._state: dict[str, ConnectorState] = {}
        self._meta: dict[str, dict] = {}
        self._instances: dict[str, Connector] = {}
        self._diagnosis: dict[str, dict] = {}
        for cid, name, category, implemented in CATALOGUE:
            self._state[cid] = ConnectorState.NOT_CONFIGURED
            self._meta[cid] = {"connector_id": cid, "name": name, "category": category,
                               "adapter_implemented": implemented}

    # -- registration ------------------------------------------------------
    def register(self, connector: Connector, config: dict | None = None,
                 enable: bool = False) -> None:
        cid = connector.connector_id
        if cid not in self._meta:
            raise ConnectorError(f"{cid} is not in the universal catalogue", connector=cid)
        connector.configure(config or {})
        diagnosis = connector.test_connection()
        self._diagnosis[cid] = diagnosis
        if not diagnosis.get("ok"):
            self._state[cid] = ConnectorState.ERROR
            return
        self._instances[cid] = connector
        self._state[cid] = ConnectorState.ENABLED if enable else ConnectorState.CONFIGURED

    # -- lifecycle ---------------------------------------------------------
    def enable(self, connector_id: str) -> None:
        if connector_id not in self._instances:
            raise ConnectorError(
                f"{connector_id} has no adapter implementation and cannot be enabled",
                connector=connector_id)
        self._state[connector_id] = ConnectorState.ENABLED

    def disable(self, connector_id: str) -> None:
        if self._state.get(connector_id) == ConnectorState.ENABLED:
            self._state[connector_id] = ConnectorState.DISABLED

    def state(self, connector_id: str) -> ConnectorState:
        return self._state.get(connector_id, ConnectorState.NOT_CONFIGURED)

    def enabled_connectors(self, within: list[str] | None = None) -> list[Connector]:
        return [c for cid, c in self._instances.items()
                if self._state.get(cid) == ConnectorState.ENABLED
                and (within is None or cid in within)]

    def get(self, connector_id: str) -> Connector:
        """A disabled connector is unreachable, not merely discouraged."""
        state = self._state.get(connector_id)
        if state != ConnectorState.ENABLED:
            raise ConnectorDisabledError(
                f"{connector_id} is {state.value if state else 'unknown'}",
                connector=connector_id)
        return self._instances[connector_id]

    # -- catalogue view ----------------------------------------------------
    def catalogue(self) -> list[dict]:
        rows = []
        for cid, meta in self._meta.items():
            state = self._state[cid]
            if not meta["adapter_implemented"]:
                display = "NO ADAPTER"
            elif state == ConnectorState.ENABLED:
                display = "ACTIVE"
            elif state == ConnectorState.ERROR:
                display = "ERROR"
            else:
                display = "DISABLED"
            rows.append({**meta, "state": state.value, "display_state": display,
                         "diagnosis": self._diagnosis.get(cid)})
        return rows

    def summary(self) -> dict:
        rows = self.catalogue()
        return {"total": len(rows),
                "active": sum(1 for r in rows if r["display_state"] == "ACTIVE"),
                "disabled": sum(1 for r in rows if r["display_state"] == "DISABLED"),
                "no_adapter": sum(1 for r in rows if r["display_state"] == "NO ADAPTER"),
                "error": sum(1 for r in rows if r["display_state"] == "ERROR")}

    # -- capability-aware fan-out -----------------------------------------
    def fan_out(self, operation: str, *args, within: list[str] | None = None,
                **kwargs) -> dict:
        """Invoke one canonical operation across every enabled connector.

        Records which connectors were queried, answered, failed or did not
        support the operation. That participation record is part of the
        provenance of the answer and is what makes honest evidence-gap reporting
        possible: 'no enabled connector supports this' is a different statement
        from 'the answer is nothing'.

        `within` scopes the fan-out to named connectors - an analysis of one
        domain's dataset should not silently merge another domain's records.
        """
        answered, unsupported, failed, results = [], [], [], []
        enabled = self.enabled_connectors(within)
        for connector in enabled:
            method = getattr(connector, operation, None)
            if method is None:
                unsupported.append(connector.connector_id)
                continue
            try:
                value = method(*args, **kwargs)
            except NotSupportedError:
                unsupported.append(connector.connector_id)
                continue
            except Exception as exc:  # degrade, never fail the whole request
                failed.append({"connector": connector.connector_id, "error": str(exc)})
                continue
            answered.append(connector.connector_id)
            results.append(value)
        return {"operation": operation, "queried": [c.connector_id for c in enabled],
                "answered": answered, "unsupported": unsupported, "failed": failed,
                "results": results,
                "no_connector_supports": bool(enabled) and not answered and not failed}

    # -- convenience merges ------------------------------------------------
    def get_entity(self, entity_id: str) -> EngineeringEntity | None:
        outcome = self.fan_out("get_entity", entity_id)
        for value in outcome["results"]:
            if value is not None:
                return value
        return None

    def list_by_type(self, entity_type: str,
                     within: list[str] | None = None) -> list[EngineeringEntity]:
        merged: list[EngineeringEntity] = []
        for value in self.fan_out("list_by_type", entity_type, within=within)["results"]:
            merged.extend(value or [])
        return merged

    def all_relationships(self, within: list[str] | None = None) -> list[Relationship]:
        merged: list[Relationship] = []
        for value in self.fan_out("all_relationships", within=within)["results"]:
            merged.extend(value or [])
        return merged

    def search(self, query: str, limit: int = 40) -> list[dict]:
        merged: list[dict] = []
        for value in self.fan_out("search_engineering_context", query, None, limit)["results"]:
            merged.extend(value or [])
        return merged[:limit]
