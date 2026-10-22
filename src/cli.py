"""CLI utility for EAN-13 barcode generation in PDF format."""

import argparse
import json
import os
import sys
from typing import Any

from src.config import (
    BAR_HEIGHT,
    BAR_WIDTH,
    CHECKSUM_EVEN_WEIGHT,
    CHECKSUM_MODULO,
    EAN12_LENGTH,
    EAN13_LENGTH,
    EXIT_FAILURE,
    EXIT_SUCCESS,
    OFFSET_X,
    OFFSET_Y,
    ONE,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    STATE_SUCCESS,
    TOTAL_MODULES,
    ZERO,
)

L_CODE = (
    "0001101",
    "0011001",
    "0010011",
    "0111101",
    "0100011",
    "0110001",
    "0101111",
    "0111011",
    "0110111",
    "0001011",
)

G_CODE = (
    "0100111",
    "0110011",
    "0011011",
    "0100001",
    "0011101",
    "0111001",
    "0000101",
    "0010001",
    "0001001",
    "0010111",
)

R_CODE = (
    "1110010",
    "1100110",
    "1101100",
    "1000010",
    "1011100",
    "1001110",
    "1010000",
    "1000100",
    "1001000",
    "1110100",
)

FIRST_DIGIT_PARITY = (
    "LLLLLL",
    "LLGLGG",
    "LLGGLG",
    "LLGGGL",
    "LGLLGG",
    "LGGLLG",
    "LGGGLL",
    "LGLGLG",
    "LGLGGL",
    "LGGLGL",
)


def compute_ean13_checksum(digits12: str) -> int:
    """Compute standard EAN-13 check digit for 12 numeric digits."""
    clean = "".join(ch for ch in digits12 if ch.isdigit())
    if len(clean) < EAN12_LENGTH:
        raise ValueError("At least 12 numeric digits required")
    odd_sum = sum(int(clean[i]) for i in range(ZERO, EAN12_LENGTH, 2))
    even_sum = sum(int(clean[i]) for i in range(ONE, EAN12_LENGTH, 2))
    total = odd_sum + CHECKSUM_EVEN_WEIGHT * even_sum
    rem = total % CHECKSUM_MODULO
    if rem == ZERO:
        return ZERO
    return CHECKSUM_MODULO - rem


def normalize_ean13(raw_code: str) -> str:
    """Validate or complete 12/13-digit string into valid 13-digit EAN."""
    digits = "".join(ch for ch in str(raw_code) if ch.isdigit())
    if len(digits) == EAN12_LENGTH:
        chk = compute_ean13_checksum(digits)
        return f"{digits}{chk}"
    if len(digits) == EAN13_LENGTH:
        expected = compute_ean13_checksum(digits[:EAN12_LENGTH])
        actual = int(digits[EAN12_LENGTH])
        if actual != expected:
            raise ValueError("Invalid check digit")
        return digits
    raise ValueError("Code must have 12 or 13 digits")


def encode_ean13_bits(ean13: str) -> str:
    """Encode 13-digit EAN into 95-module binary barcode string."""
    first = int(ean13[ZERO])
    parity_pattern = FIRST_DIGIT_PARITY[first]
    left_bits = []
    for idx, p_type in enumerate(parity_pattern):
        d_val = int(ean13[ONE + idx])
        chunk = L_CODE[d_val] if p_type == "L" else G_CODE[d_val]
        left_bits.append(chunk)

    right_bits = []
    for idx in range(7, 13):
        d_val = int(ean13[idx])
        right_bits.append(R_CODE[d_val])

    full = (
        "101"
        + "".join(left_bits)
        + "01010"
        + "".join(right_bits)
        + "101"
    )
    if len(full) != TOTAL_MODULES:
        raise RuntimeError("Barcode bit length mismatch")
    return full


def _build_pdf_stream(ean13: str, bits: str) -> str:
    """Construct PDF graphics commands for barcode bars and caption."""
    stream_cmds = ["0 0 0 rg\n"]
    curr_x = OFFSET_X
    for b in bits:
        if b == "1":
            stream_cmds.append(
                f"{curr_x} {OFFSET_Y} {BAR_WIDTH} {BAR_HEIGHT} re f\n"
            )
        curr_x += BAR_WIDTH
    text_y = OFFSET_Y - 15
    stream_cmds.append(
        f"BT /F1 12 Tf {OFFSET_X + 20} {text_y} Td ({ean13}) Tj ET\n"
    )
    return "".join(stream_cmds)


def generate_barcode_pdf(ean13: str, bits: str, pdf_path: str) -> None:
    """Render vector EAN-13 barcode into standalone PDF document."""
    stream = _build_pdf_stream(ean13, bits)
    content_len = len(stream)

    o1 = "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    o2 = "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    o3 = (
        "3 0 obj\n<< /Type /Page /Parent 2 0 R "
        f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
        "/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 "
        "/BaseFont /Helvetica >> >> >> /Contents 4 0 R >>\nendobj\n"
    )
    o4 = (
        f"4 0 obj\n<< /Length {content_len} >>\n"
        f"stream\n{stream}endstream\nendobj\n"
    )

    head = "%PDF-1.4\n"
    p1 = len(head)
    p2 = p1 + len(o1)
    p3 = p2 + len(o2)
    p4 = p3 + len(o3)
    xref_pos = p4 + len(o4)
    xref = (
        f"xref\n0 5\n0000000000 65535 f \n"
        f"{p1:010d} 00000 n \n{p2:010d} 00000 n \n"
        f"{p3:010d} 00000 n \n{p4:010d} 00000 n \n"
    )
    trailer = (
        f"trailer\n<< /Size 5 /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    )

    with open(pdf_path, "wb") as f_pdf:
        content = head + o1 + o2 + o3 + o4 + xref + trailer
        f_pdf.write(content.encode("latin1"))


def process_ean13_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute barcode computation and produce PDF artifact."""
    raw_code = str(payload.get("code", "460123456789"))
    ean13 = normalize_ean13(raw_code)
    bits = encode_ean13_bits(ean13)

    pdf_out = str(payload.get("output_pdf", "barcode.pdf"))
    generate_barcode_pdf(ean13, bits, pdf_out)

    return {
        "raw_code": raw_code,
        "ean13": ean13,
        "check_digit": int(ean13[-1]),
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
        description="EAN-13 barcode PDF generator"
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
