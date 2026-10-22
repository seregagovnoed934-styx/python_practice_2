"""Command-line interface utility for profile compatibility calculation."""

import argparse
import json
import math
import sys
from typing import Any

from src.config import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    MATCH_THRESHOLD,
    MAX_AGE_DIFF,
    MAX_DISTANCE_KM,
    MAX_PERCENT,
    MAX_SCORE_RATIO,
    MIN_INTERESTS_COUNT,
    MIN_SCORE_RATIO,
    POTENTIAL_THRESHOLD,
    SCORE_WEIGHT_AGE,
    SCORE_WEIGHT_DISTANCE,
    SCORE_WEIGHT_INTERESTS,
    ZERO,
)


def calculate_age_score(age1: float, age2: float) -> float:
    """Calculate normalized score based on age difference."""
    diff = abs(age1 - age2)
    ratio = diff / MAX_AGE_DIFF
    if ratio > MAX_SCORE_RATIO:
        return MIN_SCORE_RATIO
    return MAX_SCORE_RATIO - ratio


def calculate_interests_score(
    interests1: list[str], interests2: list[str]
) -> tuple[float, list[str]]:
    """Calculate Jaccard similarity score for profile interests."""
    set1 = set(interests1)
    set2 = set(interests2)
    common = sorted(list(set1.intersection(set2)))
    union = set1.union(set2)
    if len(union) == MIN_INTERESTS_COUNT:
        return MIN_SCORE_RATIO, common
    score = len(common) / len(union)
    return score, common


def calculate_distance_score(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate normalized score based on geographic distance."""
    dlat = lat1 - lat2
    dlon = lon1 - lon2
    approx_km = math.sqrt(dlat * dlat + dlon * dlon) * 111.0
    ratio = approx_km / MAX_DISTANCE_KM
    if ratio > MAX_SCORE_RATIO:
        return MIN_SCORE_RATIO
    return MAX_SCORE_RATIO - ratio


def evaluate_compatibility(
    profile1: dict[str, Any], profile2: dict[str, Any]
) -> dict[str, Any]:
    """Calculate total compatibility metrics between two profiles."""
    age_sc = calculate_age_score(
        float(profile1.get("age", ZERO)), float(profile2.get("age", ZERO))
    )
    int_sc, common = calculate_interests_score(
        profile1.get("interests", []), profile2.get("interests", [])
    )
    dist_sc = calculate_distance_score(
        float(profile1.get("lat", ZERO)),
        float(profile1.get("lon", ZERO)),
        float(profile2.get("lat", ZERO)),
        float(profile2.get("lon", ZERO)),
    )
    total_val = (
        SCORE_WEIGHT_AGE * age_sc
        + SCORE_WEIGHT_INTERESTS * int_sc
        + SCORE_WEIGHT_DISTANCE * dist_sc
    )
    percent = round(total_val * MAX_PERCENT, 2)
    status_label = "UNLIKELY"
    if percent >= MATCH_THRESHOLD:
        status_label = "MATCH"
    elif percent >= POTENTIAL_THRESHOLD:
        status_label = "POTENTIAL"

    return {
        "user_1_id": profile1.get("id"),
        "user_2_id": profile2.get("id"),
        "common_interests": common,
        "compatibility_percent": percent,
        "status": status_label,
    }


def process_files(input_filepath: str, output_filepath: str) -> None:
    """Read input JSON file, calculate metrics, write output file."""
    with open(input_filepath, "r", encoding="utf-8") as f_in:
        payload = json.load(f_in)

    res = evaluate_compatibility(
        payload.get("user_1", {}), payload.get("user_2", {})
    )

    with open(output_filepath, "w", encoding="utf-8") as f_out:
        json.dump(res, f_out, ensure_ascii=False, indent=2)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Profile compatibility calculator"
    )
    parser.add_argument("-i", "--input", help="Path to input JSON file")
    parser.add_argument("-o", "--output", help="Path to output JSON file")
    parser.add_argument(
        "pos_input", nargs="?", help="Positional input JSON file"
    )
    parser.add_argument(
        "pos_output", nargs="?", help="Positional output JSON file"
    )
    return parser


def main() -> int:
    """Main execution point for CLI utility."""
    parser = build_arg_parser()
    args = parser.parse_args()

    in_file = args.input or args.pos_input
    out_file = args.output or args.pos_output

    if not in_file or not out_file:
        sys.stderr.write("Error: input and output files are required.\n")
        return EXIT_FAILURE

    try:
        process_files(in_file, out_file)
        return EXIT_SUCCESS
    except Exception as exc:
        sys.stderr.write(f"Error during execution: {exc}\n")
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
