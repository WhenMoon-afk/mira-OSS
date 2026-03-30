# Experiment 5: Passage Compression

## Hypothesis
stored_passages gets 7.68% of terminal attention budget — more aggregate than current_message (4.49%). The model needs passage IDs and enough context for relevance judgment, but full passage text is overkill. Truncating to ID + first ~15 words reduces mass by ~60% while preserving enough signal for topic matching.

## Change
- Testbed `--truncate-passages 15` flag: truncates each passage to first 15 words after the ID
- Same `<stored_passages>` wrapper — don't break the lexical link to task 2 rules
- No prompt template changes needed

## Measurement
- stored_passages % of terminal budget: should drop from 7.68% to ~3-4%
- Does freed attention flow to current_message or to the ChatML sink?
- Passage filtering accuracy: does truncation cause relevant passages to be dropped?
- Context bleed ratio: should improve if freed attention goes to content
