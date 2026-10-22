"""Unit tests for the CLI computational tool."""

import json
import os
import subprocess
import sys
import tempfile

from src.cli import (
    calculate_age_score,
    calculate_distance_score,
    calculate_interests_score,
    evaluate_compatibility,
    main,
)
from src.config import EXIT_FAILURE, EXIT_SUCCESS, ZERO


def test_calculate_age_score() -> None:
    """Verify age similarity scoring."""
    score_exact = calculate_age_score(25.0, 25.0)
    assert score_exact == 1.0

    score_diff = calculate_age_score(20.0, 45.0)
    assert score_diff == 0.0


def test_calculate_interests_score() -> None:
    """Verify interests Jaccard scoring."""
    score, common = calculate_interests_score(["a", "b"], ["b", "c"])
    assert len(common) == 1
    assert score > ZERO

    empty_sc, empty_com = calculate_interests_score([], [])
    assert empty_sc == 0.0
    assert len(empty_com) == ZERO


def test_calculate_distance_score() -> None:
    """Verify distance scoring."""
    score_same = calculate_distance_score(55.0, 37.0, 55.0, 37.0)
    assert score_same == 1.0

    score_far = calculate_distance_score(55.0, 37.0, 10.0, 10.0)
    assert score_far == 0.0


def test_evaluate_compatibility_levels() -> None:
    """Verify profile compatibility label thresholds."""
    prof1 = {"id": 1, "age": 25, "interests": ["a"], "lat": 0.0, "lon": 0.0}
    prof2 = {"id": 2, "age": 25, "interests": ["a"], "lat": 0.0, "lon": 0.0}
    res_high = evaluate_compatibility(prof1, prof2)
    assert res_high["status"] == "MATCH"

    prof3 = {
        "id": 3,
        "age": 25,
        "interests": ["a", "b", "c"],
        "lat": 0.0,
        "lon": 0.0,
    }
    prof4 = {
        "id": 4,
        "age": 27,
        "interests": ["a", "d", "e"],
        "lat": 0.5,
        "lon": 0.5,
    }
    res_pot = evaluate_compatibility(prof3, prof4)
    assert res_pot["status"] == "POTENTIAL"

    prof5 = {"id": 5, "age": 20, "interests": ["x"], "lat": 0.0, "lon": 0.0}
    prof6 = {"id": 6, "age": 50, "interests": ["y"], "lat": 10.0, "lon": 10.0}
    res_low = evaluate_compatibility(prof5, prof6)
    assert res_low["status"] == "UNLIKELY"


def test_cli_execution_subprocess() -> None:
    """Verify running CLI tool as subprocess on sample input."""
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
        assert data["status"] == "MATCH"
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def test_cli_main_missing_arguments(monkeypatch) -> None:
    """Verify main function handles missing arguments."""
    monkeypatch.setattr(sys, "argv", ["src.cli"])
    code = main()
    assert code == EXIT_FAILURE


def test_cli_main_invalid_file(monkeypatch) -> None:
    """Verify main function handles nonexistent file."""
    monkeypatch.setattr(
        sys, "argv", ["src.cli", "-i", "missing.json", "-o", "out.json"]
    )
    code = main()
    assert code == EXIT_FAILURE
