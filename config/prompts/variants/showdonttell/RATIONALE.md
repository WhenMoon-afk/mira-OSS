# Show-Don't-Tell Variant: Remove Decorative Rules, Strengthen Examples

## Strategy
Built on tighten base (composite + rule rewording). Instead of trying to boost decorative rule attention with markers, removes the most decorative rule sections entirely and relies on output format examples to teach the model the correct behavior. Adds one targeted output example to compensate for the removed passage filtering rules.

## Core Insight
The MI data reveals a clean separation between what teaches the model and what doesn't:

| Content Type | Attention at Generation | Status |
|---|---|---|
| Output format examples | 4.19% at complexity_gen | CAUSAL |
| Expansion few-shot examples | 4.56% at expansion_gen | CAUSAL |
| T1 entity rules | 0.3x uniform | Decorative |
| T2 passage rules | 0.1x uniform | Decorative |
| T3 expansion rules | 0.2x uniform | Decorative |
| T4 complexity rules | 0.2x uniform | Decorative |

Rules are below uniform attention -- they receive less attention than random chance at their task's generation positions. Examples receive strong attention and are demonstrably causal. The insight: decorative rules are dead weight that competes for attention budget. Removing them frees budget that reallocates to high-salience content (examples). This is the same mechanism that made strengthen work: removing the complexity bias rule freed budget that reallocated to expansion examples (+7.2x).

## Design Decisions

### What was removed

**T2 passage `<rules>` block (~420 chars)**:
The 4 passage filtering rules (preserve background, drop moved-past topics, output relevant only, copy ID exactly) received 0.1x uniform attention -- the most decorative content in the entire prompt. The model was learning passage filtering entirely from the output format examples, which show the correct `<passage id="..." still_relevant="true">` pattern.

Three of the four rules are behavioral judgments that are better taught by demonstration:
- "Preserve passages providing useful background" -> demonstrated by example 2 (focus/distraction passages retained during a complex conversation)
- "Drop passages when conversation has shifted" -> demonstrated by new example 3 (only 1 passage retained, implying others dropped)
- "Output ONLY passages that remain relevant" -> demonstrated by all examples (only still_relevant passages appear)

The fourth rule ("copy the full passage ID exactly") is a mechanical precision requirement that cannot be demonstrated implicitly. This was moved into the `<input_format>` section as a `<note>` element, which is part of the passage format teaching block rather than the behavioral rules block. The input_format section has higher intrinsic relevance to passage ID handling than the rules block.

**T4 complexity `<rules>` block (~188 chars)**:
The 2 complexity rules ("evaluate based on cognitive effort, not message length" and "output exactly one of: straightforward OR complex") received 0.2x uniform attention. The criteria block (straightforward vs complex examples) is inherently demonstrative -- it teaches by enumeration. And the output format examples already demonstrate the binary choice in action.

The "output exactly one of" constraint was moved into the task description as a trailing clause: "Output exactly one of: straightforward OR complex." This puts the format constraint in a higher-visibility position (descriptions get more attention than rule sub-blocks) without adding a separate rules section.

### What was added

**Third output example (~430 chars)**:
```xml
<entities>
<named_entity>Costco</named_entity>
</entities>
<relevant_passages>
<passage id="mem_y6Z7a8B9" still_relevant="true">Weekly meal prep routine...</passage>
</relevant_passages>
<query_expansion>
grocery shopping trip to Costco; weekly meal prep supplies and bulk buying; food planning and budgeting for household
</query_expansion>
<complexity>straightforward</complexity>
```

This example teaches four things the previous two examples didn't demonstrate:
1. **Passage dropping**: Only 1 passage retained (vs 2 in both existing examples). Implicitly teaches that fewer passages = correct when conversation has narrowed.
2. **Single entity extraction**: Shows extracting one entity (Costco as ORG) rather than multiple or none.
3. **Current-turn-grounded expansion**: First phrase directly describes the current activity. No arc drift.
4. **Entity precision under ambiguity**: "Costco" is unambiguously an ORG -- teaches the model the confidence threshold for inclusion.

### What was kept unchanged

**T1 entity `<entity_constraint>`**: Compact, contains the negative examples list ("Build pipeline", "testing", etc.) that cannot be effectively demonstrated in output examples. Negative examples require explicit enumeration.

