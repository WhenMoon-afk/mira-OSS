# Diamonds Variant: Rare-Token Markers on Rule Sections

## Strategy
Built on tighten base (composite + rule rewording). Adds rare-token attention anchors around the two most decorative task rule sections in the system prompt to boost their attention at generation positions.

## Core Finding Being Addressed
All four task rule sections receive BELOW uniform attention at their own generation positions:
- T1 entity rules: 0.3x uniform at terminal
- T2 passage rules: 0.1x uniform at terminal (worst)
- T3 expansion rules: 0.2x uniform at expansion_gen
- T4 complexity rules: 0.2x uniform at complexity_gen

Meanwhile, examples receive strong attention: output format examples 4.19% at complexity_gen, expansion few-shot examples 4.56% at expansion_gen. The model learns from examples, not rules.

## Design Decisions

### Which rules get markers: T2 and T3 only (not all four)

Anchor markers on current_message in the user template worked because the markers were SCARCE -- only 2 marker pairs in the entire sequence. The rarity of U+2503/U+25C6 in Qwen3-32B's BPE vocabulary forces attention head allocation because the model cannot predict them from context.

Adding markers to all 4 task rule sections would create 4 system prompt marker pairs + 2 user template marker pairs = 6 total. This risks crossing the saturation threshold where the pattern becomes predictable ("another marker pair") and loses its attention-forcing property.

**Selection criteria**:
- **T2 passage rules (0.1x uniform)**: Most decorative. Highest potential lift. Passage filtering quality depends on the model actually reading the rules about when to drop vs preserve.
- **T3 expansion rules (0.2x uniform)**: Second most decorative AND most critical task. Query expansion replaces the user's query for BM25 + vector search -- it's the single highest-impact output.
- **T1 entity rules (0.3x, SKIPPED)**: Entity attention has a stable floor (~3.1%) driven by in-context entity patterns. No structural change moved entity attention in v1 testing. Markers would be wasted here.
- **T4 complexity rules (0.2x, SKIPPED)**: Output format examples already teach complexity effectively at 4.19%. The criteria block (straightforward vs complex examples) is demonstrative, not rule-based. Rules here are redundant with the examples.

This gives 2 system prompt marker pairs + 2 user template marker pairs = 4 total. Twice the current count but still scarce enough to maintain the rarity mechanism.

### Marker token choice: ║⊕║ (different from user template's ┃◆┃)

Using DIFFERENT rare tokens for the system prompt avoids a habituation problem. Due to causal attention, the model processes system prompt markers BEFORE user template markers. If both use ┃◆┃, the system prompt occurrences partially habituate the attention heads to these tokens, potentially reducing the +43% effect measured for current_message in the user template.

- **System prompt markers**: ║ (U+2551 BOX DRAWINGS DOUBLE VERTICAL) + ⊕ (U+2295 CIRCLED PLUS)
- **User template markers**: ┃ (U+2503 BOX DRAWINGS HEAVY VERTICAL) + ◆ (U+25C6 BLACK DIAMOND) [unchanged]

U+2551 and U+2295 are rare in Qwen3-32B's multilingual web training data:
- ║ appears primarily in ASCII art tables and box-drawing contexts, infrequent in general web text
- ⊕ appears in mathematical/logical notation, very sparse in conversational or documentation text
- Both should tokenize as single BPE tokens given their Unicode range

### Marker placement: Outside the XML tags, inside the task block

```
║⊕║ PASSAGE RULES ║⊕║
<rules>
  ...
</rules>
║⊕║ END PASSAGE RULES ║⊕║
```

Placing markers OUTSIDE `<rules>` but INSIDE `<task>` ensures:
1. prep_inputs.py region detection still works (it finds `<task id="2"` to `</task>`, which includes the markers)
2. The markers are adjacent to but not inside the XML structure, avoiding potential confusion in XML parsing
3. The markers create attention anchors that bracket the rule content, boosting attention for tokens between the markers via spatial locality

### Base changes (inherited from tighten + examples)
- Expansion rules reworded: "Start from the current turn", "first phrase MUST directly describe current turn's topic"
- Entity constraint expanded with more false-positive examples + capitalization rule
- Passage filtering tightened: "clearly shifted to a different topic"
- Complexity bias rule removed (decorative across 160 observations)
- 4 expansion examples (from examples variant: dropped the escalation example, added 2 context_hint examples targeting short/ambiguous messages: "yeah let's keep going with that" and "Alright. I'll be back in a bit.")

