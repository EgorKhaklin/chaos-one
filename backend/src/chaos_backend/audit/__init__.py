"""Hash-chained audit log primitives.

Append-only JSONL with a SHA-256 Merkle chain over the entries. Designed
as the Python-side companion to the Unity AuditLogWriter so the backend
can produce its own engagement records that a future shared verifier
could reconcile. Cross-platform hash compatibility is a milestone-6
concern; for now each side writes and verifies its own logs with the
same internal contract.
"""

from chaos_backend.audit.diff import (
    DiffResult,
    EntryDelta,
)
from chaos_backend.audit.diff import (
    compare as compare_logs,
)
from chaos_backend.audit.diff import (
    compare_paths as compare_log_paths,
)
from chaos_backend.audit.diff import (
    render_html as render_diff_html,
)
from chaos_backend.audit.html_viewer import render as render_html
from chaos_backend.audit.html_viewer import render_from_path as render_html_from_path
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
    "DiffResult",
    "EntryDelta",
    "VerificationResult",
    "compare_log_paths",
    "compare_logs",
    "render_diff_html",
    "render_html",
    "render_html_from_path",
]
