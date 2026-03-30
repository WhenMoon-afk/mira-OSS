# Experiment 3: Task Reminder Elimination

## Hypothesis
task_reminders (97 tokens, 1.71% terminal budget) are a condensed repeat of system prompt rules. Rules are already absorbed in Phase 1 (L0-6) with 6-14x terminal attention. The reminders add 97 tokens of mass to the user message that compete with current_message during Phase 4 re-engagement. If Phase 1 absorption is sufficient, these are deadweight.

## Change
Complete removal of `<task_reminders>` block from user template. Nothing replaces it.

## Measurement
- Context bleed ratio: should improve (97 fewer tokens competing in Phase 4)
- Output quality comparison: entity false-positive rate, expansion quality, passage filtering accuracy
- If quality degrades: which task is affected? That tells us which rule isn't surviving Phase 1 absorption.
- Fallback: if entity FP spikes, try Option D (18-token minimal reminder for entity + expansion only)
