"""Hash-chained audit log primitives.

Append-only JSONL with a SHA-256 Merkle chain over the entries. Designed
as the Python-side companion to the Unity AuditLogWriter so the backend
can produce its own engagement records that a future shared verifier
could reconcile. Cross-platform hash compatibility is a milestone-6
concern; for now each side writes and verifies its own logs with the
same internal contract.
"""

from chaos_backend.audit.log import (
    AuditLogEntry,
    AuditLogReader,
    AuditLogVerifier,
    AuditLogWriter,
    VerificationResult,
)

__all__ = [
    "AuditLogEntry",
    "AuditLogReader",
    "AuditLogVerifier",
    "AuditLogWriter",
    "VerificationResult",
]
