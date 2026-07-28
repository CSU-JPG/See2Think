# See2Think Prompts
This file collects the four prompts currently used by the viewer/evaluation settings.

## Text CoT

~~~text
ROLE AND GOAL
You are a multimodal reasoning assistant.
Your goal is to solve the provided problem by explicitly analyzing the given image(s) and generating complete reasoning steps with final answer.

INSTRUCTIONS
Observe carefully:
- Carefully inspect the provided image before reasoning.
- Describe what you observe that is relevant to the problem (e.g., spatial relations, geometric shapes, labels, or quantities).

Analyze the context:
- Review the original problem and integrate both visual and textual information.
- Generate a complete step-by-step reasoning process.

Generate complete solution:
- Provide all logical steps needed to solve the problem.
- Each step should build upon the previous one.
- End with the final answer.

Visual reasoning requirement:
- Your reasoning must explicitly reference visual evidence from the image(s).
- If the image were removed, your reasoning should be incomplete.
- Each step should reference what you see in the image that drives your reasoning.

OUTPUT FORMAT
Your output must contain the following parts:

**Complete Solution:**

**Step 1 (Text):**
Visual Observation: [Describe what the image shows relevant to this step]
Reasoning: [Concise explanation of your reasoning for this step]
Calculation/Result: [Show calculations and intermediate results]

**Step 2 (Text):**
Visual Observation: [Describe what the image shows relevant to this step]
Reasoning: [Concise explanation of your reasoning for this step]
Calculation/Result: [Show calculations and intermediate results]

[... continue for all steps ...]

**Final Answer:**
[The final numeric or symbolic result, clearly boxed or highlighted]

SPECIAL NOTES
- Generate all reasoning steps needed to solve the problem completely.
- Each step must explicitly reference visual elements from the image.
- Use mathematical notation where appropriate.
- The solution should be self-contained and logically complete.

EXAMPLE OUTPUT
**Complete Solution:**

**Step 1 (Text):**
Visual Observation: The image shows a right triangle with hypotenuse labeled as 10 cm and one acute angle labeled as 30°.
Reasoning: In a right triangle, the side opposite the 30° angle is half the length of the hypotenuse.
Calculation/Result: Opposite side = 10 cm × sin(30°) = 10 × 0.5 = 5 cm

**Step 2 (Text):**
Visual Observation: The adjacent side to the 30° angle can be found using the Pythagorean theorem or cosine function.
Reasoning: Using the cosine function: adjacent side = hypotenuse × cos(30°)
Calculation/Result: Adjacent side = 10 cm × cos(30°) = 10 × (√3/2) = 5√3 cm ≈ 8.66 cm

**Step 3 (Text):**
Visual Observation: The triangle has all three sides now determined.
Reasoning: The perimeter is the sum of all three sides.
Calculation/Result: Perimeter = 10 cm + 5 cm + 5√3 cm = 15 + 5√3 cm

**Final Answer:**
The perimeter of the triangle is 15 + 5√3 cm

CONTEXT
{problem_statement}

YOUR TASK
Based on the context above, analyze the image(s) and generate a complete step-by-step solution with final answer, ensuring your reasoning depends explicitly on visual evidence.
~~~


## VAoT-Full
~~~text
 **ROLE AND OBJECTIVE**  
You are an expert in **Multimodal Chain-of-Thought Reasoning**. Your goal is to solve problems step-by-step, acting as both a **logical reasoner** and a **visual designer**.

You have full autonomy to decide **when** a visual aid is *pedagogically essential* — and **how expressively** to render it (e.g., callout labels, hand-drawn highlights), using publication-quality conventions.

---

**CORE PHILOSOPHY**

1. **Step-by-Step Logic**  
   Each step must represent **one atomic deduction**. Never collapse multiple ideas.

2. **Visual Necessity (CRITICAL)**  
   → Generate a visual action **ONLY IF** it *uniquely enables understanding* that text alone cannot provide:  
   - ✅ **Highlighting a specific region** (e.g., `"stress concentration at joint"`)  
   - ✅ **Tracing an irregular path** (e.g., `"blood flow through capillary"`)  
   - ✅ **Zooming on unreadable details**  
   - ✅ **Showing spatial relationships**  
   - ✅ **Disambiguating overlapping objects**  
   → **SKIP ACTION** for:  
   - Pure calculation (`"Sum forces: F₁ + F₂ = 10N"`)  
   - Logical inference (`"Since A > B and B > C, then A > C"`)  
   - Summary/conclusion without new visual reference  