## Token Budget Analysis

Added tokens from markers:
- `║⊕║ PASSAGE RULES ║⊕║` + `║⊕║ END PASSAGE RULES ║⊕║`: ~20 tokens
- `║⊕║ EXPANSION RULES ║⊕║` + `║⊕║ END EXPANSION RULES ║⊕║`: ~22 tokens
- Total: ~42 tokens added to system prompt

This is a 0.5% increase in system prompt token count. The tighten base already removed ~15 tokens (complexity bias rule), partially offsetting.

## Predicted Effects

### T2 passage rule attention (primary target)
- Baseline: 0.1x uniform
- Predicted: 0.3-0.5x uniform
- Reasoning: Anchor markers on current_message boosted attention +43%. If the same mechanism applies to system prompt content (lower confidence -- system prompt is processed earlier, farther from generation), a similar proportional boost would bring T2 from 0.1x to ~0.14x. But T2 is much smaller than current_message, so per-token density boost may be proportionally larger. Conservative estimate: 3-5x improvement from 0.1x baseline, reaching 0.3-0.5x uniform.
- Confidence: MODERATE. The anchor effect was measured on user template content (closer to generation). System prompt content is further from the generation position, so the recency gradient works against us. The markers may be less effective here.

### T3 expansion rule attention (primary target)
- Baseline: 0.2x uniform at expansion_gen
- Predicted: 0.4-0.7x uniform
- Reasoning: Same mechanism as T2 but T3 is the expansion task, processed closer in task order to expansion generation. The expansion examples at 4.56% demonstrate that expansion-relevant content CAN capture attention at expansion_gen.
- Confidence: MODERATE.

### Current_message attention (must not regress)
- Baseline (composite): ~3.68% (anchor effect)
- Predicted: ~3.5-3.7%
- Reasoning: Using different marker tokens (║⊕║ vs ┃◆┃) avoids habituation. The 42 additional tokens in the system prompt slightly increase total sequence length, diluting all per-token percentages by ~0.5%. Negligible.

### Format compliance (`<` rank at L63)
- Baseline (tighten): ~20-50 (estimated from composite prediction)
- Predicted: ~30-70
- Risk: Adding non-XML content (║⊕║ lines) inside task blocks could slightly confuse the format compliance signal. The markers are outside `<rules>` tags but inside `<task>` tags, so the XML structural hierarchy is preserved. Risk is LOW -- the same placement pattern worked for ┃◆┃ in the user template without catastrophic format degradation.

### Expansion example attention
- Baseline (tighten): ~3.17% (strengthen level)
- Predicted: ~3.0-3.2%
- Reasoning: The 42 additional marker tokens slightly increase competition for attention budget. Expansion examples have high intrinsic salience, so the effect should be minimal.

## Risks

1. **Marker saturation**: 4 marker pairs might be past the scarcity threshold for Qwen3-32B. If the model learns to predict "another ║⊕║ block", the attention-forcing mechanism fails. The user template ┃◆┃ effect was measured with only 2 marker pairs. Mitigation: using different tokens creates two independent rarity signals rather than one repeated pattern.

2. **System prompt markers less effective than user template markers**: The recency gradient means system prompt content (early in sequence) inherently gets less attention at generation positions (late in sequence) than user template content. Markers in the system prompt may provide a smaller boost than the +43% measured for current_message. This is the main uncertainty.

3. **prep_inputs.py region detection**: The markers are INSIDE the `<task>` blocks, so task region detection works. But the `<rules>` sub-region detection for task3 (expansion_rules) searches within the task3 block for `<rules>...</rules>`, which will find the markers inside the block but outside the rules tags. The markers are NOT inside `<rules>`, so the expansion_rules region annotation will correctly capture just the `<rules>...</rules>` content. However, the markers themselves won't be in any annotated region -- they'll be in the task block but not in any sub-region. This is acceptable for MI measurement: we can detect whether the markers boosted attention for the adjacent rules regions.

4. **Interaction with trim3**: With fewer conversation turns (3 instead of 6), the total sequence is shorter, which means system prompt markers are relatively closer to the generation position (shorter distance in token positions). This should slightly AMPLIFY the marker effect.

## Required Code Changes
Same as composite: CONTEXT_PAIRS 6->3 in `cns/services/subcortical.py` for trim3 component.