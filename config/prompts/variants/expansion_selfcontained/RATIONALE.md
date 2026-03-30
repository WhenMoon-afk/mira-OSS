# Experiment: Self-Contained Expansion with Example Diversity

## Hypothesis
Expansion is a generation task, not a classification task. The MI data shows examples bloom at L59 and retain 75%+ to generation — they carry more instructional weight than rules during Phase 5 when the model actually generates the expansion. The current expansion rules say "use stored-memory vocabulary," but at Phase 1 absorption the model hasn't seen any stored memories yet. This requires fragile late binding: the rule representation formed at L0-6 must re-attach to passage data encountered at L32+ during re-engagement.

Two changes: (1) Replace "stored-memory vocabulary" with a self-contained style description the model can absorb at Phase 1 without late binding: "concrete nouns, activities, emotions — not abstract categories." (2) Add a fourth example demonstrating pronoun dereferencing and 2-phrase output. Current examples all show 3 phrases, which may anchor the model at 3. The new example shows that 2 is valid and explicitly demonstrates "She" → "partner" pronoun resolution through demonstration rather than declaration.

## Changes
- Removed `<ir_task>`, `<task id="N" name="...">`, `</task>` XML wrappers (shared across all round 3 variants — structural noise with no instructional value)
- Expansion rules: "using stored-memory vocabulary" → "Style: concrete nouns, activities, emotions — not abstract categories"
- Added fourth example showing 2-phrase expansion with pronoun dereferencing:
  User: "She's been doing that thing again where she ignores my texts"
  Expansion: "partner ignoring text messages; communication frustration in relationship"

## What to Measure
- Expansion phrase count distribution: should see occasional 2-phrase outputs (currently anchored at 3)
- Pronoun dereferencing rate: should improve (demonstrated by example, not just declared by rule)
- Expansion vocabulary: should see more concrete nouns/activities, fewer abstract categories
- Expansion word count: may decrease slightly if 2-phrase outputs appear (not a regression)

## What to Watch For
- If the fourth example dominates and the model starts producing mostly 2-phrase outputs, the example may be too influential relative to the 3-phrase examples (3:1 ratio should prevent this)
- If expansion quality degrades: "concrete nouns, activities, emotions" may be less precise than "stored-memory vocabulary" for guiding the right style
