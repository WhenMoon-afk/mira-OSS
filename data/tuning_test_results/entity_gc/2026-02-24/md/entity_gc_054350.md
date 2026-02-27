# Entity GC Tuning Test Results
Generated: 2026-02-24 05:43:50

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Similar pairs found | 408 |
| Groups formed | 10 |
| Total entities in groups | 78 |
| Avg group size | 7.8 |
| Parse success | Yes |
| Valid groups | 9/9 |

### Action Distribution

| Action | Count | Rate |
|--------|-------|------|
| canonical | 8 | 10.3% |
| merge | 30 | 38.5% |
| delete | 12 | 15.4% |
| keep | 19 | 24.4% |

### Global Violations

- 9 input entities missing from response: 232a7653 (Greenbrier Valley), 95c8862a (Greenbrier valley), cd21264d (Greenbrier River), 8a7dd376 (Greenbrier), 4da94d71 (Greenbrier Valley's), e6af9779 (Greenbrier River Trail), b33b146c (Greenbrier valley's), 928166a8 (Greenbrier Trail), 33283ebc (the Greenbrier River Trail)

### Config Values Used

| Parameter | Value |
|-----------|-------|
| similarity_threshold | 0.6 |
| gc_max_tokens | 2048 |
| gc_temperature | 0.2 |

---

## Group 1 of 10 (11 entities)

### Input Entities
- **b2c4500b** — "Opus 4.5" (ORG, 5 links)
- **cab9ed3b** — "Opus 4.5" (LAW, 6 links)
- **a5f7f30b** — "Opus 4.5's" (GPE, 5 links)
- **af0163b6** — "Opus 5" (WORK_OF_ART, 1 links)
- **c76b7d04** — "Opus 4.0" (ORG, 5 links)
- **229ae67b** — "Opus 4.5" (FAC, 3 links)
- **6789d4fb** — "Opus 4.5" (WORK_OF_ART, 4 links)
- **0db4d552** — "Opus 4.0" (WORK_OF_ART, 1 links)
- **7ebdf5ec** — "Opus" (ORG, 7 links)
- **263968c6** — "Opus" (PERSON, 1 links)
- **44711238** — "Opus 3.0" (WORK_OF_ART, 1 links)

### LLM Decisions
- [MERGE ->] b2c4500b — "Opus 4.5"
- [CANONICAL] cab9ed3b — "Opus 4.5"
- [MERGE ->] a5f7f30b — "Opus 4.5's"
- [keep] af0163b6 — "Opus 5"
- [keep] c76b7d04 — "Opus 4.0"
- [MERGE ->] 229ae67b — "Opus 4.5"
- [MERGE ->] 6789d4fb — "Opus 4.5"
- [keep] 0db4d552 — "Opus 4.0"
- [keep] 7ebdf5ec — "Opus"
- [keep] 263968c6 — "Opus"
- [keep] 44711238 — "Opus 3.0"

---

## Group 2 of 10 (10 entities)

### Input Entities
- **1d7374b2** — "Owens Cross" (ORG, 1 links)
- **9c71513f** — "Owens Cross Roads," (ORG, 1 links)
- **9e916933** — "Owens Cross" (FAC, 1 links)
- **b9591537** — "Owens Cross Roads" (FAC, 50 links)
- **68934703** — "Owens Cross Roads" (ORG, 58 links)
- **47a6ee36** — "Owens Cross Roads:" (ORG, 1 links)
- **d442a536** — "Owens Cross Roads/" (FAC, 1 links)
- **584208bb** — "Owens Cross Roads/Hampton Cove" (ORG, 1 links)
- **cd4588a8** — "Huntsville/Owens Cross Roads" (ORG, 1 links)
- **95c3bad2** — "Owens Cross Roads, AL" (ORG, 1 links)

