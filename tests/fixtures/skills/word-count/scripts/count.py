"""Count words in text files."""
import json
import sys
from pathlib import Path


def count_folder(folder):
    """Count words per .txt file and write report.json."""
    folder = Path(folder)
    counts = {}
    for path in sorted(folder.glob("*.txt")):
        words = path.read_text(encoding="utf-8").split()
        counts[path.name] = len(words)
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    report = {"files": [{"name": name, "words": total} for name, total in ranked]}
    (folder / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    print(json.dumps(count_folder(sys.argv[1]), indent=2))
