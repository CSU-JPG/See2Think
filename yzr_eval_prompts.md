# See2Think Eval Prompts

This file collects the two evaluation prompts requested: the answer-accuracy judge prompt and the original process-judge prompt.

## Accuracy / Answer Judge Prompt

~~~python
def build_prompt(row: dict[str, Any]) -> str:
    return f"""You are a strict answer evaluator for a multimodal reasoning benchmark.

Judge whether the model's final answer is semantically correct with respect to the reference answer.

Question:
{row.get("question", "")}

Reference answer:
{row.get("ground_truth", "")}

Model final answer:
{row.get("final_answer", "")}

Rules:
1. Ignore harmless formatting differences, units formatting, LaTeX wrappers, punctuation, and equivalent wording.
2. For math, accept algebraically equivalent expressions and numerically equivalent answers when the intended quantity matches.
3. For multiple-choice questions, accept either the correct option letter or the correct option text.
4. If the model gives extra claims that contradict the reference, mark it incorrect.
5. If the model answer is empty, evasive, or says it cannot answer, mark it incorrect.
6. Be strict about counts, directions, relations, and named entities.

Return only a JSON object with:
{{
  "correct": true or false,
  "reason": "brief explanation"
}}
"""


~~~

## Process Judge Prompt with Key-Step Selection

Source: neweval/process_judge_prompt.txt

~~~text
You are an expert evaluator for multimodal reasoning trajectories.

You will evaluate a Visual Action-of-Thought (VAoT) trajectory. The model solves a visual reasoning problem by alternating between textual thoughts, visual actions, rendered visual states, and subsequent reasoning.

Your task is to evaluate ONLY the VAoT-Full trajectory. Do NOT compare it with Text-CoT, VAoT-NoRender, or VAoT-WrongRender.

Question:
{question}

Ground-truth answer:
{ground_truth}

Model final answer:
{final_answer}

Trajectory:
{trajectory_text}

Please first select the key visual step, then evaluate that selected step along three dimensions.

0. Key Visual Step Selection:
Identify the single visual step that is most relevant to the final reasoning or most directly exposes the failure source.
If there is no effective visual operation, use null.

1. Action Relevance:
Does the model choose visual actions that are useful for solving the task?
Score 0 / 0.5 / 1.
- 1: The visual action directly targets task-relevant evidence and is useful for solving the question.
- 0.5: The visual action is partially relevant, weakly targeted, or contains unnecessary but not harmful operations.
- 0: The visual action is irrelevant, generic, decorative, or does not meaningfully support the task.

2. Render Faithfulness:
Are the rendered visual states faithful to the intended visual actions?
Score 0 / 0.5 / 1.
- 1: The rendered visual state faithfully executes the intended action.
- 0.5: The rendering partially matches the action, but has noticeable ambiguity, imprecision, or minor errors.
- 0: The rendering is missing, wrong, misleading, or inconsistent with the intended action.

3. Feedback Uptake:
Does the subsequent reasoning actually use the rendered visual states?
Score 0 / 0.5 / 1.
- 1: Subsequent reasoning clearly uses the rendered visual state as evidence.
- 0.5: Subsequent reasoning weakly or implicitly uses the rendered state, but still relies mostly on text priors.
- 0: Subsequent reasoning ignores the rendered state or continues independently of it.

Return ONLY valid JSON in the following format:

{{
  "key_step_id": <step id or null>,
  "key_step_reason": "<short explanation>",
  "action_relevance": {{
    "score": <0, 0.5, or 1>,
    "reason": "<short explanation>"
  }},
  "render_faithfulness": {{
    "score": <0, 0.5, or 1>,
    "reason": "<short explanation>"
  }},
  "feedback_uptake": {{
    "score": <0, 0.5, or 1>,
    "reason": "<short explanation>"
  }},
  "overall_failure_source": "<action_relevance | render_faithfulness | feedback_uptake | none | unclear>",
  "summary": "<one-sentence diagnostic summary>"
}}
~~~
