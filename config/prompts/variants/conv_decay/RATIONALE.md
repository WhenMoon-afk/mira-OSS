# Experiment 1: Conversation Decay

## Hypothesis
conversation_turns (264 tokens, 5.73% terminal budget) competes with current_message (64 tokens, 4.49%) during Phase 4 re-engagement (L32-47). Token mass wins. Reducing conversation mass to ~100 tokens should flip the ratio.

## Change
Two-tier conversation structure:
- Most recent turn pair: full verbatim text
- Older turns: compressed to topic keywords only (nouns/entities extracted from turn text)
- Tiers separated by `║◇║` rare-token markers (proven attention mechanism from anchor variant)

## Template Variables
- `{older_context}` — keyword-compressed older turns (replaces part of `{conversation_turns}`)
- `{recent_turns}` — most recent turn pair in full text
- Requires testbed `--conversation-decay` flag

## Measurement
- Context bleed ratio at L32-47 (not just terminal)
- current_message should dominate earlier in Phase 4
- Cooking curves: conversation_turns peak should shrink or shift
