# Experiment: Calibration-Only Rules

## Hypothesis
Qwen3-32B already knows NER, query expansion, and complexity assessment from pre-training. The value of our rules isn't teaching these tasks — it's calibrating the model's threshold away from its default. Pedagogical framing ("Capitalization does not make a word an entity") wastes tokens explaining what the model knows. Stripping teaching language and keeping only calibration (threshold-setting, boundary examples, defaults) should achieve the same output quality with ~40% fewer rule tokens. Fewer tokens = higher per-token attention density (same mechanism that made passage truncation work in round 2).

## Changes
- Removed `<ir_task>`, `<task id="N" name="...">`, `</task>` XML wrappers (shared across all round 3 variants — structural noise with no instructional value)
- Entity rules: removed "spaCy NER test" framing, removed full-sentence explanations. Kept negative example list and "None when no matches" default. Reordered with threshold at opening edge, format instruction at closing edge.
- Passage rules: compressed to essential test + uncertainty bias. Removed redundant "system matches by ID only" explanation.
- Expansion rules: removed "using stored-memory vocabulary" (unchanged from baseline — Proposal C addresses this). Compressed to 4 lines.
- Complexity rules: removed "when the response requires no reasoning" expansion. Compressed verb list.

## What to Measure
- Entity precision: should maintain or improve (same calibration signals, less noise)
- Entity count: baseline 1.1/sample (composite). Should stay in 0.8-1.5 range.
- Expansion quality: unchanged (rules minimally modified)
- Complexity: unchanged (rules minimally modified)
- Token count: ~40 fewer rule tokens → expect ~2-3% terminal attention gain for other regions

## What to Watch For
- If entity FP rate increases: the pedagogical framing may have been doing work after all (the "why" behind calibration helps the model generalize to novel edge cases)
- If passage retention drops further: compressed rules may be too terse for the model to form a clear relevance threshold
