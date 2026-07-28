# WrongRender Quality Audit

This module is a human-only quality-control workflow for VAoT-WrongRender visual states. It does not call an LLM, show model answers, show post-WrongRender reasoning, or use automatic judge scores in the annotation page.

## Annotation rules

- Judge the WrongRender image, not whether the model answered correctly.
- A render is not automatically Pass because it misled the model; broad unrelated edits can still make it Fail.
- A polished render can still Fail when it does not change task-relevant evidence.
- Use Partial for a result that is usable but not clean. If evidence or metadata is insufficient, leave a note and select `Unable to judge / metadata missing`; it is excluded from formal statistics by default.
- Do not infer quality labels from model answers, correctness, or post-WrongRender reasoning. Those fields are deliberately unavailable in the UI.

## Commands

Create the formal 3 × 3 × 10 audit plus ten calibration cases:

```powershell
python scripts/wrongrender_audit.py sample `
  --input-root final_results_1200 `
  --models gpt-5.5 o3 gemini-3.5-flash `
  --per-cell 10 --seed 2026 --pilot-size 10 `
  --output-dir audits/wrongrender_quality_90
```

Run the local annotation page:

```powershell
python scripts/wrongrender_audit.py serve `
  --audit-dir audits/wrongrender_quality_90 `
  --annotator annotator_a --port 8765
```

Open `http://127.0.0.1:8765/`. If `--annotator` is omitted, the page requires an annotator ID before it permits annotation. Every annotator writes only to `annotations/<annotator_id>.jsonl`; saving a case replaces that annotator's previous record for the same case rather than adding a duplicate record.

Create summaries:

```powershell
python scripts/wrongrender_audit.py summarize --audit-dir audits/wrongrender_quality_90
```

The ten pilot cases are separate in `pilot_manifest.jsonl` and excluded from the formal statistics by default. Use `--include-pilot` only when explicitly desired.

## Bundle layout

```text
audits/wrongrender_quality_90/
  manifest.jsonl
  pilot_manifest.jsonl
  sampling_report.json
  assets/<case_id>/
  annotations/<annotator_id>.jsonl
  summaries/
```

Images and trajectory markdown files are copied into `assets/` with relative manifest paths. Source paths are retained in the manifest; source experiment outputs are never edited.

See `criteria_guideline.md` and `annotation_schema.json` for the rubric and stored annotation format.