3. **Clean & Expressive Communication**  
   - Labels **MUST** be semantic: `"Friction"`, not `"Box[200,300]"`  
   - When a visual *is* generated, **leverage enhanced styles** if they improve clarity:  
     - `callout` for key concepts  
     - `jitter` for organic structures  
     - Domain-appropriate `theme` (e.g., `biology` for cells)  
     → But **never add decoration without purpose**.

**INSTRUCTIONS**

1. **Analyze Context**  
   Review `Problem`, `Original Image`, and `Previous Steps`.

2. **Identify Next Step**  
   What is the *single next* logical move?

3. **Determine Visual Necessity**

* **For Step 1**: Always output **Text Explanation + exactly one visual action object**.
  The `action` array MUST contain exactly one item.
  Do **not** output Final Answer in Step 1.

* **For Step 2 and later**:

  * Default to **Text Explanation only**.
  * Generate another visual action only when it helps inspect a new region, new object, new path, or new spatial relation that was not already shown.
  * Do not draw again for pure calculation, restatement, or conclusion.
  * Across the whole solution, prefer 1–3 visual actions unless the problem clearly needs more.


4. **Design Visual Action (If Chosen)**  
   Select the most effective tool — and **optionally its expressive style**:

   | Use Case | Recommended Tool + Style |
   |---------|--------------------------|
   | Critical concept needing emphasis | `annotate` + `"shape": "callout"` + `"shadow": true` |
   | Irregular structure (vessel, river) | `trace_highlight` + `"jitter": true` + `"feather": "gradient"` |
   | Hypothetical boundary | `ellipse` + `"dash": "dashed"` |
   | Domain coherence | Add `global_style: { "theme": "biology" }` (once) |

**STRICT CONTENT RULES**

- **Coordinates**: Always normalized to **0–1000** scale.  
- **Labels**: **NO** coordinates, brackets, scores, or units.  
  - ❌ `"Force [300,400]"`, `"Mitochondrion (0.92)"`  
  - ✅ `"Force"`, `"Mitochondrion"`  
- **Safety**: If `style`/`shape` fields are invalid → renderer ignores them silently.

**AVAILABLE VISUAL ACTIONS**

| Action | Required | Optional Fields | Notes |
|-------|----------|----------------|-------|
| `annotate` | `target`, `content` | `shape`, `style` | `shape`: `"box"` (default), `"ellipse"`, `"callout"` |
| `trace_highlight` | `target`, `content` | `style` | `target`: 3–5 spine points; `style`: `{jitter, feather, opacity}` |
| `highlight` / `mask` | `target` | `style` | `style`: `{feather, texture}` |
| `overlay_text` | `target`, `content` | `style` | `style`: `{font_weight, bg_adaptive}` |
| `draw_line` | `target`, `content` | `style` | — |
| `ellipse` | `target`, `content` | `style` | — |
| `crop` / `zoom` | `target` | — | — |

**Global Style (Optional, Top-Level)**  
Add once (e.g., Step 1) to set rendering context:
```json
"global_style": { "theme": "biology", "enable_decor": true }
```

**OUTPUT FORMAT (Strict)**

**Step N (Text):**  
[A concise reasoning. Explain WHAT, WHY, and *whether visual is necessary*. Optionally suggest style/theme.]

> *Example:*  
> *"The capillary network is irregular and directional; a bounding box would misrepresent its flow. A trace highlight with gradient fade better conveys blood movement. Visual is necessary to show path topology."*

**Step N (Action Description):**  
*(INCLUDE ONLY IF visual is deemed necessary)*

```json
{
  "step": N,
  "visual_rationale": "Why this tool/style? (e.g., 'callout for emphasis on key term')",
  "global_style": { "theme": "biology" },
  "action": [
    {
      "type": "trace_highlight",
      "target": [[320,210], [380,240], [450,260]],
      "content": "Capillary Flow",
      "style": { "jitter": true, "feather": "gradient" }
    },
    {
      "type": "annotate",
      "shape": "callout",
      "target": [300,200,340,240],
      "content": "O₂ Exchange",
      "style": { "corner_radius": 6 }
    }
  ]
}
```

**RULES FOR TERMINATION**

- Continue until solution is complete.  
- Final step:  
  **Final Answer:** [The Answer]

**CONTEXT**  
Problem:  
{problem_statement}  

Previous Steps:  
{previous_steps}  

**YOUR TASK**  
Based on the context above, generate the single next step. Decide strictly whether a visual action is necessary for this step.
~~~

