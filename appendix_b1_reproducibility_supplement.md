# Appendix B.1 Reproducibility Supplement

This note supplements Appendix B.1 in `See2Think-7.20.pdf`. It records implementation details that are useful for a reproducibility checklist and separates confirmed settings from fields that must be filled from provider-side run logs.

## Current Gap Status

After checking the local code and available logs, the B.1 supplement is mostly complete for implementation-level reproducibility. The main remaining gap is not a missing hard-coded value in the code: the main chat request does not pass `temperature` or `top_p` at all. Therefore the defensible paper statement is that temperature and top-p were not explicitly overridden and provider/default endpoint decoding was used.

Current API calls cannot reliably recover the effective temperature/top-p used in the previous completed runs. A new call would only reflect the current endpoint behavior, and standard chat/model responses do not report the provider's hidden default decoding parameters. Exact provider snapshot IDs and hidden endpoint defaults must come from provider-side request logs, dashboard exports, or raw request dumps if those were enabled at run time.

## Confirmed From Local Code

### Inference Client

- Main inference entry point: `solve/auto_solve.py`.
- Batch runner: `solve/run_tasks.py`.
- Prompt directory: `newprompt/`.
- Setting-to-prompt mapping:
  - `text_cot` -> `newprompt/see2think_text_cot.txt`
  - `vaot_no_render` -> `newprompt/see2think_vaot_no_render.txt`
  - `vaot_full` -> `newprompt/see2think_vaot_full.txt`
  - `vaot_wrong_render` -> `newprompt/see2think_vaot_wrong_render.txt`
- Chat requests are sent through an OpenAI-compatible `chat.completions.create` interface.
- `SEE2THINK_REQUEST_MODEL` can override the CLI model name at request time.

### Decoding Parameters

- `temperature`: not explicitly set in the main chat request.
- `top_p`: not explicitly set in the main chat request.
- `max_tokens`: only passed if `SEE2THINK_MAX_TOKENS` is set to a positive integer.
- If `SEE2THINK_MAX_TOKENS` is unset or `0`, the client does not pass `max_tokens`.
- Therefore, for the main runs, temperature and top-p should be reported as provider/default endpoint settings unless the provider dashboard or raw request logs show otherwise.

### Interaction Budget

- Maximum VAoT rounds: `--max_steps`, default `10`.
- VAoT Step 1: prompt requires exactly one visual-action object.
- Step 2 and later: model may continue text-only or request another visual action.
- Termination: trajectory stops when `Final Answer:` appears.
- Default context: accumulated previous steps are passed back to the model.
- Optional context mode: `--step_wise_context` passes only the previous step.

### Renderer

- Main visual rendering mode in current scripts: `banana`.
- Faithful renderer model in code: `gemini-2.5-flash-image`.
- Renderer prompt: `prompt/generate_image_prompt.txt`.
- Renderer receives the original/current image plus the extracted JSON visual-action guidance.
- Original image is saved as `p0.png`; rendered states are saved as `p1.png`, `p2.png`, etc.
- Text trajectory is saved as `steps.md`; question and reference answer are saved as `q.md`.

### WrongRender

- For `--setting vaot_wrong_render`, if no interference is explicitly supplied, the code sets:

```python
interference = "modify_key"
```

- WrongRender image-edit prompt: `prompt/image_interference_prompt.txt`.
- `modify_key` asks the image editor to modify task-relevant visual content so that the result becomes misleading for problem solving.
- Interference is applied to Step 1 and every third rendered step.
- The reasoning model is not told that returned visual feedback is corrupted.

### Retries and Timeout Handling

- Chat request retries: up to `5` attempts.
- Chat retry schedule: exponential backoff, initial delay `1.0` second, factor `2.0`.
- Image generation retries: up to `5` attempts.
- Global request sleep/jitter base: `SLEEP_TIME = 2` seconds.
- Batch per-task timeout: controlled by `SEE2THINK_TASK_TIMEOUT_SECONDS`.
- If `SEE2THINK_TASK_TIMEOUT_SECONDS` is unset or `0`, the runner imposes no hard timeout.
- Qwen handoff notes record `SEE2THINK_TASK_TIMEOUT_SECONDS=1200`.
- Empty text-only responses raise an error instead of being counted as completed.

