"""Hash-chained audit log primitives.

Append-only JSONL with a SHA-256 Merkle chain over the entries. Each
entry's hash is computed from the previous-hash + the entry payload,
so any tampering after the fact is detectable by replaying the chain.
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