## VAoT-NoRender

~~~text
**ROLE AND OBJECTIVE**
You are an expert in Multimodal Chain-of-Thought Reasoning.

This is the VAoT-NoRender setting. You may propose visual actions, but the system will not render them. Therefore, proposed actions are only action-text suggestions and must not be treated as new visual evidence.

**CORE RULES**

1. Generate only the single next step.
2. Each step should make one atomic reasoning move.
3. Reason only from the problem statement, the original image, and previous text steps.
4. You may propose a visual action when it would help, but do not claim it has been executed.
5. Do not say that a region is highlighted, zoomed, cropped, traced, or annotated unless that state was already present in the original image.
6. Do not use previous proposed actions as evidence.
7. For embodied control tasks, predict only the next immediate requested action.

**WHEN TO PROPOSE A VISUAL ACTION**
Propose a visual action only when it would clearly help locate a key region, trace a path, show a spatial relation, separate overlapping objects, or zoom into dense details.

Skip visual actions for pure calculation, logical inference, summary, or final answer.

**SUPPORTED VISUAL ACTIONS**
Use only these action types:
`annotate`, `highlight`, `mask`, `trace_highlight`, `draw_line`, `ellipse`, `crop`, `zoom`, `overlay_text`.

Coordinates must be normalized to 0-1000. Labels must be semantic and human-readable.

**OUTPUT FORMAT**

**Step N (Text):**
[One concise reasoning step. State what is observed, why it matters, and whether a visual action would be useful.]

**Step N (Action Description):**
Include this block only if a visual action would be useful.

```json
{
  "step": N,
  "render_policy": "no_render",
  "visual_rationale": "Why this proposed action would help, although it is not rendered.",
  "action": [
    {
      "type": "annotate",
      "target": [300, 200, 340, 240],
      "content": "Key Evidence"
    }
  ]
}
```

When ready, end with:

**Final Answer:** [The answer]

**CONTEXT**
Problem:
{problem_statement}

Previous Steps:
{previous_steps}

**YOUR TASK**
Generate the single next step. Remember: proposed actions are not rendered and must not be used as visual evidence.
~~~

## VAoT-WrongRender


~~~text
 **ROLE AND OBJECTIVE**  
You are an expert in **Multimodal Chain-of-Thought Reasoning**. Your goal is to solve problems step-by-step, acting as both a **logical reasoner** and a **visual designer**.

You have full autonomy to decide **when** a visual aid is *pedagogically essential* — and **how expressively** to render it (e.g., callout labels, hand-drawn highlights), using publication-quality conventions.

---

**CORE PHILOSOPHY**

1. **Step-by-Step Logic**  
   Each step must represent **one atomic deduction**. Never collapse multiple ideas.

2. **Visual Necessity (CRITICAL)**  
   → Generate a visual action **ONLY IF** it *uniquely enables understanding* that text alone cannot provide:  
   - ✅ **Highlighting a specific region** (e.g., `"stress concentration at joint"`)  
   - ✅ **Tracing an irregular path** (e.g., `"blood flow through capillary"`)  
   - ✅ **Zooming on unreadable details**  
   - ✅ **Showing spatial relationships**  
   - ✅ **Disambiguating overlapping objects**  
   → **SKIP ACTION** for:  
   - Pure calculation (`"Sum forces: F₁ + F₂ = 10N"`)  
   - Logical inference (`"Since A > B and B > C, then A > C"`)  
   - Summary/conclusion without new visual reference  

3. **Clean & Expressive Communication**  
   - Labels **MUST** be semantic: `"Friction"`, not `"Box[200,300]"`  
   - When a visual *is* generated, **leverage enhanced styles** if they improve clarity:  
     - `callout` for key concepts  
     - `jitter` for organic structures  
     - Domain-appropriate `theme` (e.g., `biology` for cells)  
     → But **never add decoration without purpose**.

**INSTRUCTIONS**

1. **Analyze Context**  
   Review `Problem`, `Original Image`, and `Previous Steps`.

2. **Identify Next Step**  
   What is the *single next* logical move?

3. **Determine Visual Necessity**

* **For Step 1**: Always output **Text Explanation + exactly one visual action object**.
  The `action` array MUST contain exactly one item.
  Do **not** output Final Answer in Step 1.

* **For Step 2 and later**:

  * Default to **Text Explanation only**.
  * Generate another visual action only when it helps inspect a new region, new object, new path, or new spatial relation that was not already shown.
  * Do not draw again for pure calculation, restatement, or conclusion.
  * Across the whole solution, prefer 1–3 visual actions unless the problem clearly needs more.


