#!/usr/bin/env bash
# Compile chaos_one.proto into Python gRPC stubs.
# Requires `grpcio-tools` (installed by the `dev` extras of pyproject.toml).
#
# Usage:
#   bash scripts/generate_protos.sh
#
# Output:
#   src/chaos_backend/generated/chaos_one_pb2.py
#   src/chaos_backend/generated/chaos_one_pb2_grpc.py
#
# The generated directory is gitignored. Re-run after any change to
# proto/chaos_one.proto.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/src/chaos_backend/generated"

mkdir -p "${OUT}"
touch "${OUT}/__init__.py"

python -m grpc_tools.protoc \
    -I "${ROOT}/proto" \
    --python_out="${OUT}" \
    --grpc_python_out="${OUT}" \
    "${ROOT}/proto/chaos_one.proto"

# Generated grpc_python imports `chaos_one_pb2` at top level; rewrite it to
# match the package layout where stubs live under chaos_backend.generated.
GRPC_FILE="${OUT}/chaos_one_pb2_grpc.py"
if [[ -f "${GRPC_FILE}" ]]; then
    python - "${GRPC_FILE}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    "import chaos_one_pb2 as chaos__one__pb2",
    "from chaos_backend.generated import chaos_one_pb2 as chaos__one__pb2",
)
path.write_text(text)
PY
fi

echo "generated ${OUT}/chaos_one_pb2.py and chaos_one_pb2_grpc.py"
