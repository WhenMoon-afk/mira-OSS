# trim3 Variant Rationale

## Strategy
Reduce conversation turns from 6 pairs to 3 pairs. System prompt unchanged. User template unchanged. The change is purely in the code constant `CONTEXT_PAIRS` (6 -> 3).

## What Changes
- `CONTEXT_PAIRS = 3` in `subcortical.py` (or passed as parameter)
- System prompt: identical to baseline
- User template: identical to baseline

## MI Metric Targeted
**Context bleed aggregate attention ratio**: currently 3.1x (conv_turns / current_message).

The decomposition is: `raw_attention_ratio (3.1x) = per_token_density_ratio (0.42x) * token_count_ratio (9.5x)`

Halving the conversation turns from 6 pairs to 3 pairs reduces the token count ratio from ~9.5x to ~4.75x. Holding per-token density constant at 0.42x, the predicted aggregate ratio becomes: `0.42 * 4.75 = 2.0x`.

This is the highest-confidence intervention because it operates on arithmetic (token mass), not on mechanistic manipulation of per-token density.

## Mechanistic Hypothesis
- Reducing token count ratio from 9.5x to ~4.75x should reduce aggregate attention ratio from 3.1x toward ~2.0x
- Per-token density ratios should remain approximately stable (current_message already has 2.4x higher density)
- Sample_19 (383 curr / 306 conv tokens, ratio ~1.2x) already showed the ratio drops to 1.1x when token mass is balanced -- this confirms the intervention direction

## Expected Tradeoffs
- **Positive**: Reduced context bleed on query expansion. Model should attend more to current turn.
- **Negative**: Less conversational context for pronoun dereferencing. If the user says "that thing we discussed" and the referent was 4-5 turns back, 3 pairs won't include it.
- **Risk level**: LOW. The current rule already says "bias towards the most recent turns." 3 pairs (6 messages) still provides substantial context. Memory pressure mode already uses `CONTEXT_PAIRS - 1 = 5`, so reducing to 3 is a larger step but in the same direction.
- **Passage filtering impact**: Less context for retention decisions. The model sees fewer turns to judge whether a memory is still topically relevant. This could cause over-retention (keeping memories that would be dropped with more context about topic drift).

## Token Count Estimates
- Baseline: ~6 pairs = ~12 messages. Average message ~50-100 tokens = ~600-1200 tokens in conversation_turns
- trim3: ~3 pairs = ~6 messages. Average ~300-600 tokens in conversation_turns
- current_message: typically 10-200 tokens (unchanged)
- Net token reduction: ~300-600 fewer tokens in user message