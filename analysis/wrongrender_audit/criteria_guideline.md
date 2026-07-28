# WrongRender Quality Audit: annotation guide

Evaluate the quality of the WrongRender image, not whether the model's final answer is correct. The page intentionally hides final answers, post-WrongRender reasoning, correctness flags, and automatic judge scores.

For every criterion choose one of `Pass`, `Partial`, or `Fail` and optionally explain uncertainty in the note.

1. **Corruption validity** — Did WrongRender change a task-relevant visual fact in a clear, wrong direction?
   - Pass: a key fact is clearly changed into a wrong counterfactual.
   - Partial: the error exists but is weak, ambiguous, imprecise, or mixed with small extra changes.
   - Fail: no substantive error, the change is actually correct, or this is only noise/corruption.
2. **Plausibility** — Does the image still look like a normal output from the same renderer?
   - Pass: style, clarity, composition, and rendering quality are consistent.
   - Partial: minor artifacts, font/edge mismatch, or local deformation remains usable.
   - Fail: severe deformation, garbled text, broad redraw, obvious collage, or unreadable content.
3. **Operation consistency** — Does it retain the original action type, target region, and intent, changing only the intended key attribute?
   - Pass: same operation and target; only expected attribute is made wrong.
   - Partial: mostly the same, with limited non-target change or small target displacement.
   - Fail: different object/action, broad redraw, or action description conflicts with the image.
4. **Task relevance** — Could the changed visual evidence affect downstream reasoning or the answer?
   - Pass: directly changes key evidence, relation, count, direction, attribute, or state.
   - Partial: related but likely auxiliary or weak.
   - Fail: irrelevant to the question.
5. **Content preservation** — Outside the intended wrong region, is the task content essentially unchanged?
   - Pass: unrelated objects, text, coordinates, layout, and facts stay intact.
   - Partial: a few non-key changes without harming recognition.
   - Fail: multiple unrelated regions change, objects disappear, or the scene is broadly altered.

The overall label is computed automatically: all five Pass → Pass; at least one Partial and no Fail → Partial; any Fail → Fail. `Unable to judge / metadata missing` permits saving but excludes the case from formal summary statistics by default.

Do not infer labels from model success or failure. A misleading image may still fail because it changes unrelated content, while a visually polished image may fail because it did not alter task-relevant evidence.
