"""CLI utility for EAN-13 barcode generation in PDF format."""

import argparse
import json
import os
import sys
from typing import Any

from barcode import EAN13
from barcode.writer import ImageWriter

from src.config import (
    EAN12_LENGTH,
    EXIT_FAILURE,
    EXIT_SUCCESS,
    STATE_SUCCESS,
    ZERO,
)


def compute_ean13_code(raw_code: str) -> str:
    """Validate and compute full 13-digit EAN code using barcode library."""
    digits = "".join(ch for ch in str(raw_code) if ch.isdigit())
    if len(digits) < EAN12_LENGTH:
        raise ValueError("At least 12 digits required")
    base_12 = digits[:EAN12_LENGTH]
    ean = EAN13(base_12)
    return ean.get_fullcode()


def generate_barcode_pdf(raw_code: str, pdf_path: str) -> str:
    """Generate EAN-13 barcode image and save to PDF file."""
    digits = "".join(ch for ch in str(raw_code) if ch.isdigit())
    if len(digits) < EAN12_LENGTH:
        raise ValueError("At least 12 digits required")
    base_12 = digits[:EAN12_LENGTH]
    ean = EAN13(base_12, writer=ImageWriter())
    img = ean.render()
    img.save(pdf_path, "PDF")
    return ean.get_fullcode()


def process_ean13_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute barcode computation and produce PDF artifact."""
    raw_code = str(payload.get("code", "460123456789"))
    pdf_out = str(payload.get("output_pdf", "barcode.pdf"))
    full_ean = generate_barcode_pdf(raw_code, pdf_out)
    chk_digit = int(full_ean[-1])

    return {
        "raw_code": raw_code,
        "ean13": full_ean,
        "check_digit": chk_digit,
        "pdf_path": pdf_out,
        "status": STATE_SUCCESS,
    }


def process_files(input_filepath: str, output_filepath: str) -> None:
    """Read task configuration file and write barcode metadata."""
    with open(input_filepath, "r", encoding="utf-8") as f_in:
        payload = json.load(f_in)

    if "output_pdf" not in payload:
        base_dir = os.path.dirname(output_filepath) or "."
        stem = os.path.splitext(os.path.basename(output_filepath))[ZERO]
        payload["output_pdf"] = os.path.join(base_dir, f"{stem}.pdf")

    res = process_ean13_task(payload)
    with open(output_filepath, "w", encoding="utf-8") as f_out:
        json.dump(res, f_out, ensure_ascii=False, indent=2)


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct argument parser for CLI tool."""
    parser = argparse.ArgumentParser(
        description="EAN-13 barcode PDF generator using python-barcode"
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
    """Main CLI execution entry point."""
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