### LLM Decisions
- [MERGE ->] 1d7374b2 — "Owens Cross"
- [MERGE ->] 9c71513f — "Owens Cross Roads,"
- [MERGE ->] 9e916933 — "Owens Cross"
- [MERGE ->] b9591537 — "Owens Cross Roads"
- [CANONICAL] 68934703 — "Owens Cross Roads"
- [MERGE ->] 47a6ee36 — "Owens Cross Roads:"
- [MERGE ->] d442a536 — "Owens Cross Roads/"
- [DELETE] 584208bb — "Owens Cross Roads/Hampton Cove"
- [DELETE] cd4588a8 — "Huntsville/Owens Cross Roads"
- [MERGE ->] 95c3bad2 — "Owens Cross Roads, AL"

---

## Group 3 of 10 (9 entities)

### Input Entities
- **5bd43276** — "MIRA" (ORG, 65 links)
- **51abd7c8** — "'mira'" (PERSON, 1 links)
- **802a27ae** — "MIRA VM" (ORG, 1 links)
- **81d39593** — "MIRA AI" (ORG, 1 links)
- **b0760294** — "MIRA" (PERSON, 4 links)
- **ad298feb** — "Mira" (ORG, 2 links)
- **f94d12cf** — "Mira AI" (ORG, 1 links)
- **4928719b** — "Mira" (PERSON, 5 links)
- **be8a092b** — "Mira" (GPE, 27 links)

### LLM Decisions
- [CANONICAL] 5bd43276 — "MIRA"
- [MERGE ->] 51abd7c8 — "'mira'"
- [MERGE ->] 802a27ae — "MIRA VM"
- [MERGE ->] 81d39593 — "MIRA AI"
- [keep] b0760294 — "MIRA"
- [MERGE ->] ad298feb — "Mira"
- [MERGE ->] f94d12cf — "Mira AI"
- [keep] 4928719b — "Mira"
- [keep] be8a092b — "Mira"

---

## Group 4 of 10 (9 entities)

### Input Entities
- **232a7653** — "Greenbrier Valley" (GPE, 21 links)
- **4da94d71** — "Greenbrier Valley's" (GPE, 4 links)
- **b33b146c** — "Greenbrier valley's" (GPE, 2 links)
- **8a7dd376** — "Greenbrier" (GPE, 46 links)
- **95c8862a** — "Greenbrier valley" (GPE, 12 links)
- **cd21264d** — "Greenbrier River" (GPE, 2 links)
- **928166a8** — "Greenbrier Trail" (FAC, 1 links)
- **33283ebc** — "the Greenbrier River Trail" (FAC, 13 links)
- **e6af9779** — "Greenbrier River Trail" (FAC, 12 links)

### LLM Decisions
- [MERGE ->] 44db1fd6 — "Claude-Opus-4-20250514"
- [MERGE ->] f8ffcbf9 — "Claude Opus-4-20250514"
- [MERGE ->] edb5260e — "Claude Opus 4"
- [CANONICAL] 1b1acd58 — "Claude Opus 4.5"
- [MERGE ->] ad105817 — "Claude Opus 4.5"
- [MERGE ->] 666b3674 — "Claude Opus"
- [MERGE ->] b189f1cd — "Claude Opus 4.5"

---

## Group 5 of 10 (7 entities)

### Input Entities
- **44db1fd6** — "Claude-Opus-4-20250514" (PERSON, 1 links)
- **f8ffcbf9** — "Claude Opus-4-20250514" (PERSON, 1 links)
- **edb5260e** — "Claude Opus 4" (PERSON, 4 links)
- **1b1acd58** — "Claude Opus 4.5" (PERSON, 15 links)
- **ad105817** — "Claude Opus 4.5" (ORG, 1 links)
- **666b3674** — "Claude Opus" (PERSON, 8 links)
- **b189f1cd** — "Claude Opus 4.5" (PRODUCT, 2 links)

### LLM Decisions
- [MERGE ->] 1c16df7e — "Raspberry Pi"
- [CANONICAL] 79e79fd5 — "Raspberry Pi"
- [keep] 9df7cbbb — "Raspberry Pi 5"
- [keep] 470a5056 — "Raspberry Pi"
- [MERGE ->] 96857ea9 — "a Raspberry Pi"
- [keep] d23627cb — "Raspberry Pi microSD"
- [keep] 6a6e35c1 — "Raspberry Pi SD"

---

## Group 6 of 10 (7 entities)

