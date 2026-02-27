# HyDE Tuning Findings — Session 2026-02-07

## Executive Summary

HyDE (Hypothetical Document Embedding) shows promise for cross-domain memory linking,
but this session was dominated by infrastructure and model-behavior issues rather than
meaningful prompt tuning. The core experiment — does implication expansion surface
genuinely useful memories that raw embedding similarity misses? — remains partially
answered. Early results suggest YES for certain memory types, but the signal is buried
under model limitations and memory pool homogeneity.

---

## Infrastructure Issues Resolved

Before any tuning could happen, three schema issues had to be fixed:

1. **Missing `annotations` column** on `memories` table — added column + set default to `[]::jsonb`
2. **Missing `global_memories` table** — created empty table with required columns
3. **RLS permissions** — granted SELECT on `global_memories` to `mira_dbuser` and `mira_admin`

These should be addressed in a proper migration to avoid blocking future test runs.

---

## Model Behavior: qwen3 Thinking Mode Problem

### The Core Issue

qwen3 models (both 1.7b and 4b) have an aggressive "thinking mode" that undermines
the entire implication generation pipeline:

- **qwen3:1.7b via OpenAI-compat API**: All 200 tokens consumed by reasoning in a
  separate `reasoning` field. The `content` field returns empty. 100% failure rate.

- **qwen3:4b with `think: false` via native API**: Thinking is partially suppressed,
  but the model frequently "bleeds" reasoning into the content field mid-output.
  Typical pattern: 30-40 tokens of useful expansion, then "Wait, I think..." or
  "Let me check..." followed by meta-reasoning that consumes the remaining budget.

### Workarounds Attempted

| Approach | Result |
|----------|--------|
| Increase `max_tokens` to 1000 | Works for 1.7b (reasoning + output fits), but wastes ~800 tokens on thinking per call |
| `think: false` on Ollama native API | Partially works for 4b, unreliable — reasoning bleeds into content |
| `/no_think` suffix in user message | No effect |
| `chat_template` parameter | No effect via OpenAI-compat endpoint |
| Assistant pre-fill ("Relevant to") | Forces correct start but model breaks format after ~40 tokens |
| Few-shot example + pre-fill | Best results, but reasoning bleed persists |
| Tight token budget (80-100) | Cuts off output before reasoning bleed, but also truncates useful content |
| Post-processing truncation | Added patterns to `clean_llm_response()` to strip reasoning bleed — works but feels fragile |

### Recommendation

**Switch away from qwen3 for this task.** The thinking mode behavior is a fundamental
model architecture issue, not a prompt problem. Every workaround adds fragility and
wastes engineering effort that should go toward prompt tuning.

Good candidates for replacement:
- **Llama 3.2 3B** — no thinking mode, follows instructions well at small sizes
- **Phi-3.5 mini (3.8B)** — Microsoft's small model, good instruction following
- **Gemma 2 2B/9B** — Google's small models, clean output format
- **Mistral 7B** — well-established instruction following

The key requirements for the implication model:
1. No thinking/reasoning mode that contaminates output
2. Follows few-shot format reliably (copies example length and style)
3. Small enough for fast inference (~1-2s per memory)
4. Understands domain context well enough to distinguish motorcycles from bicycles

---

## Prompt Tuning Findings

### Baseline Prompt (v1)

```
System: XML-structured task with <directive> and <example>
Example: "Annika is vegetarian" → "Relevant to meal planning, restaurant selection,
         dietary accommodations, food-related gift choices"
Prefill: "Relevant to"
```

**Implication Quality Tally (10 samples):**

| Type | Count | Samples |
|------|-------|---------|
| contextual_expansion | 3 | 6, 7, 10 |
| paraphrase | 5 | 1, 2, 4, 5, 8 |
| too_generic | 1 | 3 |
| off_topic | 1 | 9 (model thought motorcycle riding was mountain biking) |

**Discovery Quality Tally (43 total implication-only discoveries):**

| Type | Count | Ratio |
|------|-------|-------|
| genuine_cross_domain | 18 | 42% |
| topically_adjacent | 10 | 23% |
| noise | 15 | 35% |

**Key metrics:** Avg overlap 22.3%, avg implication-only count 4.3

### Revised Prompt (v2) — Few-Shot + Causal Framing

