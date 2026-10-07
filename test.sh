#!/usr/bin/env bash

MODE=""
OUTPUT_PATH=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        base)
            MODE="base"
            shift
            ;;
        new)
            MODE="new"
            shift
            ;;
        --output_path)
            if [ "$#" -lt 2 ]; then
                echo "Missing value for --output_path"
                exit 2
            fi
            OUTPUT_PATH="$2"
            shift 2
            ;;
        --output_path=*)
            OUTPUT_PATH="${1#*=}"
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 2
            ;;
    esac
done

if [ -z "$MODE" ]; then
    echo "Missing mode: base or new"
    exit 2
fi

if [ -z "$OUTPUT_PATH" ]; then
    echo "Missing --output_path"
    exit 2
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"

NEW_TESTS="test/sql/test_generative_add_for_update_clauses.py"

if [ "$MODE" = "base" ]; then
    echo "=== BASE MODE ==="

    python3 -m pytest \
        test/dialect/postgresql/test_compiler.py -k "for_update" \
        test/dialect/oracle/test_compiler.py -k "for_update" \
        test/dialect/mysql/test_for_update.py \
        test/sql/test_compiler.py -k "for_update" \
        --junitxml="$OUTPUT_PATH" \
        -q

    EXIT_CODE=$?

    if [ ! -f "$OUTPUT_PATH" ]; then
        echo "ERROR: JUnit XML was not created."
        exit 1
    fi

    exit "$EXIT_CODE"
fi

if [ "$MODE" = "new" ]; then
    echo "=== NEW MODE ==="

    python3 -m pytest \
        "$NEW_TESTS" \
        --junitxml="$OUTPUT_PATH" \
        -q

    EXIT_CODE=$?

    if [ ! -f "$OUTPUT_PATH" ]; then
        echo "ERROR: JUnit XML was not created."
        exit 1
    fi

    exit "$EXIT_CODE"
fi

echo "Unknown mode: $MODE"
exit 2