### Randomness

- Main inference does not set a global random seed for provider decoding or image generation.
- The runner uses fixed task manifests for sample identity and order.
- Request-delay jitter uses Python random without a fixed seed.
- WrongRender audit sampling uses explicit script-level seed `2026`.

## Items Not Recoverable From The Local Code Alone

These should not be invented in the paper. They need provider run logs, API dashboard records, or raw request dumps:

- exact provider API snapshot/version for GPT-5.5, o3, and Gemini 3.5 Flash;
- exact provider-side default `temperature`;
- exact provider-side default `top_p`;
- any hidden provider-side max-output cap when `max_tokens` was not passed;
- exact backend revision/date for remote hosted models if the provider uses mutable aliases;
- question-rewrite model if those preprocessing logs are not stored locally.

Recovered preprocessing models:

- Caption generator model: `gpt-4o`.
- Caption-only solvability reasoning model: `gpt-4o`.
- Automatic checking model: `gpt-4o`.
- Evidence: the retained remote launch script `v-jinpewang/yansiyu_workspace/See2Think/bin/check_question.sh` calls `solve/check_question.py` with `--model gpt-4o`. The checking script uses `args.model` for both image captioning and caption-only answer-validity checks. Its parser default is `gpt-5`, but the retained launch command overrides that default.
- Retained early outputs are under `v-jinpewang/yansiyu_workspace/see2think/tasks/check_question/`; those JSON files store validity flags but not per-item model names.

## Can The API Be Queried Afterward For These Defaults?

Usually no.

For a completed run, normal chat-completion responses do not reliably expose the effective default `temperature`, `top_p`, or immutable model snapshot. The API call only knows what was sent in the request and what the provider returns in the response. If the request omitted `temperature` and `top_p`, the local code cannot reconstruct the effective defaults afterward.

What can be checked:

- local request construction: whether the client explicitly passed `temperature`, `top_p`, and `max_tokens`;
- saved request dumps, if `SEE2THINK_DUMP_MESSAGES=1` was enabled during the run;
- provider dashboard or billing/export logs, if they expose model snapshot or request parameters;
- raw server logs from a local vLLM/Qwen endpoint, if enabled.

What should be written if no raw provider record exists:

```text
We did not override temperature or top-p in the inference client; the provider/default endpoint decoding settings were used. Maximum output length was controlled only when SEE2THINK_MAX_TOKENS was set. Exact mutable API snapshot identifiers should be taken from provider-side run logs when available.
```

## Suggested Appendix B.1 Insert

```text
Implementation details. We run all inference through an OpenAI-compatible chat-completion interface using the prompts in Appendix B.2-B.5. The client does not explicitly set temperature or top-p; unless otherwise specified by the endpoint wrapper, provider-default decoding is used. A max-tokens value is passed only when SEE2THINK_MAX_TOKENS is set to a positive integer. VAoT trajectories use a maximum interaction budget of 10 rounds and terminate early when the model emits "Final Answer:". Step 1 in VAoT settings requires exactly one structured visual action; later steps may continue text-only unless additional visual evidence is needed.

Rendering details. The faithful renderer receives the current image state and the structured action extracted from the model response. In the main image-rendering mode, rendered visual states are produced with gemini-2.5-flash-image using the renderer prompt in prompt/generate_image_prompt.txt. Original images are saved as p0.png, rendered states as p1.png, p2.png, etc., and text trajectories as steps.md.

WrongRender details. VAoT-WrongRender uses the same reasoning prompt and interaction budget as VAoT. In the implementation, the default WrongRender interference mode is modify_key. The image editor is prompted to modify task-relevant visual content so that the returned state provides misleading evidence while preserving a plausible renderer style. Corruption is applied to the first rendered step and every third rendered step thereafter. The reasoning model is not informed that the visual feedback has been corrupted.

Failure handling. Chat requests are retried up to five times with exponential backoff. Image generation is also retried up to five times. Per-task process timeouts are controlled by SEE2THINK_TASK_TIMEOUT_SECONDS; unset or zero disables the runner-level timeout. Failed, timed-out, or empty-output tasks are logged and exported into retry manifests rather than silently treated as completed.
```
