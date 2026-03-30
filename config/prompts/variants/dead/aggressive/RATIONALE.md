# aggressive Variant Rationale

## Strategy
Combine all five individual strategies: trim3 + anchor + strengthen + reorder + focus. This is the maximum-intervention variant.

## Combined Changes

### Code Change (from trim3)
- `CONTEXT_PAIRS = 3` (reduced from 6)

### System Prompt Changes (from strengthen)
- Entity extraction: 4 `<rule>` elements consolidated into single `<entity_constraint>` block with concrete false-positive examples
- Complexity: bias directive promoted from nested `<rule>` to first-class `<complexity_default>` element

### User Template Changes (from anchor + reorder + focus)
- Section order: conversation_turns -> stored_passages -> current_message (reorder)
- Current message wrapped with `┃◆┃ CURRENT TURN ┃◆┃` markers (anchor)
- Terminal `<primary_focus>` directive added after current message (focus)

### Combined User Template Structure
```
1. <conversational_context>{3 pairs}</conversational_context>     [trim3]
2. ---- separator ----
3. <stored_passages>{previous_memories}</stored_passages>          [reorder]
4. ---- separator ----
5. <system_message>Execute...</system_message>
6. ┃◆┃ CURRENT TURN ┃◆┃                                          [anchor]
7. <turn speaker="user">{user_message}</turn>
8. ┃◆┃ END CURRENT TURN ┃◆┃                                      [anchor]
9. ---- separator ----
10. <primary_focus>...</primary_focus>                             [focus]
```

## Interaction Analysis

### Positive Interactions (Reinforcing)

1. **trim3 + reorder**: Reducing conversation_turns token count (trim3) AND moving current_message to terminal position (reorder) are complementary. trim3 reduces the numerator of the token mass ratio while reorder boosts the current_message's positional advantage. These operate on different axes (mass vs position) and should compound: trim3 reduces aggregate ratio from 3.1x toward ~2.0x via mass, reorder further reduces it via positional advantage.

2. **anchor + reorder**: The rare-token markers around current_message (anchor) combined with terminal positioning (reorder) create a double salience boost. The rare tokens force attention allocation at the boundary, and the terminal position provides recency advantage. These should compound — the rare tokens are MORE effective at terminal position because the recency gradient amplifies their already-high per-token density.

3. **focus + reorder**: The `<primary_focus>` directive (focus) explicitly names the current turn as the grounding target. When placed after current_message at absolute terminal position (reorder puts current_message last, focus adds the directive after it), the focus directive is the FINAL content before generation. It directly precedes the generation distribution and benefits maximally from the recency gradient.

### Potentially Negative Interactions

4. **anchor + focus**: Both add tokens to the current_message region. The anchor markers add ~10-12 tokens and the focus directive adds ~45 tokens. Together that's ~57 new tokens. This slightly increases the total token count in the current_message neighborhood, but since these tokens are AT or NEAR terminal position, they benefit from the recency gradient and shouldn't dilute attention — they should concentrate it. LOW RISK.

5. **trim3 + passage filtering**: With only 3 conversation pairs, the model has less context to judge whether a stored passage is still relevant. If the user discussed topic A 4-5 turns ago and the passage relates to topic A, the model might over-retain (the absence of evidence isn't evidence of absence — it won't see the topic drift that happened in turns 4-6). Combined with reorder moving stored_passages away from terminal position, passage filtering takes a double hit. MEDIUM RISK — this is the most concerning interaction.

6. **strengthen (entity_constraint) + short context (trim3)**: The consolidated entity constraint includes concrete false-positive examples ("Father", "subcortical", "PATCHNOTE"). With less conversational context (3 pairs instead of 6), the model has fewer tokens to judge whether a word is a proper noun in context. However, the constraint is a procedural test ("would spaCy tag this?") that doesn't depend on context length. LOW RISK.

### Novel Risk: Over-Focusing

The aggressive variant applies FOUR separate mechanisms to boost current_message salience (trim token mass, reorder to terminal, anchor with rare tokens, explicit focus directive). There's a real possibility this over-corrects:

- Expansion becomes too narrow, losing beneficial context from conversation history
- Entity extraction becomes too focused on current turn, missing entities mentioned in assistant responses
- Passage filtering becomes unreliable due to insufficient context

This variant should be tested with the "Alright. I shall return." class of messages (where context bleed was worst) AND with multi-turn reference messages (where context is necessary) to see if the over-correction creates new failure modes.

## MI Metrics Targeted (All)

| Metric | Baseline | Targeted Change | Mechanism |
|--------|----------|-----------------|-----------|
| conv_turns/curr_msg aggregate ratio | 3.1x | < 1.5x | trim3 (mass) + reorder (position) |
| current_message aggregate attention | 2.8% | > 8% | reorder + anchor + focus |
| Entity rules at entity gen | 3.5% | > 5% | strengthen (consolidation) |
| Complexity bias attention | 0.19% (below uniform 0.57%) | > 0.57% | strengthen (structural promotion) |
| Terminal-position current_message density | 0.69/1K tok | > 1.5/1K tok | anchor + reorder + focus |

## Expected Net Token Count Changes
- trim3: removes ~300-600 tokens from conversation_turns
- anchor: adds ~12 tokens (markers)
- strengthen: removes ~10 tokens (consolidated rules are slightly shorter)
- reorder: zero change (rearrangement only)
- focus: adds ~45 tokens (terminal directive)
- **Net**: ~250-550 fewer tokens overall

## Risk Level: MEDIUM-HIGH
This is intentionally the most aggressive variant. The individual strategies are each LOW-MEDIUM risk, but combining them creates interaction risks (especially trim3 + reorder affecting passage filtering) and over-correction risk (four mechanisms all boosting current_message). The aggressive variant is designed to establish the upper bound of intervention — if it over-corrects, we can dial back to a subset of the individual strategies.