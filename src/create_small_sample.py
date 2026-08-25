"""Create a reproducible CSV sample using bounded-memory streaming."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from config import settings


def create_small_sample(
    input_file: Path,
    output_file: Path,
    rows: int,
) -> int:
    """Copy the header and at most ``rows`` data records to a new CSV file."""

    if rows <= 0:
        raise ValueError("The number of sample rows must be greater than zero.")

    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")

    if not input_file.is_file():
        raise ValueError(f"Input path is not a regular file: {input_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    copied_rows = 0

    with input_file.open(
        mode="r",
        encoding=settings.CSV_ENCODING,
        newline=settings.CSV_NEWLINE,
    ) as source_handle, output_file.open(
        mode="w",
        encoding=settings.CSV_ENCODING,
        newline=settings.CSV_NEWLINE,
    ) as target_handle:
        reader = csv.reader(source_handle)
        writer = csv.writer(target_handle)

        try:
            header = next(reader)
        except StopIteration as error:
            raise ValueError("The input CSV file is empty.") from error

        if not header or all(not column.strip() for column in header):
            raise ValueError("The input CSV header is empty or invalid.")

        writer.writerow(header)

        for record in reader:
            writer.writerow(record)
            copied_rows += 1

            if copied_rows >= rows:
                break

    return copied_rows


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for sample creation."""

    parser = argparse.ArgumentParser(
        description=(
            "Create a reproducible bounded-memory sample from a large CSV."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.SOURCE_DATA_FILE,
        help="Path to the source CSV file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.SAMPLE_DATA_FILE,
        help="Path where the sample CSV will be written.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=settings.DEFAULT_SAMPLE_ROWS,
        help="Maximum number of data rows to copy.",
    )
    return parser


def main() -> int:
    """Run sample creation from the command line."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        copied_rows = create_small_sample(
            input_file=arguments.input,
            output_file=arguments.output,
            rows=arguments.rows,
        )
    except (FileNotFoundError, ValueError, OSError) as error:
        parser.error(str(error))
        return 2

    print("Small sample created successfully")
    print(f"Input file: {arguments.input.resolve()}")
    print(f"Output file: {arguments.output.resolve()}")
    print(f"Requested data rows: {arguments.rows}")
    print(f"Copied data rows: {copied_rows}")
    print("Memory strategy: streaming CSV reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
