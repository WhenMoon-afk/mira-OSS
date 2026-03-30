# Experiment: Output Format as Active Instruction

## Hypothesis
The CDATA output_format block peaks at L48 and directly shapes generation during Phase 5 (output prep). It is the strongest implicit instruction surface because it demonstrates what the output should look like at the exact point in the forward pass where the model decides what to generate. Currently it undermines the "default is complex" rule by showing `<complexity>straightforward</complexity>` as the example value. Every example value in the format IS a default instruction.

Changing three values in the format block — `None` for entities, `current turn topic` for first expansion phrase, `complex` for complexity — aligns the format's implicit instruction with the explicit rules. No rule text changes. This is a pure signal-alignment change: make Phase 5's strongest instruction carrier reinforce rather than contradict Phase 1's absorbed rules.

## Changes
- Removed `<ir_task>`, `<task id="N" name="...">`, `</task>` XML wrappers (shared across all round 3 variants — structural noise with no instructional value)
- `<entities><named_entity>Name</named_entity></entities>` → `<entities>None</entities>`
  (reinforces "None when no matches" as the default)
- `<query_expansion>phrase1; phrase2; phrase3</query_expansion>` → `<query_expansion>current turn topic; contextual phrase; contextual phrase</query_expansion>`
  (reinforces "first phrase = current turn's topic" directly in format)
- `<complexity>straightforward</complexity>` → `<complexity>complex</complexity>`
  (aligns with "default is complex" rule)

## What to Measure
- Complexity distribution: should shift back toward baseline 80% complex (from composite's 65%)
- Entity default behavior: should see more "None" outputs when no proper nouns present
- Expansion first-phrase relevance: should more consistently describe current turn
- Format compliance: must remain 100% (if the model starts emitting "current turn topic" literally, the change backfired)

## What to Watch For
- Model emitting the example text literally ("current turn topic" as an actual phrase) instead of treating it as a pattern to fill — this would mean the model is copying the format rather than following it as a template
- Entity extraction becoming too conservative if "None" as default suppresses legitimate entities
