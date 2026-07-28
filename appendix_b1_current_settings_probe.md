# Appendix B.1 Current Settings Probe

Date checked: 2026-07-22

This file records what can be recovered from the current See2Think workspace and the currently configured OpenAI-compatible endpoint. Secrets are intentionally omitted.

## API Metadata Probe

Configured endpoint in `config.sh`:

```text
OPENAI_BASE_URL=https://yunwu.ai/v1
```

Metadata query performed:

```text
GET https://yunwu.ai/v1/models
```

The endpoint returned 453 model IDs. Relevant visible IDs include:

```text
gpt-5.5
gpt-5.5-2026-04-24
o3
o3-2025-04-16
gpt-5.4
gpt-5.4-2026-03-05
```

Gemini-3.5-Flash IDs were not exposed by this endpoint's `/models` list. The run scripts use the request alias below, but the exact provider-side snapshot for that alias is not recoverable from `/models`.

```text
gemini-3.5-flash:floor
```

## Main Model Request Aliases Used By Scripts

The production run scripts set:

| Display model | Run label | Request model alias |
| --- | --- | --- |
| GPT-5.5 | `gpt-5.5` | `gpt-5.5:floor` |
| o3 | `o3` | `o3:floor` |
| Gemini 3.5 Flash | `gemini-3.5-flash` | `gemini-3.5-flash:floor` |

Note: some historical local directories and analysis files contain the string `gemini-3.5-flash`. That is a local bookkeeping label used by earlier scripts, not the API model name to report in the paper. The paper-facing model name should be `gemini-3.5-flash`.

The endpoint currently exposes date-stamped IDs for GPT-5.5 and o3:

| Request alias | Currently visible related dated ID |
| --- | --- |
| `gpt-5.5:floor` | `gpt-5.5-2026-04-24` |
| `o3:floor` | `o3-2025-04-16` |
| `gemini-3.5-flash:floor` | not exposed by `/models` |

Do not state that `:floor` definitely equals the dated ID unless the provider documents that mapping. The safe statement is: "The current endpoint exposes these related dated IDs."

## Decoding Parameters

Confirmed from `solve/auto_solve.py`:

```text
temperature: not explicitly passed
top_p: not explicitly passed
max_tokens: passed only if SEE2THINK_MAX_TOKENS is a positive integer
```

Current local shell did not have `SEE2THINK_MAX_TOKENS` set when checked. Some Qwen watchdog scripts set `SEE2THINK_MAX_TOKENS=16384`, but the closed-model 1.2K scripts do not hard-code it.

Current API metadata does not expose default temperature/top-p. A new chat call also would not reveal the provider's hidden defaults unless the provider includes them in request logs or responses.

## VAoT Budget And Action Handling

Confirmed from `solve/auto_solve.py`:

```text
max_steps default: 10
termination: stop when "Final Answer:" appears
Step 1 VAoT prompt rule: exactly one visual action object
Step 2+: text-only by default; request another action only if needed
```

Invalid or missing action handling:

```text
No separate invalid-action retry loop is implemented for malformed/missing VAoT action JSON.
If no action description is parsed, rendering is skipped for that step and the trajectory continues.
Renderer/API failures are retried, but invalid action formatting itself is not repaired by a dedicated retry rule.
```

## Renderer

Main renderer mode:

```text
mode=banana
renderer model: gemini-2.5-flash-image
renderer prompt: prompt/generate_image_prompt.txt
```

WrongRender image editor:

```text
model: gemini-2.5-flash-image
prompt: prompt/image_interference_prompt.txt
default interference: modify_key
```

Renderer resolution and edit parameters:

```text
Gemini image renderer: no explicit output resolution, seed, temperature, or edit strength is set in local code.
Qwen local image-edit path: qwen_image_edit_inference_steps default is 10, but this is not the main banana renderer path.
```

## Judge And Evaluation Calls

Evaluation result files record:

```text
answer_judge_model: gpt-5.4
process judge: GPT-5.4 in paper text
```

The local evaluation outputs record the judge model label but do not expose a date-stamped judge snapshot or explicit judge temperature/top-p/max_tokens. The endpoint currently exposes:

```text
gpt-5.4
gpt-5.4-2026-03-05
```

Again, do not claim that the alias used during the completed run was exactly the date-stamped ID unless provider logs confirm the alias mapping.

## Caption, Rewrite, And Checking Models

Recovered from the remote early workspace:

```text
caption generator model: gpt-4o
caption-only solvability reasoning model: gpt-4o
automatic checking model: gpt-4o
```

Evidence:

```text
remote script: v-jinpewang/yansiyu_workspace/See2Think/solve/check_question.py
remote launch script: v-jinpewang/yansiyu_workspace/See2Think/bin/check_question.sh
launch argument: --model gpt-4o
script default if no launch override is passed: parser.add_argument("--model", type=str, default="gpt-5")
```

The launch script overrides the parser default, so the recoverable run evidence should be reported as `gpt-4o`, not the parser default. The checking script uses `args.model` both for image-to-text captioning and for answer-validity checks: it first converts the image into a textual description and then checks whether the question can be solved from `Image Description + Question` alone. Early retained results are stored under:

```text
v-jinpewang/yansiyu_workspace/see2think/tasks/check_question/
```

These result JSON files store pass/fail validity flags but do not store the model name per item. The model evidence therefore comes from the retained launch script rather than the result JSON files.

Still not recovered from current local or remote logs:

```text
question rewrite model
```

## Retry, Timeout, And Empty Output

Confirmed from code:

```text
chat retries: 5 attempts
chat retry backoff: initial 1.0 second, factor 2.0
image generation retries: 5 attempts
base request sleep/jitter: SLEEP_TIME = 2 seconds
task timeout: SEE2THINK_TASK_TIMEOUT_SECONDS, set to 1200 in production scripts
empty text-only response: raises RuntimeError
task failure/timeout: logged by run_tasks.py and included in failed-task summary
```

## Random Seed

Main inference:

```text
No fixed global random seed is set for provider decoding or Gemini image generation.
```

Audit sampling:

```text
WrongRender quality-audit sampling seed: 2026
Other helper/audit scripts have their own script-level seeds.
```

## Manual QC

Human validation and WrongRender audit sections have explicit sample sizes and protocols. The benchmark construction manual QC item in Appendix A.4 still lacks a precise count of annotators/reviewers and a conflict-resolution rule in the current local evidence.