**T3 expansion `<rules>` block**: The most critical task. The tighten variant's rules ("start from current turn", "first phrase MUST directly describe current turn's topic") are behavioral constraints that are partially demonstrated by the few-shot examples but benefit from explicit statement. Expansion rules at 0.2x uniform is decorative, but this is the one task where behavioral rule compliance most directly impacts production quality. Conservative choice: keep rules for the critical path, remove for the non-critical paths.

**T3 expansion `<examples>` block**: Already proven effective at 4.56% attention. The 4 examples (including context_hint examples from the examples variant) are the primary teaching mechanism for expansion quality.

## Token Budget Analysis

| Change | Tokens (est.) |
|---|---|
| Removed T2 rules block | -85 tokens |
| Removed T4 rules block | -40 tokens |
| Added third output example | +90 tokens |
| Moved ID note to input_format | +8 tokens |
| Moved "one of" to T4 description | +5 tokens |
| **Net** | **-22 tokens** |

Slight net reduction in system prompt token count. The freed attention budget from removing ~125 tokens of decorative content should reallocate to high-salience regions (output examples, expansion examples).

## Predicted Effects

### Output format example attention
- Baseline: 4.19% at complexity_gen
- Predicted: 4.5-5.5% at complexity_gen
- Reasoning: Third example adds token mass to the output_format section, and the freed budget from rule removal reallocates preferentially to high-salience content. strengthen showed this exact mechanism: removing decorative content led to +7.2x expansion example boost.
- Confidence: HIGH. The strengthen precedent directly applies. The question is magnitude, not direction.

### Passage filtering quality
- Predicted: UNCHANGED or IMPROVED
- Reasoning: The model was not using the passage rules (0.1x uniform). Removing them removes dead weight without losing functional influence. The third output example now demonstrates passage dropping behavior, which was previously not demonstrated at all. If output examples are causal (4.19% attention), adding a passage-dropping example should improve passage filtering quality.
- Risk: The ID-matching precision requirement moved from rules to input_format. If the input_format section also gets low attention, the model might truncate or modify passage IDs. But every output example demonstrates correct ID format, so the pattern is reinforced 3 times in the examples vs 1 time in the old rule.

### Complexity assessment quality
- Predicted: UNCHANGED
- Reasoning: The criteria block is the functional teaching mechanism. The removed rules were decorative. The "output exactly one of" constraint is now in the task description, which is a slightly higher-visibility position.

### Context bleed ratio
- Predicted: ~1.0-1.5x (same as composite prediction)
- Reasoning: The show-don't-tell changes are to system prompt structure, not user template structure. Context bleed is driven by user template token mass ratio. anchor (user template markers) and trim3 (fewer turns) are the primary context bleed interventions, both preserved.

### Format compliance (`<` rank at L63)
- Predicted: ~20-40
- Reasoning: Adding a third output example provides MORE XML format demonstration, which should help format compliance. The removed rules were not contributing to format compliance (below uniform attention). Net effect should be slightly positive.
- Risk: LOW. No terminal-position prose directives.

## Comparison with Diamonds Variant

| Dimension | Diamonds | Show-Don't-Tell |
|---|---|---|
| Mechanism | Boost rule attention via rare tokens | Remove rules, strengthen examples |
| Confidence | MODERATE (untested mechanism on system prompt) | HIGH (strengthen precedent applies) |
| Token change | +42 tokens | -22 tokens |
| Attention budget | Slight competition increase | Slight competition decrease |
| Format risk | LOW (new non-XML tokens in task blocks) | LOW (more XML examples) |
| Teaching mechanism | Force model to read existing rules | Replace rules with demonstrated behavior |

The two variants test orthogonal hypotheses:
- **Diamonds**: Can rare-token markers boost system prompt rule attention the way they boosted user template content attention?
- **Show-don't-tell**: Are decorative rules better removed entirely, with their teaching function delegated to output examples?

If both improve quality, a future composite could combine them (diamonds markers on T3 expansion rules + show-don't-tell removal of T2/T4 rules). They target different tasks and should not interfere.

## Required Code Changes
Same as composite: CONTEXT_PAIRS 6->3 in `cns/services/subcortical.py` for trim3 component.