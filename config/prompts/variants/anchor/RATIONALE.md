# anchor Variant Rationale

## Strategy
Add rare-token emphasis markers around `current_message` in the user template to force attention head allocation. System prompt unchanged. Code constants unchanged.

## What Changes
- User template: Wraps the current turn `<turn speaker="user">` block with `┃◆┃ CURRENT TURN ┃◆┃` / `┃◆┃ END CURRENT TURN ┃◆┃` markers.
- System prompt: identical to baseline
- `CONTEXT_PAIRS`: unchanged (6)

## Token Choice Rationale

### Selected: `┃` (U+2503, BOX DRAWINGS HEAVY VERTICAL) and `◆` (U+25C6, BLACK DIAMOND)

**Why these are rare in Qwen3-32B's vocabulary:**

1. `┃` (U+2503): Box-drawing characters appear in terminal output and ASCII art but are uncommon in natural language web text. Qwen3-32B's tokenizer (trained on multilingual web corpus) likely tokenizes this as a single token because it's a standalone Unicode codepoint, but it will have very low frequency in the training distribution. Low frequency means the model cannot predict it from context -- it becomes an obligate attention sink.

2. `◆` (U+25C6): Geometric shapes are used in bullet points in some CJK web content but are still rare enough that they break normal co-occurrence patterns. As a single Unicode codepoint, it should tokenize as 1 token (not decompose into multi-token sequences like many emoji do).

**Why NOT other candidates:**
- Common emoji (thumbs up, fire, etc.): Many decompose into multi-token sequences in BPE (base codepoint + variation selector), spreading attention across subwords instead of concentrating it.
- ASCII art (`===`, `***`): Too common in web text. The model has strong predictions for these, so they don't force attention reallocation.
- Rare CJK characters: Would work as attention sinks but risk confusing the model's language identification circuits in a multilingual model, potentially degrading output quality.

### Marker Structure: `┃◆┃ CURRENT TURN ┃◆┃`

The English words "CURRENT TURN" provide semantic content that reinforces the structural signal. The rare tokens on both sides create attention anchors at the *boundaries* of the current message, not just at one end. This is important because:
- The opening marker (`┃◆┃ CURRENT TURN ┃◆┃`) creates an attention anchor BEFORE the current message content
- The closing marker (`┃◆┃ END CURRENT TURN ┃◆┃`) creates an anchor AFTER it
- Together they create a "spotlight" effect -- attention heads that lock onto the rare tokens will also attend to everything between them

## MI Metric Targeted
**current_message per-token density** (currently 0.692, already 2.4x higher than conversation_turns at 0.246).

The anchor strategy does NOT directly address the token mass ratio (9.5x). Instead, it attempts to boost per-token density for the current_message region even higher, compensating for the mass disadvantage. If the rare tokens push per-token density from 0.692 to ~1.0+, the aggregate ratio would shift from 3.1x toward ~2.3x even without changing token counts.

This is a MODERATE confidence intervention because it manipulates per-token density (mechanistic) rather than token mass (arithmetic).

## Mechanistic Hypothesis
- Rare tokens `┃` and `◆` should force attention head allocation at the current_message boundary positions
- This creates "attention anchors" that increase the probability of nearby tokens (the actual user message) also receiving elevated attention
- The effect should be visible as a spike in per-token attention density for the current_message region
- Expected directional change: per-token density ratio from 2.4x toward 3.0-4.0x, partially offsetting the 9.5x token mass disadvantage

## Expected Tradeoffs
- **Positive**: Should boost current_message salience without losing any conversational context
- **Negative**: Adds ~10-12 tokens of non-content markers. Small token overhead.
- **Risk**: The rare tokens could confuse the model's output formatting if they leak into the generation distribution. However, since they're in the user message (not system prompt), and the model is strongly conditioned to output XML, this risk is low.
- **Uncertainty**: We don't know Qwen3-32B's exact tokenization of these characters. If `┃` decomposes into multiple tokens, the concentration effect weakens. This needs to be verified empirically.
- **Risk level**: LOW-MEDIUM. The mechanism is sound (rare tokens force attention allocation) but the magnitude of the effect is uncertain.