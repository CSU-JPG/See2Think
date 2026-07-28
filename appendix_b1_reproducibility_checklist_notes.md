# Notes For Appendix B.1 Reproducibility Checklist

- Gemini 3.5 Flash is reported as `gemini-3.5-flash` because the endpoint did not expose a dated snapshot ID.
- Temperature, top-p, renderer resolution, and renderer edit parameters were not explicitly passed in local code, so exact provider-side defaults are not recoverable from retained logs.
- `max_tokens` is controlled by `SEE2THINK_MAX_TOKENS`; if unset or 0, it is not passed.
- `gpt-4o` for caption generation, caption-only solvability, and automatic checking is supported by the retained remote launch script `See2Think/bin/check_question.sh`, which passes `--model gpt-4o`.
- The question rewrite model was not found in retained local or remote scripts/logs.
- Benchmark manual QC annotator count and conflict-resolution rule need to be filled from the actual dataset construction protocol.