### Input Entities
- **1c16df7e** — "Raspberry Pi" (WORK_OF_ART, 2 links)
- **79e79fd5** — "Raspberry Pi" (ORG, 11 links)
- **9df7cbbb** — "Raspberry Pi 5" (PRODUCT, 1 links)
- **470a5056** — "Raspberry Pi" (PERSON, 5 links)
- **96857ea9** — "a Raspberry Pi" (ORG, 3 links)
- **d23627cb** — "Raspberry Pi microSD" (PRODUCT, 1 links)
- **6a6e35c1** — "Raspberry Pi SD" (ORG, 9 links)

### LLM Decisions
- [MERGE ->] b6eaded5 — "Claude Sonnet"
- [CANONICAL] cbc9210e — "Claude Sonnet"
- [keep] 6fd4cdc3 — "Claude Sonnet 3.5"
- [keep] ead412d4 — "Claude Sonnet 4.5"
- [DELETE] 36467beb — "Refining Claude Sonnet"
- [DELETE] 6cdeb5dc — "Refining Claude Sonnet 3.5"
- [DELETE] a006f062 — "Refining Claude"

---

## Group 7 of 10 (7 entities)

### Input Entities
- **b6eaded5** — "Claude Sonnet" (PRODUCT, 1 links)
- **cbc9210e** — "Claude Sonnet" (PERSON, 5 links)
- **6fd4cdc3** — "Claude Sonnet 3.5" (PERSON, 1 links)
- **ead412d4** — "Claude Sonnet 4.5" (PERSON, 1 links)
- **36467beb** — "Refining Claude Sonnet" (PERSON, 1 links)
- **6cdeb5dc** — "Refining Claude Sonnet 3.5" (PERSON, 1 links)
- **a006f062** — "Refining Claude" (PERSON, 2 links)

### LLM Decisions
- [DELETE] da3725bd — "Claude/Mira"
- [DELETE] f3d8d797 — "Claude/MIRA"
- [DELETE] 088d6162 — "MIRA/Claudius"
- [CANONICAL] 29ba2463 — "Miralaudius"
- [keep] c327f3c5 — "Claudius"
- [MERGE ->] 1486feb2 — "Miralaudius"

---

## Group 8 of 10 (6 entities)

### Input Entities
- **da3725bd** — "Claude/Mira" (ORG, 1 links)
- **f3d8d797** — "Claude/MIRA" (ORG, 2 links)
- **088d6162** — "MIRA/Claudius" (ORG, 1 links)
- **29ba2463** — "Miralaudius" (ORG, 8 links)
- **c327f3c5** — "Claudius" (PERSON, 3 links)
- **1486feb2** — "Miralaudius" (PERSON, 2 links)

### LLM Decisions
- [MERGE ->] db5e6c9b — "Claude Code"
- [CANONICAL] 1e61511a — "Claude"
- [MERGE ->] dd6bd4b3 — "Claude"
- [DELETE] db6fc1a6 — "Claude Code"
- [MERGE ->] 46f97484 — "claude"
- [MERGE ->] 8c762174 — "Claude API"

---

## Group 9 of 10 (6 entities)

### Input Entities
- **db5e6c9b** — "Claude Code" (PERSON, 3 links)
- **1e61511a** — "Claude" (PERSON, 18 links)
- **dd6bd4b3** — "Claude" (PRODUCT, 1 links)
- **db6fc1a6** — "Claude Code" (LAW, 2 links)
- **46f97484** — "claude" (PERSON, 6 links)
- **8c762174** — "Claude API" (PERSON, 1 links)

### LLM Decisions
- [DELETE] 697b097d — "Recognizes"
- [keep] 698cd2dc — "Recognizes"
- [DELETE] 09830fac — "Recognizes"
- [DELETE] 52e2959b — "Recognizes emoji"
- [keep] eca9c579 — "Recognizes MIRA"
- [keep] 1af92120 — "Recognizes Letta"

---

## Group 10 of 10 (6 entities)

