"""Convert a CSV file to JSON."""
import csv
import json
import sys
from pathlib import Path

from helpers import report_usage


def convert(path):
    rows = list(csv.DictReader(open(path, newline="")))
    out = Path(path).with_suffix(".json")
    out.write_text(json.dumps(rows, indent=2))
    report_usage(len(rows))
    return out


if __name__ == "__main__":
    print(convert(sys.argv[1]))
