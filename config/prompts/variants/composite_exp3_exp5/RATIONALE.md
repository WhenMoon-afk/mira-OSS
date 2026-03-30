# Composite: Exp 3 (No Reminders) + Exp 5 (Passage Compress)

## Hypothesis
Combining the two safe, additive improvements from round 1:
- Exp 3: task_reminders are deadweight (97 tokens, 1.71% terminal budget). Rules survive Phase 1 absorption without recency reinforcement. Removal freed 6.4% more terminal attention for current_message.
- Exp 5: Passage truncation to 15 words reduced token mass competition. Best bleed ratio (0.23x vs 0.26x baseline). current_message gained 6.4% terminal attention.

Expected combined effect: ~10-15% context bleed improvement over baseline.

## Changes
1. Complete removal of `<task_reminders>` block from user template (Exp 3)
2. `--truncate-passages 15` flag truncates each passage to ID + first 15 words (Exp 5)
3. Base system prompt unchanged

## Measurement
- Context bleed ratio: should improve beyond either individual experiment
- current_message terminal attention: should see additive gains from both token reductions
- stored_passages per-token density: should increase (fewer tokens, same region)
- No regressions expected in entity_rules, expansion_examples, or format compliance
