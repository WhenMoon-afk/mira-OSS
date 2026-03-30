# Subcortical Prompt Variants

Prompt restructuring variants based on mechanistic interpretability analysis of Qwen3-32B attention patterns on the subcortical IR system prompt. Each variant targets specific attention pathologies identified through 20-sample forward pass analysis with attention hooks across all 64 layers.

## Baseline Pathologies (Empirical)

| Finding | Measurement | Impact |
|---------|-------------|--------|
| Context bleed | conv_turns 3.1x aggregate vs current_message | Query expansion drifts to conversational arc |
| Complexity rule decorative | 0.19% attention (below uniform 0.57%) | No influence on complexity decisions |
| Entity rules weak | 3.5% at entity generation positions | False positives from in-context patterns |
| L48 directive crash | `<` rank crashes layer 48, recovers L60 | Format compliance via recovery, not stability |

## v1 MI Results (20-sample, B200 GPU, 2026-03-01)

| Variant | Bleed Ratio | Delta | Exp Examples | `<` Rank L63 | Verdict |
|---------|------------|-------|-------------|-------------|---------|
| baseline | 2.34x | -- | 0.44% | 4 | -- |
| **anchor** | **1.38x** | **-41%** | 0.46% | 31 | WINNER |
| **trim3** | **1.76x** | **-25%** | 0.37% | 4 | WINNER |
| **strengthen** | 2.26x | -3% | **3.17%** | 3 | WINNER (expansion) |
| focus | 2.78x | +19% | 0.45% | 34,188 | CATASTROPHIC |
| reorder | N/A | N/A | N/A | 26 | UNMEASURABLE |
| aggressive | N/A | N/A | 3.23% | 29,092 | CATASTROPHIC |
| **composite** | TBD | TBD | TBD | TBD | NEXT TEST |

## v2 Findings: Rule Attention Below Uniform

All four task rule sections receive BELOW uniform attention at their own generation positions:

| Rule Section | Attention at Gen Position | Relative to Uniform |
|---|---|---|
| T1 entity rules | — | 0.3x uniform |
| T2 passage rules | — | 0.1x uniform (worst) |
| T3 expansion rules | — | 0.2x uniform |
| T4 complexity rules | — | 0.2x uniform |
| Output format examples | 4.19% at complexity_gen | CAUSAL |
| Expansion few-shot examples | 4.56% at expansion_gen | CAUSAL |

Rules are decorative. Examples teach the model.

## Variant Summary

| Variant | Changes | Target Metric | Confidence | Risk |
|---------|---------|---------------|------------|------|
| **trim3** | CONTEXT_PAIRS 6->3 | Token mass ratio 9.5x -> ~4.75x | HIGH (arithmetic) | LOW |
| **anchor** | Rare tokens around current_message | Per-token density boost | MODERATE (mechanistic) | LOW-MEDIUM |
| **strengthen** | Entity + complexity rule restructure | Entity 3.5% -> >5%, complexity >uniform | MODERATE | LOW-MEDIUM |
| **reorder** | current_message to terminal position | Recency gradient for current turn | MODERATE-HIGH | LOW-MEDIUM |
| **focus** | Terminal metacognitive directive | Query expansion grounding | MODERATE | LOW |
| **aggressive** | All combined | All metrics simultaneously | VARIES | MEDIUM-HIGH |
| **composite** | anchor + trim3 + strengthen | Bleed ratio + expansion quality | HIGH | LOW-MEDIUM |
| **tighten** | composite + rule rewording | Expansion grounding, entity precision | MODERATE (behavioral) | LOW |
| **examples** | composite + context_hint few-shot | Short/ambiguous message expansion | MODERATE (behavioral) | LOW |
| **diamonds** | tighten + ║⊕║ markers on T2/T3 rules | Rule attention 0.1-0.2x -> above uniform | MODERATE (untested on sys prompt) | LOW-MEDIUM |
| **showdonttell** | tighten + remove T2/T4 rules + 3rd output example | Free attention budget, strengthen examples | HIGH (strengthen precedent) | LOW |

## File Structure

Each variant directory contains:
- `subcortical_system.txt` — Complete deployable system prompt
- `subcortical_user.txt` — Complete deployable user template
- `RATIONALE.md` — MI-grounded rationale, mechanistic hypothesis, and risk analysis

## Testing Plan

Run each variant through the tuning harness (`scripts/tuning_harnesses/subcortical_tuning_test.py`) with identical seeds and then through the MI pipeline (`scripts/tuning_harnesses/mech_interp/`) to measure attention distribution changes.

### Behavioral Testing (tuning harness)
- Same 20 samples, same seed
- Compare: query expansion quality, entity false-positive rate, passage retention decisions, complexity accuracy

### Mechanistic Testing (MI pipeline)
- Same 20 samples through prep_inputs.py -> run_analysis.py
- Compare: aggregate attention ratios, per-token density, per-region attention at generation positions
- Specific diagnostic: conv_turns/curr_msg ratio, entity rule attention at entity_gen, complexity bias attention at complexity_gen

### Critical Test Cases
- **"Alright. I shall return."** class: Short messages where context bleed was worst. All variants should reduce expansion drift.
- **Multi-turn reference**: "yeah let's keep going with that" class. trim3 and aggressive variants risk losing necessary context.
- **Entity edge cases**: Capitalized non-entities (RAPT, PATCHNOTE). strengthen and aggressive should reduce false positives.

## Code Changes Required

### trim3 and aggressive
Require `CONTEXT_PAIRS = 3` in `cns/services/subcortical.py`. Options:
1. Change the constant directly (simplest, but hard to A/B test)
2. Make it configurable via `config.py` (allows runtime switching)
3. Pass as parameter to `SubcorticalLayer.__init__()` (allows harness control)

Option 3 is recommended for testing: the harness can pass different values per variant run without touching production config.

### All variants
The tuning harness already loads prompts from files. To test variants, pass `--system-prompt` and `--user-template` paths pointing to the variant directory.