"""Writes the ground-truth lab values behind every generated lab report, for measuring extraction accuracy.

    backend/.venv/bin/python scripts/patient_files/export_truth.py

Output: backend/app/evals/data/lab_truth.json  — {"<patient folder>/<file>": [[test, result, unit, range, method?], ...]}
Nothing is rendered, so the committed PDFs are left untouched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cohort_a  # noqa: E402
import cohort_b  # noqa: E402
import cohort_c  # noqa: E402
from build import folder_name  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "backend" / "app" / "evals" / "data" / "lab_truth.json"


def main() -> int:
    truth = {}
    for make in cohort_a.PATIENTS + cohort_b.PATIENTS + cohort_c.PATIENTS:
        p = make()
        for d in p.docs:
            if d.kind == "lab_report" and d.truth:
                truth[f"{folder_name(p)}/{d.path}"] = [list(r[:4]) for r in d.truth]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(truth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(truth)} lab reports, {sum(len(v) for v in truth.values())} values -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