### Input Entities
- **697b097d** — "Recognizes" (ORG, 1 links)
- **698cd2dc** — "Recognizes" (PERSON, 8 links)
- **09830fac** — "Recognizes" (NORP, 3 links)
- **52e2959b** — "Recognizes emoji" (PERSON, 1 links)
- **eca9c579** — "Recognizes MIRA" (PERSON, 4 links)
- **1af92120** — "Recognizes Letta" (ORG, 1 links)

*No LLM decision (group excluded by validation)*

---

## System Prompt

```xml
<gc_task>
  <system_directive>
    Review groups of similar entity names from a knowledge graph.
    Output only the specified XML format.
    CRITICAL: Your response must begin with "<gc_decisions>" — no preamble.
  </system_directive>

  <task name="entity_review">
    <description>For each entity in each group, assign exactly one action.</description>

    <actions>
      <action name="canonical">This entity is the merge target (best name, most links). At most one per group. Requires at least one "merge" sibling.</action>
      <action name="merge">Merge this entity into the canonical entity. Same real-world thing — spelling variation, abbreviation, case difference.</action>
      <action name="keep">This entity is distinct despite a similar name. Leave unchanged.</action>
      <action name="delete">This entity is noise, a typo, or an extraction error. Archive it.</action>
    </actions>

    <rules>
      <rule>Default to "keep" when uncertain — false merges lose data, false keeps are harmless</rule>
      <rule>Merge: "PostgreSQL"/"Postgres", "JS"/"JavaScript", "GPT-4"/"GPT4"</rule>
      <rule>Keep: similar names but genuinely different referents</rule>
      <rule>Delete: meaningless fragments, obvious NER errors</rule>
      <rule>When merging, prefer the most complete/formal name as canonical</rule>
      <rule>When merging, prefer the entity with more links as canonical</rule>
      <rule>CRITICAL: Use entity IDs exactly as provided. Do not invent IDs.</rule>
    </rules>
  </task>

  <output_format>
    <instruction>Respond with this exact XML structure.</instruction>
    <example_output><![CDATA[
<gc_decisions>
<group id="1">
<entity id="abc12345" action="canonical"/>
<entity id="def67890" action="merge"/>
</group>
<group id="2">
<entity id="ghi11111" action="keep"/>
<entity id="jkl22222" action="delete"/>
</group>
</gc_decisions>
]]></example_output>
  </output_format>
</gc_task>

```

## User Prompt

