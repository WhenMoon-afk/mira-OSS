# focus Variant Rationale

## Strategy
Add an explicit metacognitive anchor directive at the terminal position of the user template. System prompt unchanged. Code constants unchanged.

## What Changes

### User Template: Terminal `<primary_focus>` Directive

**Added at the end of the user template (after stored_passages, before generation):**
```xml
<primary_focus>All four tasks — entity extraction, passage filtering, query expansion, and complexity — must be grounded in the current user turn above, not the conversational history. The conversation context is for pronoun resolution and topic continuity only. Expand what the user is saying NOW.</primary_focus>
```

This is a single addition — nothing else in the system prompt or user template changes.

## MI Metric Targeted
**Query expansion context bleed** and **current_message aggregate attention** (currently 2.8%, vs conversation_turns at 6.1%).

The metacognitive directive addresses the root behavioral problem directly: the model should attend to conversation_turns for context resolution but ground its output in current_message. The current system prompt already says "bias towards the most recent turns" in the expansion rules, but that rule gets 2.2% attention at the expansion generation position — not enough to override the 6.1% aggregate pull from conversation_turns.

## Why Terminal Position Matters

The `<primary_focus>` directive is placed at the absolute terminal position of the user message — the last tokens before generation begins. In causal attention:

1. Terminal tokens have the shortest causal distance to every generated token
2. The model's residual stream at the generation position is most strongly influenced by the immediately preceding tokens
3. A metacognitive directive ("Your primary task right now is...") at terminal position creates a strong attention anchor because it directly conditions the generation distribution

The existing expansion rule "bias towards the most recent turns" is buried at token position ~middle of the system prompt. By the time generation begins, it's hundreds of tokens back and competing with the output_format examples for attention. The terminal `<primary_focus>` restates the same intent with no competition from subsequent content.

## Mechanistic Hypothesis
- The terminal-position directive should receive disproportionate attention at all generation positions because it's the last content before generation
- It explicitly names "the current user turn" and "conversational history" as distinct concepts, creating a semantic contrast that helps the model route attention correctly
- The word "NOW" at the terminal position is a strong temporal anchor that should activate recency-biased attention patterns
- Expected effect: query expansion should shift from drawing on conversational arc toward grounding in the current message, even without changing token mass ratios

## Design Choices

### Why `<primary_focus>` and not `<instruction>`?
The system prompt already uses `<instruction>` tags. Using the same tag would create attention competition — the model would split attention between two `<instruction>` blocks. `<primary_focus>` is a novel tag that creates its own attention pathway.

### Why list all four tasks?
Naming all four tasks ("entity extraction, passage filtering, query expansion, and complexity") creates token-level connections to each task's generation position. When the model generates entities, the tokens "entity extraction" in the focus directive are available via attention. Same for the other three tasks. This is cross-task reinforcement — a single directive that amplifies attention routing for all four output sections.

### Why "NOW" in caps?
Capitalized tokens break expected casing patterns, marginally increasing their information content and attention draw. It's a small effect but adds to the temporal grounding signal.

## Expected Tradeoffs
- **Positive**: Strongest expected improvement for query expansion grounding. The directive explicitly tells the model to use conversation context for resolution, not as the basis for expansion.
- **Negative**: Adds ~45 tokens. These tokens compete for attention with everything else, slightly diluting the overall attention budget. However, because they're at terminal position, they receive outsized attention relative to their token count.
- **Risk**: The directive could over-correct — making the model ignore conversational context entirely, producing expansions that are too narrow. If the user says "yeah let's keep going with that" and the directive suppresses attention to the conversation that would resolve "that", the expansion would be worse. The phrasing "pronoun resolution and topic continuity" is intended to mitigate this by explicitly permitting context use for those purposes.
- **Risk level**: LOW. The directive adds a clear behavioral instruction that's compatible with existing system prompt rules. The main risk (over-narrowing) is mitigated by the explicit permission for pronoun resolution.