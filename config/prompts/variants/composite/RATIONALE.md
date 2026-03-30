# Composite Variant: anchor + trim3 + strengthen

## Strategy
Combines the three empirically validated interventions from the v1 MI pipeline run (20 samples each, Qwen3-32B, B200 GPU). Explicitly excludes focus and reorder based on data-driven disqualification.

## Changes Applied

### From anchor (user template)
- Added `┃◆┃ CURRENT TURN ┃◆┃` and `┃◆┃ END CURRENT TURN ┃◆┃` rare-token markers around `<turn speaker="user">` in user template
- Tokens: U+2503 (┃) and U+25C6 (◆) — rare in Qwen3-32B's multilingual web training data
- ~18 tokens added

**Empirical effect (measured)**: Reduced context bleed ratio from 2.34x to 1.38x (-41%). Increased current_message absolute attention from 2.58% to 3.68% (+43%). Increased per-token density ratio from 3.69x to 4.32x. The only variant that improved per-token density.

**Mechanism**: Rare tokens force attention head allocation at their positions. Spatial locality in intermediate-layer attention heads causes adjacent current_message content to benefit. Global attention budget displacement disproportionately taxes low-density regions (conv_turns).

**Format risk**: `<` rank degraded from 4 to 31 at L63. Rank 31 is 99.98th percentile of ~150K vocab — low risk for greedy decoding.

### From trim3 (service code change)
- CONTEXT_PAIRS reduced from 6 to 3 in `cns/services/subcortical.py`
- Removes ~400-600 tokens of conversation history per invocation (sample-dependent)

**Empirical effect (measured)**: Reduced context bleed ratio from 2.34x to 1.76x (-25%). Per-token density ratio decreased from 3.69x to 2.96x (expected — fewer conv_turns tokens means higher per-token density for conv_turns). No format compliance impact (rank 4 at L63, identical to baseline).

**Mechanism**: Pure mass reduction. Token mass ratio drives aggregate attention arithmetically. Halving conv_turns mass approximately halves its aggregate attention share.

**Complementarity with anchor**: trim3 attacks mass ratio, anchor attacks per-token density ratio. They operate through different mechanisms and should be approximately additive. trim3's density ratio decrease (3.69x→2.96x) and anchor's density ratio increase (3.69x→4.32x) work in orthogonal dimensions.

### From strengthen (system prompt)
- Consolidated 4 `<rule>` elements in entity extraction into single `<entity_constraint>` block with concrete false positive examples
- Removed complexity bias rule ("When uncertain, prefer complex") and `<complexity_default>` element
- Reduced from 3 complexity rules to 2

**Empirical effect (measured)**: Expansion example attention increased 7.2x (0.44%→3.17%). Entity attention unchanged (3.15%→3.18%). Complexity bias remained decorative (0.19%→0.23%, below 0.57% uniform threshold). No format compliance impact (rank 3 at L63).

**Mechanism**: Consolidating entity rules reduced structural complexity (6 fewer XML tag boundaries). Freed attention budget reallocated to highest-salience content in the prompt — the few-shot expansion examples. Output format attention decreased (4.73%→3.20%), suggesting the model relies less on output examples when input structure is cleaner.

**Complexity bias removal rationale**: 160 observations across 8 conditions (baseline + 6 variants + aggressive) unanimously show the bias rule below uniform attention. The `SubcorticalResult` dataclass defaults `complexity="complex"` — code-level safety net exists regardless. The `<complexity_default>` restructuring in strengthen proved restructuring does not help. Removing saves ~15 tokens of dead weight.

## Changes NOT Applied

### focus (DISQUALIFIED)
Terminal `<primary_focus>` directive destroyed format compliance: `<` rank at L63 = 34,188 (vs baseline 4). The mechanism: terminal-position prose directive dominates the generation context, displacing XML structural patterns. Even when combined with anchor tokens in the aggressive variant, the terminal directive was dominant (rank 29,092). Natural language directives at the terminal position are incompatible with XML output format compliance.

### reorder (DISQUALIFIED)
Current_message region was undetectable by prep_inputs.py after repositioning. Format compliance degraded (rank 26). Passage filtering may be impaired by seeing passages before the current turn (task requires evaluating passage relevance to the current turn). anchor + trim3 provide sufficient context bleed reduction without reorder's risks.

## Predicted Composite Effects

### Context bleed ratio
- Baseline: 2.34x
- Expected range: 1.0x-1.5x
- Reasoning: anchor achieved 1.38x alone, trim3 achieved 1.76x alone. They operate through different mechanisms (density vs mass). Combined effect should be better than either alone, with diminishing returns keeping it above 1.0x.

### Expansion example attention
- Baseline: 0.44%
- Expected range: 2.5%-4.0%
- Reasoning: strengthen achieved 3.17% alone. Combined with trim3's reduced overall mass (which slightly increases all system prompt per-token attention), the effect should persist or increase slightly.

### Format compliance (`<` rank at L63)
- Baseline: 4
- Expected range: 20-50
- Reasoning: anchor alone was 31. strengthen was 3 (better than baseline). The compound effect is uncertain — strengthen's cleaner structure might partially offset anchor's degradation.
- Risk level: LOW. Even rank 50 is 99.97th percentile in ~150K vocab.

### Entity rule attention
- Baseline: 3.15%
- Expected: ~3.0-3.2% (unchanged)
- Reasoning: Neither anchor nor trim3 affected entity attention. strengthen's consolidation maintained T1 attention at 3.18%. This appears to be a stable floor determined by in-context entity patterns, not by rule attention. Further improvement would require architectural changes (e.g., entity examples in the prompt) rather than structural changes.

## Interaction Risks

1. **trim3 + strengthen on passage filtering**: With only 3 turns of context, the model has less information for determining which passages "the conversation has moved past." strengthen's changes don't affect T2 directly, but the reduced context may make the model more conservative about dropping passages. Monitor passage retention rates.

2. **anchor + strengthen on output format**: Anchor degrades `<` rank (4→31). Strengthen reduces output format attention (4.73%→3.20%). These could compound. If `<` rank exceeds ~100 in the composite, consider removing one of the two CDATA example blocks from output_format to reduce its token mass and concentrate attention on the remaining example.

3. **strengthen expansion boost durability**: The 7.2x expansion example boost was measured without trim3's mass reduction or anchor's rare tokens. The attention landscape changes with all three combined. The examples' intrinsic salience is high, so the boost should persist, but the magnitude may vary.

## Required Code Change

CONTEXT_PAIRS in `cns/services/subcortical.py` line 62 must be changed from 6 to 3 for the trim3 component. The prompt files alone are insufficient.