```xml
<entity_groups>
<group id="1">
  <entity id="b2c4500b" name="Opus 4.5" type="ORG" links="5"/>
  <entity id="cab9ed3b" name="Opus 4.5" type="LAW" links="6"/>
  <entity id="a5f7f30b" name="Opus 4.5's" type="GPE" links="5"/>
  <entity id="af0163b6" name="Opus 5" type="WORK_OF_ART" links="1"/>
  <entity id="c76b7d04" name="Opus 4.0" type="ORG" links="5"/>
  <entity id="229ae67b" name="Opus 4.5" type="FAC" links="3"/>
  <entity id="6789d4fb" name="Opus 4.5" type="WORK_OF_ART" links="4"/>
  <entity id="0db4d552" name="Opus 4.0" type="WORK_OF_ART" links="1"/>
  <entity id="7ebdf5ec" name="Opus" type="ORG" links="7"/>
  <entity id="263968c6" name="Opus" type="PERSON" links="1"/>
  <entity id="44711238" name="Opus 3.0" type="WORK_OF_ART" links="1"/>
</group>
<group id="2">
  <entity id="1d7374b2" name="Owens Cross" type="ORG" links="1"/>
  <entity id="9c71513f" name="Owens Cross Roads," type="ORG" links="1"/>
  <entity id="9e916933" name="Owens Cross" type="FAC" links="1"/>
  <entity id="b9591537" name="Owens Cross Roads" type="FAC" links="50"/>
  <entity id="68934703" name="Owens Cross Roads" type="ORG" links="58"/>
  <entity id="47a6ee36" name="Owens Cross Roads:" type="ORG" links="1"/>
  <entity id="d442a536" name="Owens Cross Roads/" type="FAC" links="1"/>
  <entity id="584208bb" name="Owens Cross Roads/Hampton Cove" type="ORG" links="1"/>
  <entity id="cd4588a8" name="Huntsville/Owens Cross Roads" type="ORG" links="1"/>
  <entity id="95c3bad2" name="Owens Cross Roads, AL" type="ORG" links="1"/>
</group>
<group id="3">
  <entity id="5bd43276" name="MIRA" type="ORG" links="65"/>
  <entity id="51abd7c8" name="'mira'" type="PERSON" links="1"/>
  <entity id="802a27ae" name="MIRA VM" type="ORG" links="1"/>
  <entity id="81d39593" name="MIRA AI" type="ORG" links="1"/>
  <entity id="b0760294" name="MIRA" type="PERSON" links="4"/>
  <entity id="ad298feb" name="Mira" type="ORG" links="2"/>
  <entity id="f94d12cf" name="Mira AI" type="ORG" links="1"/>
  <entity id="4928719b" name="Mira" type="PERSON" links="5"/>
  <entity id="be8a092b" name="Mira" type="GPE" links="27"/>
</group>
<group id="4">
  <entity id="232a7653" name="Greenbrier Valley" type="GPE" links="21"/>
  <entity id="4da94d71" name="Greenbrier Valley's" type="GPE" links="4"/>
  <entity id="b33b146c" name="Greenbrier valley's" type="GPE" links="2"/>
  <entity id="8a7dd376" name="Greenbrier" type="GPE" links="46"/>
  <entity id="95c8862a" name="Greenbrier valley" type="GPE" links="12"/>
  <entity id="cd21264d" name="Greenbrier River" type="GPE" links="2"/>
  <entity id="928166a8" name="Greenbrier Trail" type="FAC" links="1"/>
  <entity id="33283ebc" name="the Greenbrier River Trail" type="FAC" links="13"/>
  <entity id="e6af9779" name="Greenbrier River Trail" type="FAC" links="12"/>
</group>
<group id="5">
  <entity id="44db1fd6" name="Claude-Opus-4-20250514" type="PERSON" links="1"/>
  <entity id="f8ffcbf9" name="Claude Opus-4-20250514" type="PERSON" links="1"/>
  <entity id="edb5260e" name="Claude Opus 4" type="PERSON" links="4"/>
  <entity id="1b1acd58" name="Claude Opus 4.5" type="PERSON" links="15"/>
  <entity id="ad105817" name="Claude Opus 4.5" type="ORG" links="1"/>
  <entity id="666b3674" name="Claude Opus" type="PERSON" links="8"/>
  <entity id="b189f1cd" name="Claude Opus 4.5" type="PRODUCT" links="2"/>
</group>
<group id="6">
  <entity id="1c16df7e" name="Raspberry Pi" type="WORK_OF_ART" links="2"/>
  <entity id="79e79fd5" name="Raspberry Pi" type="ORG" links="11"/>
  <entity id="9df7cbbb" name="Raspberry Pi 5" type="PRODUCT" links="1"/>
  <entity id="470a5056" name="Raspberry Pi" type="PERSON" links="5"/>
  <entity id="96857ea9" name="a Raspberry Pi" type="ORG" links="3"/>
  <entity id="d23627cb" name="Raspberry Pi microSD" type="PRODUCT" links="1"/>
  <entity id="6a6e35c1" name="Raspberry Pi SD" type="ORG" links="9"/>
</group>
<group id="7">
  <entity id="b6eaded5" name="Claude Sonnet" type="PRODUCT" links="1"/>
  <entity id="cbc9210e" name="Claude Sonnet" type="PERSON" links="5"/>
  <entity id="6fd4cdc3" name="Claude Sonnet 3.5" type="PERSON" links="1"/>
  <entity id="ead412d4" name="Claude Sonnet 4.5" type="PERSON" links="1"/>
  <entity id="36467beb" name="Refining Claude Sonnet" type="PERSON" links="1"/>
  <entity id="6cdeb5dc" name="Refining Claude Sonnet 3.5" type="PERSON" links="1"/>
  <entity id="a006f062" name="Refining Claude" type="PERSON" links="2"/>
</group>
<group id="8">
  <entity id="da3725bd" name="Claude/Mira" type="ORG" links="1"/>
  <entity id="f3d8d797" name="Claude/MIRA" type="ORG" links="2"/>
  <entity id="088d6162" name="MIRA/Claudius" type="ORG" links="1"/>
  <entity id="29ba2463" name="Miralaudius" type="ORG" links="8"/>
  <entity id="c327f3c5" name="Claudius" type="PERSON" links="3"/>
  <entity id="1486feb2" name="Miralaudius" type="PERSON" links="2"/>
</group>
<group id="9">
  <entity id="db5e6c9b" name="Claude Code" type="PERSON" links="3"/>
  <entity id="1e61511a" name="Claude" type="PERSON" links="18"/>
  <entity id="dd6bd4b3" name="Claude" type="PRODUCT" links="1"/>
  <entity id="db6fc1a6" name="Claude Code" type="LAW" links="2"/>
  <entity id="46f97484" name="claude" type="PERSON" links="6"/>
  <entity id="8c762174" name="Claude API" type="PERSON" links="1"/>
</group>
<group id="10">
  <entity id="697b097d" name="Recognizes" type="ORG" links="1"/>
  <entity id="698cd2dc" name="Recognizes" type="PERSON" links="8"/>
  <entity id="09830fac" name="Recognizes" type="NORP" links="3"/>
  <entity id="52e2959b" name="Recognizes emoji" type="PERSON" links="1"/>
  <entity id="eca9c579" name="Recognizes MIRA" type="PERSON" links="4"/>
  <entity id="1af92120" name="Recognizes Letta" type="ORG" links="1"/>
</group>
</entity_groups>

```

