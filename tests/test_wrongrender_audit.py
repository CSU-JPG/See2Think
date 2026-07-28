import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import wrongrender_audit as audit  # noqa: E402


def candidate(model, group, source, sample):
    return {
        "model": model,
        "task_group": group,
        "source_directory": source,
        "source_key": f"{source}::{sample}",
        "sample_id": str(sample),
    }


class WrongRenderAuditTests(unittest.TestCase):
    def test_task_group_mapping(self):
        self.assertEqual(audit.task_group_for_source("emma/physics"), "2D")
        self.assertEqual(audit.task_group_for_source("clevr_math/val"), "3D")
        self.assertEqual(audit.task_group_for_source("VLABench"), "Real")
        self.assertIsNone(audit.task_group_for_source("unknown"))

    def test_overall_label_rules(self):
        passed = {name: {"label": "Pass"} for name in audit.CRITERIA}
        partial = {**passed, "plausibility": {"label": "Partial"}}
        failed = {**partial, "task_relevance": {"label": "Fail"}}
        self.assertEqual(audit.overall_from_criteria(passed)[0], "Pass")
        self.assertEqual(audit.overall_from_criteria(partial)[0], "Partial")
        self.assertEqual(audit.overall_from_criteria(failed)[0], "Fail")

    def test_balanced_sampling_is_deterministic_and_unique(self):
        rows = [candidate("m", "2D", source, number) for source in ("math", "prism") for number in range(8)]
        used_one, used_two = set(), set()
        first = audit.take_balanced(rows, 6, audit.seeded_rng(2026, "cell"), used_one)
        second = audit.take_balanced(rows, 6, audit.seeded_rng(2026, "cell"), used_two)
        self.assertEqual([row["source_key"] for row in first], [row["source_key"] for row in second])
        self.assertEqual(len({row["source_key"] for row in first}), 6)
        self.assertEqual(set(row["source_directory"] for row in first), {"math", "prism"})

    def test_short_cell_does_not_borrow_from_other_cell(self):
        rows = [candidate("m", "2D", "math", 1), candidate("m", "2D", "math", 2)]
        selected = audit.take_balanced(rows, 10, audit.seeded_rng(2026, "short"), set())
        self.assertEqual(len(selected), 2)

    def test_missing_required_files_are_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = root / "wrong_render" / "m" / "math" / "one"
            case.mkdir(parents=True)
            (case / "q.md").write_text("Question only", encoding="utf-8")
            (case / "steps.md").write_text("**Step 1 (Text):** inspect", encoding="utf-8")
            discovered, skipped = audit.discover_cases(root, ["m"])
            self.assertEqual(discovered, [])
            self.assertEqual(len(skipped), 1)
            self.assertIn("original p0.png is missing", skipped[0]["reason"])

    def test_needs_review_excluded_by_default(self):
        records = [
            {"case_id": "a", "audit_set": "formal", "needs_review": False, "overall_label": "Pass"},
            {"case_id": "b", "audit_set": "formal", "needs_review": True, "overall_label": ""},
            {"case_id": "c", "audit_set": "pilot", "needs_review": False, "overall_label": "Pass"},
        ]
        included, excluded = audit.rows_for_stats(records, include_pilot=False)
        self.assertEqual([row["case_id"] for row in included], ["a"])
        self.assertEqual({row["exclusion_reason"] for row in excluded}, {"needs_review", "pilot"})

    def test_summary_rates(self):
        result = audit.stats([
            {"overall_label": "Pass"},
            {"overall_label": "Partial"},
            {"overall_label": "Fail"},
            {"overall_label": "Pass"},
        ])
        self.assertEqual(result["strict_pass_rate"], 0.5)
        self.assertEqual(result["pass_or_partial_rate"], 0.75)

    def test_annotation_update_replaces_same_case(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path = audit.annotation_path(directory, "ann_a")
            audit.write_jsonl(path, [{"case_id": "x", "audit_index": 1}])
            rows = audit.load_annotation_map(directory, "ann_a")
            rows["x"] = {"case_id": "x", "audit_index": 1, "general_note": "updated"}
            audit.write_jsonl(path, list(rows.values()))
            self.assertEqual(len(audit.read_jsonl(path)), 1)
            self.assertEqual(audit.read_jsonl(path)[0]["general_note"], "updated")


if __name__ == "__main__":
    unittest.main()
