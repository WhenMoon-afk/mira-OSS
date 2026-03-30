# arrows — Rare Unicode marker ablation

## Hypothesis
The rare Unicode characters used as section markers (║⊕║, ║⊗║, ║⊙║, ║⊛║, ┃◆┃, ═══) may be acting as attention sinks — the model fixates on the unusual tokens themselves rather than having attention flow through to the instructions within the block. BPE tokenizes these characters into multiple rare subword tokens, each potentially absorbing disproportionate attention.

## Changes
Replaced all rare Unicode markers with ASCII arrow markers (`>>>>> HEADER <<<<<<` / `>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>`) which tokenize into common, high-frequency tokens that shouldn't attract attention on their own.

### System prompt
- `║⊕║ BEGIN/END ENTITY RULES ║⊕║` → `>>>>> BEGIN/END ENTITY RULES <<<<<<`
- `║⊗║ BEGIN/END PASSAGE RULES ║⊗║` → `>>>>> BEGIN/END PASSAGE RULES <<<<<<`
- `║⊙║ BEGIN/END EXPANSION RULES ║⊙║` → `>>>>> BEGIN/END EXPANSION RULES <<<<<<`
- `║⊛║ BEGIN/END COMPLEXITY RULES ║⊛║` → `>>>>> BEGIN/END COMPLEXITY RULES <<<<<<`
- Trailing `═══` → `>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>`

### User prompt
- All `═══` separators → `>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>`
- `┃◆┃ BEGIN/END CONTENT OF CURRENT TURN ┃◆┃` → `>>>>> BEGIN/END CONTENT OF CURRENT TURN <<<<<<`

## What to measure
Compare per-token attention at marker positions between baseline and this variant. If rare chars are attention sinks, we expect:
1. Lower per-token attention at marker positions in this variant (arrows don't attract fixation)
2. Higher attention on the actual rule content within marked blocks (attention redistributed to instructions)
3. Similar or improved task-level metrics (context bleed, rule attention %)