## Raw Response

```xml
```xml
<gc_decisions>
<group id="1">
<entity id="b2c4500b" action="merge"/>
<entity id="cab9ed3b" action="canonical"/>
<entity id="a5f7f30b" action="merge"/>
<entity id="af0163b6" action="keep"/>
<entity id="c76b7d04" action="keep"/>
<entity id="229ae67b" action="merge"/>
<entity id="6789d4fb" action="merge"/>
<entity id="0db4d552" action="keep"/>
<entity id="7ebdf5ec" action="keep"/>
<entity id="263968c6" action="keep"/>
<entity id="44711238" action="keep"/>
</group>
<group id="2">
<entity id="1d7374b2" action="merge"/>
<entity id="9c71513f" action="merge"/>
<entity id="9e916933" action="merge"/>
<entity id="b9591537" action="merge"/>
<entity id="68934703" action="canonical"/>
<entity id="47a6ee36" action="merge"/>
<entity id="d442a536" action="merge"/>
<entity id="584208bb" action="delete"/>
<entity id="cd4588a8" action="delete"/>
<entity id="95c3bad2" action="merge"/>
</group>
<group id="3">
<entity id="5bd43276" action="canonical"/>
<entity id="51abd7c8" action="merge"/>
<entity id="802a27ae" action="merge"/>
<entity id="81d39593" action="merge"/>
<entity id="b0760294" action="keep"/>
<entity id="ad298feb" action="merge"/>
<entity id="f94d12cf" action="merge"/>
<entity id="4928719b" action="keep"/>
<entity id="be8a092b" action="keep"/>
</group>
<group id="4">
<entity id="232a7653" action="canonical"/>
<entity id="4da94d71" action="merge"/>
<entity id="b33b146c" action="merge"/>
<entity id="8a7dd376" action="keep"/>
<entity id="95c8862a" action="merge"/>
<entity id="cd21264d" action="keep"/>
<entity id="928166a8" action="merge"/>
<entity id="33283ebc" action="canonical"/>
<entity id="e6af9779" action="merge"/>
</group>
<group id="5">
<entity id="44db1fd6" action="merge"/>
<entity id="f8ffcbf9" action="merge"/>
<entity id="edb5260e" action="merge"/>
<entity id="1b1acd58" action="canonical"/>
<entity id="ad105817" action="merge"/>
<entity id="666b3674" action="merge"/>
<entity id="b189f1cd" action="merge"/>
</group>
<group id="6">
<entity id="1c16df7e" action="merg
... [truncated]
```
