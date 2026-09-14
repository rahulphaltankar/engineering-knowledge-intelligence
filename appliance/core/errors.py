"""Appliance error taxonomy.

Every error carries a machine-readable code so failures surface as actionable
engineering statements rather than stack traces.

`EvidenceInsufficient` is deliberately NOT an error class. "The context does not
support an answer" is a successful outcome carried by the Result envelope, not a
failure. Conflating the two is how systems end up inventing answers.
"""
from __future__ import annotations


class ApplianceError(Exception):
    """Base class. `code` is stable and machine-readable."""

    code = "APPLIANCE_ERROR"

    def __init__(self, message: str, **detail):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class ConfigurationError(ApplianceError):
    code = "CONFIGURATION_ERROR"


class ConnectorError(ApplianceError):
    code = "CONNECTOR_ERROR"


class ConnectorDisabledError(ConnectorError):
    code = "CONNECTOR_DISABLED"


class NotSupportedError(ConnectorError):
    """The connector cannot answer this - distinct from 'the answer is nothing'."""

    code = "OPERATION_NOT_SUPPORTED"


class AuthorisationError(ApplianceError):
    code = "AUTHORISATION_DENIED"


class ModelError(ApplianceError):
    code = "MODEL_ERROR"


class ModelNotConfiguredError(ModelError):
    code = "MODEL_NOT_CONFIGURED"


class GuardrailViolation(ApplianceError):
    code = "GUARDRAIL_VIOLATION"


class WorkflowError(ApplianceError):
    code = "WORKFLOW_ERROR"


class ContextError(ApplianceError):
    code = "CONTEXT_ERROR"


class ReviewError(ApplianceError):
    """A reviewer decision that cannot be recorded as submitted."""

    code = "REVIEW_ERROR"
