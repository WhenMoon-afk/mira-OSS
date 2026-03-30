# Examples Variant

## Strategy
Built on composite base (anchor + trim3 + strengthen). Tests whether better few-shot expansion examples improve query expansion quality, especially for short/ambiguous messages.

## Changes from Composite

### System Prompt — Expansion Examples
Added two new examples targeting known failure modes. Kept original first and fourth examples. Total: 4 examples (up from 3).

**New example 1**: Short pronoun-heavy message with context hint.
```
User: "yeah let's keep going with that"
Context hint: Conversation was about garage workshop layout
Expansion: garage workshop organization and layout planning; workbench placement and tool storage arrangement; workspace optimization for electronics projects
```
Targets the "yeah let's do that" class of messages where the model must dereference pronouns to produce useful expansions. The `<context_hint>` element is new — teaches the model to use conversation context for dereferencing without drifting.

**New example 2**: Short departure message with context hint.
```
User: "Alright. I'll be back in a bit."
Context hint: Conversation was about debugging a deployment issue
Expansion: taking a break from debugging session; stepping away from deployment troubleshooting; returning to resume technical problem-solving
```
Directly targets the "Alright. I shall return." failure class where production expansions drifted to MIRA architecture topics instead of the current conversational context.

### Why `<context_hint>`
The new examples include `<context_hint>` elements that are NOT present in production user messages. This is intentional — the examples teach the model the *reasoning pattern* (use context to interpret short messages) without requiring structural changes to the user template. The model sees the hint in the example and applies the same reasoning to the actual conversation context.

## Predicted Effects
- Better expansion quality on short/ambiguous messages
- Reduced arc-drift on departure/return messages
- MI: expansion example attention should remain at strengthen's 3.17% level (same structural base)
- Behavioral: expansion word count may increase on short messages (more targeted content)

## Risk
- Adding a 4th example adds ~50 tokens to the system prompt
- The `<context_hint>` element is novel XML that could confuse the model into expecting it in user messages
