"""Utility functions for VideoAgent services."""

import csv
import io
import json


def csv_to_json(csv_content: str) -> str:
    """Convert CSV content string to JSON string.

    Args:
        csv_content: CSV data as string

    Returns:
        JSON string representation of the CSV data
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    return json.dumps(rows, indent=2)
