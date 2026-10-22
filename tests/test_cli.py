"""Unit tests for the EAN-13 barcode PDF generator CLI tool."""

import json
import os
import subprocess
import sys
import tempfile

import pytest

from src.cli import (
    compute_ean13_checksum,
    encode_ean13_bits,
    generate_barcode_pdf,
    main,
    normalize_ean13,
)
from src.config import (
    EAN13_LENGTH,
    EXIT_FAILURE,
    EXIT_SUCCESS,
    EXPECTED_CHECK_DIGIT,
    STATE_SUCCESS,
    TOTAL_MODULES,
    ZERO,
)


def test_compute_ean13_checksum() -> None:
    """Verify standard check digit computation."""
    chk = compute_ean13_checksum("460123456789")
    assert chk == EXPECTED_CHECK_DIGIT

    with pytest.raises(ValueError):
        compute_ean13_checksum("123")


def test_normalize_ean13() -> None:
    """Verify 12-to-13 digit normalization and validation."""
    code13 = normalize_ean13("460123456789")
    assert len(code13) == EAN13_LENGTH
    assert code13 == "4601234567893"

    valid13 = normalize_ean13("4601234567893")
    assert len(valid13) == EAN13_LENGTH

    with pytest.raises(ValueError):
        normalize_ean13("4601234567890")

    with pytest.raises(ValueError):
        normalize_ean13("1234")


def test_encode_ean13_bits() -> None:
    """Verify bit encoding pattern and total module length."""
    bits = encode_ean13_bits("4601234567893")
    assert len(bits) == TOTAL_MODULES
    assert bits.startswith("101")
    assert bits.endswith("101")


def test_generate_barcode_pdf() -> None:
    """Verify vector PDF creation and non-empty file write."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = tmp.name

    try:
        bits = encode_ean13_bits("4601234567893")
        generate_barcode_pdf("4601234567893", bits, pdf_path)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > ZERO
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_cli_execution_subprocess() -> None:
    """Verify subprocess execution of CLI on sample input."""
    input_path = os.path.join("data", "input_1.json")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        out_path = tmp.name

    try:
        cmd = [
            sys.executable,
            "-m",
            "src.cli",
            "-i",
            input_path,
            "-o",
            out_path,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.returncode == EXIT_SUCCESS
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == STATE_SUCCESS
        assert len(data["ean13"]) == EAN13_LENGTH
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def test_cli_main_missing_arguments(monkeypatch) -> None:
    """Verify handling of missing input/output arguments."""
    monkeypatch.setattr(sys, "argv", ["src.cli"])
    code = main()
    assert code == EXIT_FAILURE


def test_cli_main_invalid_file(monkeypatch) -> None:
    """Verify handling of invalid or missing input file."""
    monkeypatch.setattr(
        sys, "argv", ["src.cli", "-i", "nonexistent.json", "-o", "out.json"]
    )
    code = main()
    assert code == EXIT_FAILURE