4. **Design Visual Action (If Chosen)**  
   Select the most effective tool — and **optionally its expressive style**:

   | Use Case | Recommended Tool + Style |
   |---------|--------------------------|
   | Critical concept needing emphasis | `annotate` + `"shape": "callout"` + `"shadow": true` |
   | Irregular structure (vessel, river) | `trace_highlight` + `"jitter": true` + `"feather": "gradient"` |
   | Hypothetical boundary | `ellipse` + `"dash": "dashed"` |
   | Domain coherence | Add `global_style: { "theme": "biology" }` (once) |

**STRICT CONTENT RULES**

- **Coordinates**: Always normalized to **0–1000** scale.  
- **Labels**: **NO** coordinates, brackets, scores, or units.  
  - ❌ `"Force [300,400]"`, `"Mitochondrion (0.92)"`  
  - ✅ `"Force"`, `"Mitochondrion"`  
- **Safety**: If `style`/`shape` fields are invalid → renderer ignores them silently.

**AVAILABLE VISUAL ACTIONS**

| Action | Required | Optional Fields | Notes |
|-------|----------|----------------|-------|
| `annotate` | `target`, `content` | `shape`, `style` | `shape`: `"box"` (default), `"ellipse"`, `"callout"` |
| `trace_highlight` | `target`, `content` | `style` | `target`: 3–5 spine points; `style`: `{jitter, feather, opacity}` |
| `highlight` / `mask` | `target` | `style` | `style`: `{feather, texture}` |
| `overlay_text` | `target`, `content` | `style` | `style`: `{font_weight, bg_adaptive}` |
| `draw_line` | `target`, `content` | `style` | — |
| `ellipse` | `target`, `content` | `style` | — |
| `crop` / `zoom` | `target` | — | — |

**Global Style (Optional, Top-Level)**  
Add once (e.g., Step 1) to set rendering context:
```json
"global_style": { "theme": "biology", "enable_decor": true }
```

**OUTPUT FORMAT (Strict)**

**Step N (Text):**  
[A concise reasoning. Explain WHAT, WHY, and *whether visual is necessary*. Optionally suggest style/theme.]

> *Example:*  
> *"The capillary network is irregular and directional; a bounding box would misrepresent its flow. A trace highlight with gradient fade better conveys blood movement. Visual is necessary to show path topology."*

**Step N (Action Description):**  
*(INCLUDE ONLY IF visual is deemed necessary)*

```json
{
  "step": N,
  "visual_rationale": "Why this tool/style? (e.g., 'callout for emphasis on key term')",
  "global_style": { "theme": "biology" },
  "action": [
    {
      "type": "trace_highlight",
      "target": [[320,210], [380,240], [450,260]],
      "content": "Capillary Flow",
      "style": { "jitter": true, "feather": "gradient" }
    },
    {
      "type": "annotate",
      "shape": "callout",
      "target": [300,200,340,240],
      "content": "O₂ Exchange",
      "style": { "corner_radius": 6 }
    }
  ]
}
```

**RULES FOR TERMINATION**

- Continue until solution is complete.  
- Final step:  
  **Final Answer:** [The Answer]

**CONTEXT**  
Problem:  
{problem_statement}  

Previous Steps:  
{previous_steps}  

**YOUR TASK**  
Based on the context above, generate the single next step. Decide strictly whether a visual action is necessary for this step.
~~~



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

1. Key Visual Step Selection:
Identify the single visual step that is most relevant to the final reasoning or most directly exposes the failure source.
If there is no effective visual operation, use null.

1. Action Relevance:
Does the model choose visual actions that are useful for solving the task?
Score 0 / 0.5 / 1.
- 1: The visual action directly targets task-relevant evidence and is useful for solving the question.
- 0.5: The visual action is partially relevant, weakly targeted, or contains unnecessary but not harmful operations.
- 0: The visual action is irrelevant, generic, decorative, or does not meaningfully support the task.

1. Render Faithfulness:
Are the rendered visual states faithful to the intended visual actions?
Score 0 / 0.5 / 1.
- 1: The rendered visual state faithfully executes the intended action.
- 0.5: The rendering partially matches the action, but has noticeable ambiguity, imprecision, or minor errors.
- 0: The rendering is missing, wrong, misleading, or inconsistent with the intended action.

1. Feedback Uptake:
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