```
System: Plain text, no XML. "decisions or situations where someone would act
        differently BECAUSE of this fact"
Example: Same Annika example but with more specific, actionable output
         ("checking ingredient lists when bringing desserts to her place")
Format: Few-shot (user/assistant pair) instead of XML example
Prefill: "choosing"
Max tokens: 100 (down from 200)
```

**Key metrics:** Avg overlap 40.2%, avg implication-only count 3.7

**Assessment:** Overlap increased but for the wrong reason — implications were CLOSER
paraphrases of the original, not better expansions. The model learned "describe the
specific activities of the topic" from the example, not "name unrelated situations
where this matters."

### Root Cause Analysis: Why Paraphrases Dominate

The 4b model cannot reliably make the conceptual leap from "fact about someone" to
"unrelated situation where this fact changes a decision." This is a reasoning capability
issue, not just a prompt issue. Evidence:

1. The Annika example itself shares vocabulary between input and output (vegetarian →
   meal planning, dietary, food). The model learns surface-level association.
2. When given "Tail of the Dragon" (motorcycle riding), the model generates cycling/
   mountain biking implications — it lacks the domain knowledge to interpret correctly.
3. Even with explicit instruction "output must share NO words with input," the model
   still produces topically adjacent output rather than truly cross-domain connections.

A larger model (7B+) with better world knowledge and reasoning would likely produce
qualitatively different expansions.

---

## Memory Pool Assessment

### Homogeneity Problem

Both seed 42 and seed 99 samples were heavily skewed toward MIRA development memories.
With seed 42:

- 8/10 memories about software development (MIRA architecture, testing, TUI, etc.)
- 1/10 education (C++ homework)
- 1/10 personal (Tail of the Dragon motorcycle riding)

All memories had importance=0.50 and access_count=0, providing no variance on those
dimensions.

### Impact on HyDE Evaluation

Cross-domain linking REQUIRES cross-domain memories to exist in the pool. When 80% of
memories are about the same topic (MIRA development), even a perfect implication
expansion would find topically adjacent memories rather than genuinely cross-domain
ones. The implication search for "MIRA developer debugging WebSocket" will always find
other MIRA development memories regardless of expansion quality.

The one genuinely interesting result was Sample 9 (Tail of the Dragon), where despite
the model misidentifying the domain as cycling, the implication embedding still surfaced
a Pocahontas County motorcycle road memory. This suggests HyDE CAN work for truly
cross-domain linking when the memory pool has diverse content.

### What's Needed

Import memories covering: relationships/people, places/travel, health/fitness,
food preferences, work (non-MIRA), hobbies, calendar events, emotional states.
The more diverse the pool, the more meaningful the cross-domain evaluation becomes.

---

## What Worked

1. **Ollama native API with `think: false`** — partially effective for suppressing reasoning
2. **Assistant pre-fill** — reliably forces the model to start in the right output format
3. **Few-shot over XML examples** — cleaner format for small models
4. **Reasoning bleed truncation** — `clean_llm_response()` now strips untagged meta-reasoning
5. **The experimental methodology itself** — single-variable changes with fixed seed, reading
   actual texts not just metrics, tallying quality categories

## What Didn't Work

1. **qwen3 thinking mode suppression** — fundamentally unreliable across both model sizes
2. **Tight token budgets as reasoning prevention** — cuts off useful content too
3. **"No words in common" instruction** — model ignores this constraint entirely
4. **Generic prefills like "choosing"** — don't prevent reasoning bleed reliably

---

## Next Steps

1. **Switch to a non-qwen model** (Llama 3.2 3B, Phi-3.5 mini, Gemma 2, or Mistral 7B)
2. **Import diverse memories** to enable genuine cross-domain evaluation
3. **Re-run baseline** with new model + diverse pool (same seed)
4. **Then** start real prompt tuning — the dominant failure mode may change entirely
   with a model that follows instructions cleanly

---

## Raw Data Files

- Baseline (qwen3:4b, v1 prompt): `data/hyde_tuning_20260207_060359.md` / `.json`
- Run 2 (qwen3:4b, v2 prompt): `data/hyde_tuning_20260207_060748.md` / `.json`
- Failed run (qwen3:1.7b, 100% empty): `data/hyde_tuning_20260207_055812.md` / `.json`
