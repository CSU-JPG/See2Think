# Repository release checklist

Use this checklist before pushing See2Think to a public GitHub repository.

## Must not be committed

- Real API keys or endpoint tokens.
- `config.sh` with local credentials.
- Raw benchmark image folders.
- Generated trajectories, renders, logs, and retry queues.
- Paper PDFs or screenshot-heavy deliverables.
- Human annotation packets that contain large copied images.

These are ignored by `.gitignore`.

## Should be committed

- Source code in `solve/`, `convert/`, `eval/`, `scripts/`, and `viewer/`.
- Prompt templates in `prompt/`.
- Lightweight task manifests and metadata in `json/`.
- Reproducibility notes in `docs/`.
- `README.md`, `requirements.txt`, and example config files.

## Pre-push checks

```bash
git status --short --ignored
python -m compileall solve convert eval scripts -q
```

Run a secret scan over files that git would include:

```powershell
$patterns = @('sk-[A-Za-z0-9]{20,}', 'OPENAI_API_KEY=.*sk-', 'GEMINI_API_KEY=.*sk-', 'sig=', 'Bearer [A-Za-z0-9._-]{20,}')
$files = git ls-files --others --cached --exclude-standard
foreach ($f in $files) {
  if (Test-Path -LiteralPath $f -PathType Leaf) {
    Select-String -LiteralPath $f -Pattern $patterns -Encoding UTF8 -ErrorAction SilentlyContinue
  }
}
```

The helper string `sig=<hidden>` in `scripts/download_reusable_results_from_blob.py` is expected and is not a secret.
