# strengthen Variant Rationale

## Strategy
Restructure entity extraction rules and complexity bias rule in the system prompt for higher attention capture at their respective generation positions. User template unchanged. Code constants unchanged.

## What Changes in the System Prompt

### Entity Extraction (Task 1): Consolidated Constraint Block

**Before:** 4 separate `<rule>` elements inside `<rules>`:
```xml
<rules>
  <rule>Extract ONLY atomic proper nouns that a spaCy model would recognize.</rule>
  <rule>Include specific technical identifiers (e.g. "OAuth", "MIRA") as PRODUCT.</rule>
  <rule>STRICTLY EXCLUDE generic noun phrases (e.g., "build pipeline", "testing") that are not named entities.</rule>
  <rule>When no clear entities are present output "None" in this section.</rule>
</rules>
```

**After:** Single `<entity_constraint>` block with a procedural test:
```xml
<entity_constraint>
  You MUST apply this test to every candidate entity before including it:
  Would a spaCy NER model tag this exact string as PERSON, ORG, PRODUCT, EVENT, or GPE?
  If NO — do not extract it. "Build pipeline", "testing", "Father", "subcortical", "PATCHNOTE" are NOT entities.
  Only extract proper nouns: specific names of people, companies, software, places, or events.
  When no entities pass this test, output "None".
</entity_constraint>
```

**Structural changes:**
1. **Collapsed 4 rules into 1 block.** The original 4 `<rule>` elements competed for attention — each was a small token span within a `<rules>` container, fragmenting attention across multiple small targets. A single consolidated block creates one larger attention target. The inclusion and exclusion constraints are now co-located in the same contiguous token span, so attention to one necessarily attends to the other.

2. **Added concrete false-positive examples.** "Father", "subcortical", "PATCHNOTE" are real false positives observed in production. Concrete negative examples at the entity generation position create stronger exclusion signals than abstract rules like "STRICTLY EXCLUDE generic noun phrases." The model can pattern-match against specific negative examples more effectively than interpreting a meta-rule.

3. **Procedural framing ("apply this test").** Instead of passive rules ("Extract ONLY..."), the constraint is framed as an active procedure the model must execute. This creates a stronger causal link between the rule and the entity generation — the model is told to "apply this test to every candidate" rather than passively observing a list of rules.

4. **Removed the `<rules>` wrapper tag.** The `<rules>` tag added structural depth (another XML nesting level) without adding information. Removing it reduces the number of attention-competing structural tokens.

### Complexity Assessment (Task 4): Promoted Bias Directive

**Before:** The bias rule was the middle `<rule>` inside `<rules>`:
```xml
<rules>
  <rule>Evaluate based on cognitive effort required to respond well, not message length</rule>
  <rule>When uncertain, prefer "complex" to ensure adequate thinking depth</rule>
  <rule>Output exactly one of: straightforward OR complex</rule>
</rules>
```

**After:** The bias directive is promoted to its own structurally-isolated element:
```xml
<complexity_default>Default to "complex" when the classification is ambiguous. Err on the side of deeper analysis.</complexity_default>

<rules>
  <rule>Evaluate based on cognitive effort required to respond well, not message length</rule>
  <rule>Output exactly one of: straightforward OR complex</rule>
</rules>
```

**Structural changes:**
1. **Structural isolation.** The bias directive was buried as one `<rule>` among three inside `<rules>`. Its attention at the complexity generation position was 0.19% — below the uniform baseline of 0.57%. By extracting it into its own `<complexity_default>` element at the same nesting level as `<criteria>` and `<rules>`, it becomes a first-class structural element rather than a nested child.

2. **Distinct tag name.** `<complexity_default>` is a novel tag that won't appear in Qwen3-32B's pretraining data. Novel tags have higher information content (lower predictability), which forces attention allocation.

3. **Shortened phrasing.** "Default to complex when ambiguous" is more direct than "When uncertain, prefer complex to ensure adequate thinking depth." Fewer tokens means higher per-token density for the same semantic content.

## MI Metrics Targeted

### Entity Rules: 3.5% -> target above 5%
The current 3.5% attention at entity generation positions means the model extracts entities from in-context patterns rather than following rules. Consolidating 4 fragmented rules into 1 contiguous block should increase the attention mass allocated to the entity constraint, and concrete negative examples should create stronger exclusion activations.

### Complexity Bias: 0.19% -> target above uniform (0.57%)
Currently below-uniform attention, making it genuinely decorative. Structural isolation and promotion from a nested `<rule>` to a first-class `<complexity_default>` element should bring it above the uniform baseline.

## Mechanistic Hypothesis
- **Entity constraint consolidation**: Replacing 4 fragmented `<rule>` spans with 1 contiguous `<entity_constraint>` block should concentrate attention that was previously split across 4 small targets. The concrete false-positive examples create stronger inhibition signals at entity generation positions because the model can directly match "Father" against candidates rather than interpreting "STRICTLY EXCLUDE generic noun phrases."
- **Complexity promotion**: Moving the bias directive from a nested `<rule>` to a first-class `<complexity_default>` element gives it its own XML boundary tokens, which are structural attention anchors. The novel tag name adds information content (unpredictability) that forces attention allocation.

## Expected Tradeoffs
- **Positive**: Stronger entity filtering should reduce false positives. Complexity bias should actually influence decisions.
- **Negative**: The consolidated entity constraint is more opinionated — it names specific false positives. If the model over-generalizes from those examples (e.g., never extracting any capitalized words), entity recall could decrease.
- **Risk level**: LOW-MEDIUM for entity changes, LOW for complexity changes. The entity consolidation is the riskier change because it replaces 4 orthogonal rules with 1 unified constraint that might be interpreted more narrowly.
- **Net token count**: Slightly fewer tokens overall (removed `<rules>` wrapper, consolidated verbose phrasings). Effect on token mass ratio: negligible since these are system prompt changes, not user message changes.