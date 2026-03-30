# Experiment 2: Phase-Aligned Examples

## Hypothesis
Rules peak at L0-6 then lose 86-93% through compression (Phases 2-3). Examples bloom late (L48-63) and retain 75%+. Adding WRONG/RIGHT demonstration pairs positioned AFTER task blocks and BEFORE output_format should create a Phase 5 blooming region that reinforces rules through demonstration instead of declaration.

## Change
New `<corrections>` section inserted between task 4 and `<output_format>`:
- Reuses `║⊕║` and `║⊗║` markers from entity/passage rules
- WRONG/RIGHT pairs for entity false positives and passage over-retention
- Positioned late in system prompt for maximum Phase 5 proximity

## Why These Markers
Same markers as the rule blocks means the same attention heads allocated in Phase 1 should re-engage with this content in Phase 5. The markers create a lexical bridge between early-absorbed rules and late-blooming demonstrations.

## Measurement
- Cooking curves for `corrections` region — must bloom at L48+ (not L0-6)
- Entity false-positive rate in outputs
- Passage over-retention rate in outputs
- If corrections peaks at L0-6 like rules, the positional hypothesis is wrong
