# Experiment 4: Format Shield

## Hypothesis
The `<` token for XML format crashes at L48 (rank drops to 64K-128K) and takes 12-15 layers to recover. A CDATA block echoing the output format at maximum recency (end of user message) gives the format representation a second chance to survive Phase 5. The `<![CDATA[` sequence is itself rare enough to function as an attention anchor.

## Change
Append a CDATA format echo after the final separator in the user template. This repeats the exact structural pattern from the system prompt's `<output_format>` block.

## Measurement
- `<` token rank trajectory at L48-63: does the crash recover faster?
- Format compliance in outputs (well-formed XML rate)
- Cooking curves: does the CDATA region at end of user message bloom in Phase 5?
- Check that it doesn't create a new attention sink that steals from current_message
