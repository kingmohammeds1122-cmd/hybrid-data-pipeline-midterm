"""Automatic processing-engine selection based on input-file size."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from config import settings


@dataclass(frozen=True)
class RoutingDecision:
    """Immutable result of the file-routing decision."""

    file_path: Path
    file_size_bytes: int
    file_size_mb: float
    threshold_mb: int
    engine: str
    reason: str


def get_file_size_bytes(file_path: Path) -> int:
    """Return the file size in bytes, or raise a clear error."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Input file does not exist: {file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"Input path is not a regular file: {file_path}"
        )

    return file_path.stat().st_size


def route_file(file_path: Path) -> RoutingDecision:
    """Select Python Batch or PySpark according to the official threshold."""

    resolved_file_path = file_path.expanduser().resolve()
    file_size_bytes = get_file_size_bytes(resolved_file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    threshold_mb = settings.SMALL_FILE_THRESHOLD_MB

    if file_size_mb <= threshold_mb:
        engine = "python_batch"
        reason = (
            f"file size {file_size_mb:.2f} MB is less than or equal to "
            f"the threshold {threshold_mb} MB"
        )
    else:
        engine = "pyspark"
        reason = (
            f"file size {file_size_mb:.2f} MB is greater than "
            f"the threshold {threshold_mb} MB"
        )

    return RoutingDecision(
        file_path=resolved_file_path,
        file_size_bytes=file_size_bytes,
        file_size_mb=file_size_mb,
        threshold_mb=threshold_mb,
        engine=engine,
        reason=reason,
    )


def print_routing_decision(decision: RoutingDecision) -> None:
    """Print a human-readable routing decision for auditability."""

    print("File Router Decision")
    print(f"Input file: {decision.file_path}")
    print(f"File size: {decision.file_size_bytes:,} bytes")
    print(f"File size: {decision.file_size_mb:.2f} MB")
    print(f"Threshold: {decision.threshold_mb} MB")
    print(f"Selected engine: {decision.engine}")
    print(f"Reason: {decision.reason}")


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Select python_batch or pyspark based on the input CSV size."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.SOURCE_DATA_FILE,
        help=(
            "Path to the input CSV. Defaults to the configured large file."
        ),
    )
    return parser


def main() -> int:
    """Run the file router from the command line."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        decision = route_file(arguments.input)
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))
        return 2

    print_routing_decision(decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
