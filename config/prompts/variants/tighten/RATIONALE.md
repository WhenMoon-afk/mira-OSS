# Tighten Variant

## Strategy
Built on composite base (anchor + trim3 + strengthen). Tests whether revised rule wording improves query expansion grounding and entity extraction precision.

## Changes from Composite

### System Prompt — Expansion Rules (KEY CHANGE)
The production rule "Capture the recent conversational arc with a bias towards the most recent turns" literally instructs the model to produce the behavior we measure as context bleed. It's doing what it's told — the problem is the instruction balance, not the model's attention.

**Old rules**:
1. Dereference pronouns to concrete nouns using conversation context
2. Include domain context that would appear in stored memories
3. Write 2-4 semicolon-separated phrases that would match stored memories about this topic
4. **Capture the recent conversational arc with a bias towards the most recent turns**
5. CRITICAL: Never leave this block empty...

**New rules**:
1. **Start from the current turn and expand outward: what is the user saying NOW, then what recent context informs it**
2. Dereference pronouns to concrete nouns using conversation context
3. Write 2-4 semicolon-separated phrases that would match stored memories about this topic
4. Include domain context and specific details that would appear in stored memories
5. **The first phrase MUST directly describe the current turn's topic. Subsequent phrases can draw from the recent arc.**
6. CRITICAL: Never leave this block empty...

The key change: the arc is preserved as a secondary signal, but the current turn is explicitly prioritized. The "first phrase MUST" constraint gives the model a concrete structural target — it can't satisfy this rule by expanding on the arc alone. This preserves the smoothing function (expansion still covers recent context) while rebalancing toward the current turn.

### System Prompt — Entity Constraint (EXPANDED)
Added more false-positive examples from production data and an explicit rule about capitalization:

```
NOT entities: "Build pipeline", "testing", "Father", "subcortical", "PATCHNOTE", "RAPT", "API", "frontend", "backend", "refactoring".
Capitalization alone does not make something an entity. ALL-CAPS words like "CRITICAL" or "NOTE" are emphasis, not names.
```

### System Prompt — Passage Filtering (TIGHTENED)
Changed "Drop entries from topics the conversation has moved past" to "Drop passages only when the conversation has clearly shifted to a different topic and the passage content is no longer relevant to any active thread."

The original was vague about what "moved past" means. The revision sets a higher bar for dropping passages (must be "clearly shifted" and "no longer relevant to any active thread").

### System Prompt — Complexity Bias Rule
Removed (same as composite). 160 observations across 8 conditions confirm it's decorative.

## Predicted Effects
- Expansion quality: current-turn grounding should improve. The "first phrase MUST" constraint is behaviorally enforceable.
- Entity precision: expanded false-positive list + capitalization rule should reduce false positives.
- Passage retention: higher bar for dropping should reduce over-pruning.
- MI: rule wording changes operate at the behavioral level, not the attention level. The structural attention patterns should be similar to composite (same anchor + trim3 + strengthen base).

## Risk
- Adding an extra expansion rule (6 vs 5) adds ~15 tokens. Minimal impact.
- "First phrase MUST" constraint might make expansions formulaic — the model could satisfy it mechanically.
- Passage filtering tightening could cause passage accumulation if the model becomes too conservative about dropping.
