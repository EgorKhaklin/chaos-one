#!/usr/bin/env bash
# Build the Chaos One Unity player headlessly.
#
# Locates a Unity Editor install via Unity Hub on macOS/Linux/Windows,
# then runs `Unity -batchmode -executeMethod ChaosOne.EditorScripts.BuildPlayer.Run`
# against this project. Defaults to macOS Universal output; override
# with --target windows|linux|macos and --output PATH.
#
# Prerequisites:
#   1. Unity Hub installed.
#   2. A Unity 6 LTS Editor installed via Hub (see Packages/manifest.json).
#   3. At least one .unity scene file saved under Assets/_ChaosOne/Scenes/
#      (or configured under File > Build Profiles > Scene List).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET="macos"
OUTPUT=""
EDITOR_VERSION=""
LOG_FILE=""
BOOTSTRAP=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGET="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --editor-version)
            EDITOR_VERSION="$2"
            shift 2
            ;;
        --log)
            LOG_FILE="$2"
            shift 2
            ;;
        --bootstrap|--bootstrap-scene)
            BOOTSTRAP=1
            shift
            ;;
        -h|--help)
            grep '^# ' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

case "$TARGET" in
    macos|mac|osx)
        TARGET_FLAG="OSXUniversal"
        DEFAULT_OUTPUT="${SCRIPT_DIR}/dist/ChaosOne.app"
        ;;
    windows|win)
        TARGET_FLAG="Win64"
        DEFAULT_OUTPUT="${SCRIPT_DIR}/dist/ChaosOne.exe"
        ;;
    linux)
        TARGET_FLAG="Linux64"
        DEFAULT_OUTPUT="${SCRIPT_DIR}/dist/ChaosOne"
        ;;
    *)
        echo "unknown --target: $TARGET (expected macos|windows|linux)" >&2
        exit 2
        ;;
esac

OUTPUT="${OUTPUT:-$DEFAULT_OUTPUT}"
LOG_FILE="${LOG_FILE:-${SCRIPT_DIR}/build.log}"

find_editor_macos() {
    local hub_root="/Applications/Unity/Hub/Editor"
    if [[ ! -d "$hub_root" ]]; then
        return 1
    fi
    if [[ -n "$EDITOR_VERSION" && -d "$hub_root/$EDITOR_VERSION" ]]; then
        echo "$hub_root/$EDITOR_VERSION/Unity.app/Contents/MacOS/Unity"
        return 0
    fi
    local latest
    latest="$(ls -1 "$hub_root" 2>/dev/null | sort -V | tail -n1)"
    if [[ -z "$latest" ]]; then
        return 1
    fi
    echo "$hub_root/$latest/Unity.app/Contents/MacOS/Unity"
}

find_editor_linux() {
    local hub_root="$HOME/Unity/Hub/Editor"
    [[ -d "$hub_root" ]] || return 1
    if [[ -n "$EDITOR_VERSION" && -d "$hub_root/$EDITOR_VERSION" ]]; then
        echo "$hub_root/$EDITOR_VERSION/Editor/Unity"
        return 0
    fi
    local latest
    latest="$(ls -1 "$hub_root" 2>/dev/null | sort -V | tail -n1)"
    [[ -n "$latest" ]] || return 1
    echo "$hub_root/$latest/Editor/Unity"
}

case "$(uname -s)" in
    Darwin)  UNITY_BIN="$(find_editor_macos || true)" ;;
    Linux)   UNITY_BIN="$(find_editor_linux || true)" ;;
    *)       UNITY_BIN="" ;;
esac

if [[ -z "${UNITY_BIN:-}" || ! -x "${UNITY_BIN:-/dev/null}" ]]; then
    cat >&2 <<EOM
chaos-one: no Unity Editor found.

Install Unity Hub from https://unity.com/download, then install Unity
6 LTS through Hub. After that, this script will find it automatically.

Set --editor-version 6000.0.x to pin a specific install.
EOM
    exit 3
fi

mkdir -p "$(dirname "$OUTPUT")"
mkdir -p "$(dirname "$LOG_FILE")"

echo "[build] Unity editor : $UNITY_BIN"
echo "[build] target       : $TARGET_FLAG"
echo "[build] output       : $OUTPUT"
echo "[build] log          : $LOG_FILE"
echo "[build] project      : $SCRIPT_DIR"
echo "[build] bootstrap    : $([[ $BOOTSTRAP -eq 1 ]] && echo yes || echo no)"
echo ""

if [[ $BOOTSTRAP -eq 1 ]]; then
    BOOTSTRAP_LOG="${LOG_FILE%.log}.bootstrap.log"
    echo "[build] running AutoSceneBuilder (log: $BOOTSTRAP_LOG)"
    set +e
    "$UNITY_BIN" \
        -batchmode \
        -nographics \
        -quit \
        -projectPath "$SCRIPT_DIR" \
        -executeMethod ChaosOne.EditorScripts.AutoSceneBuilder.Create \
        -logFile "$BOOTSTRAP_LOG"
    bootstrap_status=$?
    set -e
    if [[ $bootstrap_status -ne 0 ]]; then
        echo "[build] scene bootstrap failed (exit $bootstrap_status). Tail of $BOOTSTRAP_LOG:"
        tail -n 40 "$BOOTSTRAP_LOG" || true
        exit $bootstrap_status
    fi
    echo "[build] scene bootstrap complete"
    echo ""
fi

set +e
"$UNITY_BIN" \
    -batchmode \
    -nographics \
    -quit \
    -projectPath "$SCRIPT_DIR" \
    -executeMethod ChaosOne.EditorScripts.BuildPlayer.Run \
    -buildTarget "$TARGET_FLAG" \
    -buildOutput "$OUTPUT" \
    -logFile "$LOG_FILE"
status=$?
set -e

if [[ $status -ne 0 ]]; then
    echo ""
    echo "[build] failed (exit $status). Tail of $LOG_FILE:"
    tail -n 40 "$LOG_FILE" || true
    exit $status
fi

echo ""
echo "[build] success: $OUTPUT"
ls -lh "$OUTPUT" 2>/dev/null || true
