# Appendix B.1 Reproducibility Checklist

| Item | Setting |
|---|---|
| GPT-5.5 API version | `gpt-5.5-2026-04-24` |
| o3 API version | `o3-2025-04-16` |
| Gemini 3.5 Flash API version | `gemini-3.5-flash` |
| Temperature | Not explicitly set; provider default used |
| Top-p | Not explicitly set; provider default used |
| Max tokens | Passed only when `SEE2THINK_MAX_TOKENS` is set to a positive integer |
| Maximum VAoT rounds | 10 |
| Invalid action retry | No dedicated invalid-action retry loop |
| Faithful renderer model | `gemini-2.5-flash-image` |
| WrongRender editor model | `gemini-2.5-flash-image` |
| Renderer resolution | Not explicitly set; provider default used |
| Renderer edit parameters | Not explicitly set; provider default used |
| Caption generator model | `gpt-4o` |
| Caption-only solvability reasoning model | `gpt-4o` |
| Question rewrite model | Not recoverable from retained logs/scripts |
| Automatic checking model | `gpt-4o` |
| GPT-5.4 judge model | `gpt-5.4-2026-03-05` |
| GPT-5.4 judge temperature/top-p/max tokens | Not explicitly recorded |
| Main random seed | No fixed global seed |
| WrongRender audit sampling seed | 2026 |
| API failure handling | Chat requests retried up to 5 times with exponential backoff |
| Renderer failure handling | Image generation retried up to 5 times |
| Timeout handling | Controlled by `SEE2THINK_TASK_TIMEOUT_SECONDS`; unset or 0 means no runner-level timeout |
| Empty output handling | Empty text-only response raises an error; failed tasks are logged for retry |
| Benchmark manual QC annotators | To be specified |
| Benchmark manual QC conflict resolution | To be specified |

