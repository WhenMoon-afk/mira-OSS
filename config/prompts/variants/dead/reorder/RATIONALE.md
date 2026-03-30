# reorder Variant Rationale

## Strategy
Move `current_message` after `stored_passages` in the user template to exploit the causal attention recency gradient. System prompt unchanged. Code constants unchanged.

## What Changes

### User Template Section Order

**Before (baseline):**
```
1. <conversational_context>{conversation_turns}</conversational_context>
2. ---- separator ----
3. <system_message>Execute...</system_message>
4. <turn speaker="user">{user_message}</turn>
5. ---- separator ----
6. <stored_passages>{previous_memories}</stored_passages>
7. ---- separator ----
```

**After (reorder):**
```
1. <conversational_context>{conversation_turns}</conversational_context>
2. ---- separator ----
3. <stored_passages>{previous_memories}</stored_passages>
4. ---- separator ----
5. <system_message>Execute...</system_message>
6. <turn speaker="user">{user_message}</turn>
7. ---- separator ----
```

The `current_message` block (system_message + turn) moves from position 3-4 to position 5-6, placing it at the terminal position of the user message -- directly before generation begins.

## MI Metric Targeted
**current_message attention at terminal position**: currently 2.8% aggregate (0.69 per 1K token density).

In causal attention, later tokens have inherent positional advantage because they are attended to by more subsequent positions. The terminal position (last token before generation) has the strongest recency bias. By placing current_message at the terminal position, it benefits from both its existing high per-token density (2.4x) AND the recency gradient.

The stored_passages section (currently 9.0% aggregate, 0.49 per 1K tok density) moves earlier. This is acceptable because passage filtering (task 2) needs to see the passages but doesn't need them at maximum salience -- it needs the *conversational context* to judge relevance, which remains in the same relative position.

## Mechanistic Hypothesis
- Moving current_message from mid-sequence to terminal position should increase its aggregate attention share. The recency gradient is strongest in the final ~100-200 tokens before generation.
- stored_passages moving earlier should decrease its aggregate attention slightly, but since passage filtering is driven by comparing passages against conversation context (which stays early), the filtering task should be unaffected.
- Query expansion should improve because the model generates expansion text immediately after seeing the current_message at terminal position. The causal attention path from current_message tokens to expansion generation tokens is now the shortest possible.
- The effect compounds with the existing 2.4x per-token density advantage: current_message already gets disproportionate per-token attention, and now it also gets positional advantage.

## Expected Tradeoffs
- **Positive**: Strongest expected improvement for query expansion quality. The model generates expansion immediately after the current message, with no intervening stored_passages content to dilute attention.
- **Negative**: Passage filtering may get slightly weaker since stored_passages are now further from generation. However, passage filtering happens BEFORE query expansion in the output XML, so by the time the model generates `<relevant_passages>`, it's attending back across the entire sequence. The loss should be small.
- **Risk**: If the model's passage filtering circuit relies on stored_passages having high positional salience (near generation), moving them earlier could cause over-retention or over-dropping. The MI data shows stored_passages already has 9.0% aggregate attention, so it's well above the danger zone.
- **Risk level**: LOW-MEDIUM. The section ordering change is simple and the mechanism (recency gradient) is well-established in attention literature. The main uncertainty is whether passage filtering quality degrades.

## Why stored_passages Moves and Not conversation_turns
conversation_turns is the dominant token mass contributor (9.5x). Keeping it in its current early position is desirable -- we WANT it to have lower positional salience. Moving it later would give it both mass AND recency advantages, worsening context bleed. The correct move is to push current_message later while leaving the high-mass sections early.