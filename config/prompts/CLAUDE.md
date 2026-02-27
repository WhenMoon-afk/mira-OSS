# config/prompts/ — LLM Prompt Templates

Prompt templates for all LLM-powered subsystems. Each file is a plain text template loaded at service initialization time. Convention: `_system.txt` = system message (instructions/rules), `_user.txt` = user message template (runtime data placeholders).

## Files

### LT_Memory Pipeline
- **`memory_extraction_system.txt`** / **`memory_extraction_user.txt`** — Extracts durable memories from conversation segments. Variables: `{formatted_messages}`. Consumer: `lt_memory/processing/extraction_engine.py`
- **`memory_extraction_system_v1.txt`** / **`memory_extraction_user_v1.txt`** — Legacy v1 extraction (atomicity model vs v2 pre-stitching). Not used in production
- **`memory_consolidation_system.txt`** — Single-pass consolidation: receives a group of similar memories, outputs multi-group merge decisions with independent_ids for rejection tracking. No user template file — user prompt constructed inline in `lt_memory/refinement.py:build_consolidation_payload()`. Consumer: `lt_memory/refinement.py`, `lt_memory/batch_result_handlers.py`, `lt_memory/processing/post_processing_orchestrator.py`
- **`memory_relationship_classification.txt`** — Combined system prompt (no _system/_user split) for classifying memory relationships (supports/conflicts/supersedes/refines/precedes/contextualizes/null). Consumer: `lt_memory/linking.py`
- **`entity_gc_system.txt`** / **`entity_gc_user.txt`** — Entity garbage collection: per-entity decisions (canonical/merge/delete/keep) for groups of similar entities. XML structured output. User template variable: `{groups}` (filled with `<group>/<entity>` XML). Consumer: `lt_memory/entity_gc.py`

### CNS Services
- **`segment_summary_system.txt`** / **`segment_summary_user.txt`** — Continuity Engine diarist. First-person memory traces for segment collapse. The largest prompt (~11KB). Variables: `{current_time}`, `{previous_summaries}`, `{conversation_text}`, `{tools_used}`. Consumer: `cns/services/summary_generator.py`
- **`synthesis_summary_system.txt`** / **`synthesis_summary_user.txt`** — Merges multi-chunk partial summaries into unified memory. Consumer: `cns/services/summary_generator.py`
- **`assessment_extraction_system.txt`** / **`assessment_extraction_user.txt`** — Evaluates conversation against system prompt sections, producing alignment/misalignment/contextual_pass signals with evidence. XML output. Consumer: `cns/services/assessment_extractor.py`
- **`thinking_block_instructions.txt`** — Conditional instructions for assessing thinking traces (included when thinking content > 70%). Consumer: `cns/services/assessment_extractor.py`
- **`user_model_synthesis_system.txt`** / **`user_model_synthesis_user.txt`** — Evolves user model observations from assessment signals. Produces section-anchored observations about the user. XML output. Consumer: `cns/services/user_model_synthesizer.py`
- **`user_model_critic_system.txt`** / **`user_model_critic_user.txt`** — Quality critic for user model validation. Checks for observation laundering, personality labels, contradictions. Pass/fail XML output. Consumer: `cns/services/user_model_synthesizer.py`
- **`subcortical_system.txt`** / **`subcortical_user.txt`** — Pre-LLM IR: entity extraction, passage filtering, query expansion, complexity assessment. XML output. Consumer: `cns/services/subcortical.py`
- **`domaindoc_summary_system.txt`** / **`domaindoc_summary_user.txt`** — One-sentence section summaries (max 100 chars). Plain text output. Consumer: `cns/services/domaindoc_summary_service.py`
- **`peanutgallery_prerunner.txt`** / **`peanutgallery_system.txt`** / **`peanutgallery_user.txt`** — Three-file pipeline: prerunner filters seed memories, system defines metacognitive observer (noop/compaction/concern/coaching), user sends conversation + memory context. Consumer: `cns/services/peanutgallery_model.py`

## Patterns to Follow

### Naming Convention
- `{feature}_system.txt` — System message (instructions, rules, output format)
- `{feature}_user.txt` — User message template with `{variable}` placeholders
- Exceptions: `memory_relationship_classification.txt` (combined, no split), `peanutgallery_prerunner.txt` (third file for fast filter stage)

### Template Variables
Use Python f-string style `{variable_name}` filled via `.format()` at runtime. Use double-brace `{{` / `}}` for literal braces in JSON examples (see `entity_gc_user.txt`).

### Output Format Conventions
- **XML with `<mira:*>` namespace**: Feedback signals, patterns, subcortical analysis, peanut gallery, summaries (display_title, complexity)
- **JSON**: Consolidation, relationship classification
- **Plain text**: Domaindoc summaries

### Input Data Wrapping
Wrap runtime data in descriptive XML tags within user templates: `<conversation>`, `<existing_memories>`, `<stored_passages>`, `<pinned_memories>`, etc.

### Loading Pattern
Each consumer service loads its own prompts — there is no centralized loader. The standard pattern:
```python
prompts_dir = Path("config/prompts")
with open(prompts_dir / "feature_system.txt") as f:
    self.system_prompt = f.read().strip()
```
Loaded once at `__init__` time, fail-fast with `FileNotFoundError` if missing.

### Adding New Prompts
1. Create `{feature}_system.txt` and `{feature}_user.txt` in this directory
2. Load them in the consuming service's `__init__` using the pattern above
3. Use `{variable}` placeholders in the user template
4. Use `<mira:*>` XML tags for structured output that needs parsing
