#!/usr/bin/env python3
"""Ratchet coverage: bump fail_under to match actual coverage.

Parses coverage.xml produced by pytest-cov and updates the ``fail_under``
value in pyproject.toml whenever actual coverage exceeds the current
threshold.  This ensures the coverage bar can only go *up* over time.

The updated pyproject.toml is automatically ``git add``-ed so the change
is included in the commit that triggered the hook.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_XML = REPO_ROOT / "coverage.xml"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"

# Small buffer subtracted from actual coverage before ratcheting.
# Accounts for minor cross-environment differences (e.g. macOS vs Linux CI)
# where branch evaluation or platform-specific code paths cause the measured
# coverage to vary by a fraction of a percent.
MARGIN = 0.15

# Matches  fail_under = <number>  (int or float)
FAIL_UNDER_RE = re.compile(r"(fail_under\s*=\s*)([\d.]+)")


def get_actual_coverage() -> float:
    """Return the combined (line + branch) coverage percentage from the XML."""
    tree = ET.parse(COVERAGE_XML)
    root = tree.getroot()

    lines_valid = int(root.attrib["lines-valid"])
    lines_covered = int(root.attrib["lines-covered"])
    branches_valid = int(root.attrib.get("branches-valid", "0"))
    branches_covered = int(root.attrib.get("branches-covered", "0"))

    total = lines_valid + branches_valid
    covered = lines_covered + branches_covered

    if total == 0:
        return 100.0

    return (covered / total) * 100


def get_precision(text: str) -> int:
    """Read the ``[tool.coverage.report] precision`` setting."""
    match = re.search(r"precision\s*=\s*(\d+)", text)
    return int(match.group(1)) if match else 2


def floor_to_precision(value: float, precision: int) -> float:
    """Floor *value* to *precision* decimal places.

    Flooring (rather than rounding) avoids a ratcheted threshold that is
    marginally *above* the reproducible coverage, which would cause flaky
    failures on the next commit.
    """
    factor = 10**precision
    return math.floor(value * factor) / factor


def format_threshold(value: float) -> str:
    """Format the threshold as an int when possible, float otherwise."""
    if value == int(value):
        return str(int(value))
    return str(value)


def main() -> int:
    if not COVERAGE_XML.exists():
        print("ratchet-coverage: coverage.xml not found – skipping")
        return 0

    text = PYPROJECT_TOML.read_text()
    match = FAIL_UNDER_RE.search(text)
    if not match:
        print("ratchet-coverage: fail_under not found in pyproject.toml – skipping")
        return 0

    current_threshold = float(match.group(2))
    precision = get_precision(text)
    actual = floor_to_precision(get_actual_coverage() - MARGIN, precision)

    if actual <= current_threshold:
        print(
            f"ratchet-coverage: coverage {actual}% ≤ threshold "
            f"{current_threshold}% – no update needed"
        )
        return 0

    new_value = format_threshold(actual)
    new_text = FAIL_UNDER_RE.sub(rf"\g<1>{new_value}", text, count=1)
    PYPROJECT_TOML.write_text(new_text)

    # Stage the updated file so it's included in the in-flight commit.
    subprocess.run(
        ["git", "add", str(PYPROJECT_TOML)],
        check=True,
        cwd=REPO_ROOT,
    )

    print(f"ratchet-coverage: threshold ratcheted {current_threshold}% → {actual}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
