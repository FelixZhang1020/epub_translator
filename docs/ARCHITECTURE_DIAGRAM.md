# Architecture Comparison: Before vs After

## BEFORE: Current Chaotic Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    API ROUTES                                            │
│  /analysis          /translation         /optimization        /proofreading             │
└───────┬─────────────────┬─────────────────────┬─────────────────────┬───────────────────┘
        │                 │                     │                     │
        ▼                 ▼                     ▼                     ▼
┌───────────────┐  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│ LLMConfig     │  │ LLMConfig   │       │ LLMConfig   │       │ LLMConfig   │
│ Service       │  │ Service     │       │ Service     │       │ Service     │
│ ┌───────────┐ │  │ ┌─────────┐ │       │ ┌─────────┐ │       │ ┌─────────┐ │
│ │temp: 0.7  │ │  │ │temp: 0.7│ │       │ │temp: 0.7│ │       │ │temp: 0.7│ │
│ │(from DB)  │ │  │ │(from DB)│ │       │ │(from DB)│ │       │ │(from DB)│ │
│ └─────┬─────┘ │  │ └────┬────┘ │       │ └────┬────┘ │       │ └────┬────┘ │
└───────┼───────┘  └──────┼──────┘       └──────┼──────┘       └──────┼──────┘
        │                 │                     │                     │
        │ IGNORED!        │ IGNORED!            │ IGNORED!            │ IGNORED!
        ▼                 ▼                     ▼                     ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                           VARIABLE BUILDING (3 DIFFERENT SYSTEMS!)                        │
│                                                                                           │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐           │
│  │   VariableService   │    │   ContextBuilder    │    │  Strategy-Specific  │           │
│  │   (variables.py)    │    │ (context_builder.py)│    │    (direct.py)      │           │
│  ├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤           │
│  │ • DERIVED_MAPPINGS  │    │ • Different extract │    │ • Minimal vars      │           │
│  │ • 30+ derived vars  │    │ • BookAnalysisCtx   │    │ • No derived.*      │           │
│  │ • Boolean flags     │    │ • No boolean flags  │    │ • No context.*      │           │
│  │ • Nested structure  │    │ • Nested structure  │    │ • Flat structure    │           │
│  └──────────┬──────────┘    └──────────┬──────────┘    └──────────┬──────────┘           │
│             │                          │                          │                       │
│             │ Used by                  │ Used by                  │ Used by               │
│             │ Analysis                 │ Translation              │ Strategies            │
│             │ (partial)                │                          │ (fallback)            │
│             ▼                          ▼                          ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                    INCONSISTENT VARIABLE AVAILABILITY                               │ │
│  │                                                                                     │ │
│  │   Analysis:     project.* ✓   derived.* ✗ (partial)   context.* ✗                  │ │
│  │   Translation:  project.* ✓   derived.* ✓ (different) context.* ✓                  │ │
│  │   Strategy:     project.* ✗   derived.* ✗             context.* ✗                  │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                              PROMPT RENDERING                                             │
│                                                                                           │
│   Template: {{#if derived.has_analysis}}                                                  │
│               {{derived.writing_style}}     ──────►  Often EMPTY or MISSING!              │
│             {{/if}}                                                                       │
│                                                                                           │
│   Why? Because derived.has_analysis is not set in many code paths!                       │
└───────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                                 LLM CALLS                                                 │
│                                                                                           │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐           │
│  │  Analysis Service   │    │  TranslationStrategy│    │   Other Services    │           │
│  ├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤           │
│  │ litellm.acompletion │    │ litellm.acompletion │    │ litellm.acompletion │           │
│  │ ┌─────────────────┐ │    │ ┌─────────────────┐ │    │ ┌─────────────────┐ │           │
│  │ │ temp: DEFAULT   │ │    │ │ temp: 0.3       │ │    │ │ temp: HARDCODED │ │           │
│  │ │ max_tokens: N/A │ │    │ │ max_tokens: 4096│ │    │ │ max_tokens: ???  │ │           │
│  │ │ (NOT from DB!)  │ │    │ │ (HARDCODED!)    │ │    │ │ (INCONSISTENT!) │ │           │
│  │ └─────────────────┘ │    │ └─────────────────┘ │    │ └─────────────────┘ │           │
│  └─────────────────────┘    └─────────────────────┘    └─────────────────────┘           │
└───────────────────────────────────────────────────────────────────────────────────────────┘


                    ╔═══════════════════════════════════════════╗
                    ║         PROBLEMS SUMMARY                  ║
                    ╠═══════════════════════════════════════════╣
                    ║ 1. DB temperature NEVER reaches LLM call  ║
                    ║ 2. 3 different variable building systems  ║
                    ║ 3. derived.* missing in some code paths   ║
                    ║ 4. max_tokens not even in database        ║
                    ║ 5. Each stage does its own thing          ║
                    ╚═══════════════════════════════════════════╝
```

---

## AFTER: Unified Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    API ROUTES                                            │
│  /analysis          /translation         /optimization        /proofreading             │
└───────┬─────────────────┬─────────────────────┬─────────────────────┬───────────────────┘
        │                 │                     │                     │
        │                 │                     │                     │
        ▼                 ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                          │
│                         ┌─────────────────────────────────────┐                         │
│                         │       LLMConfigResolver             │                         │
│                         │         (SINGLE ENTRY)              │                         │
│                         ├─────────────────────────────────────┤                         │
│                         │                                     │                         │
│                         │  Resolution Priority:               │                         │
│                         │  1. Request Override (debugging)    │                         │
│                         │  2. DB Config (by ID)               │                         │
│                         │  3. Active Config (is_active=true)  │                         │
│                         │  4. Default Config                  │                         │
│                         │  5. Environment Variables           │                         │
│                         │                                     │                         │
│                         │  Output: LLMRuntimeConfig           │                         │
│                         │  ┌─────────────────────────────┐    │                         │
│                         │  │ provider: "anthropic"       │    │                         │
│                         │  │ model: "claude-3-5-sonnet"  │    │                         │
│                         │  │ api_key: "sk-..."           │    │                         │
│                         │  │ temperature: 0.5  ◄─────────┼────┼── FROM DB!              │
│                         │  │ max_tokens: 4096  ◄─────────┼────┼── FROM DB!              │
│                         │  │ top_p: null                 │    │                         │
│                         │  └─────────────────────────────┘    │                         │
│                         └──────────────────┬──────────────────┘                         │
│                                            │                                             │
│                                            │ Flows through entire pipeline               │
│                                            ▼                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                          │
│                         ┌─────────────────────────────────────┐                         │
│                         │     UnifiedVariableBuilder          │                         │
│                         │        (SINGLE SOURCE)              │                         │
│                         ├─────────────────────────────────────┤                         │
│                         │                                     │                         │
│                         │  Input: VariableInput               │                         │
│                         │  ┌─────────────────────────────┐    │                         │
│                         │  │ project_id: "abc123"        │    │                         │
│                         │  │ stage: "translation"        │    │                         │
│                         │  │ source_text: "Hello..."     │    │                         │
│                         │  │ previous_source: "..."      │    │                         │
│                         │  │ previous_target: "..."      │    │                         │
│                         │  └─────────────────────────────┘    │                         │
│                         │                                     │                         │
│                         │  Sources (in order):                │                         │
│                         │  ┌─────────────────────────────┐    │                         │
│                         │  │ 1. Project DB    → project.*│    │                         │
│                         │  │ 2. Input Data    → content.*│    │                         │
│                         │  │ 3. Input Data    → context.*│    │                         │
│                         │  │ 4. Analysis DB   → derived.*│◄───┼── SINGLE EXTRACTION!    │
│                         │  │ 5. Computed      → meta.*   │    │                         │
│                         │  │ 6. Input Data    → pipeline*│    │                         │
│                         │  │ 7. variables.json→ user.*   │    │                         │
│                         │  └─────────────────────────────┘    │                         │
│                         │                                     │                         │
│                         │  Output: Flat Dict[str, Any]        │                         │
│                         │  ┌─────────────────────────────┐    │                         │
│                         │  │ "project.title": "Book"     │    │                         │
│                         │  │ "project.author": "Author"  │    │                         │
│                         │  │ "content.source": "Hello"   │    │                         │
│                         │  │ "derived.has_analysis": True│◄───┼── ALWAYS SET!           │
│                         │  │ "derived.writing_style": "."│◄───┼── ALWAYS SET!           │
│                         │  │ "derived.tone": "formal"    │    │                         │
│                         │  │ "derived.has_terminology": T│    │                         │
│                         │  │ "context.previous_source"..."    │                         │
│                         │  │ "meta.word_count": 150      │    │                         │
│                         │  └─────────────────────────────┘    │                         │
│                         └──────────────────┬──────────────────┘                         │
│                                            │                                             │
│                                            │ Consistent for ALL stages                   │
│                                            ▼                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                          │
│                         ┌─────────────────────────────────────┐                         │
│                         │         PromptLoader                │                         │
│                         │     (UNCHANGED - already good)      │                         │
│                         ├─────────────────────────────────────┤                         │
│                         │                                     │                         │
│                         │  1. Load template for project/stage │                         │
│                         │  2. Render with variables           │                         │
│                         │                                     │                         │
│                         │  Template:                          │                         │
│                         │  {{#if derived.has_analysis}}       │                         │
│                         │    {{derived.writing_style}}        │──► NOW WORKS!           │
│                         │  {{/if}}                            │                         │
│                         │                                     │                         │
│                         └──────────────────┬──────────────────┘                         │
│                                            │                                             │
│                                            ▼                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                          │
│                         ┌─────────────────────────────────────┐                         │
│                         │          LLMGateway                 │                         │
│                         │        (SINGLE ENTRY)               │                         │
│                         ├─────────────────────────────────────┤                         │
│                         │                                     │                         │
│                         │  Input:                             │                         │
│                         │  • system_prompt (rendered)         │                         │
│                         │  • user_prompt (rendered)           │                         │
│                         │  • config: LLMRuntimeConfig         │                         │
│                         │                                     │                         │
│                         │  LLM Call:                          │                         │
│                         │  ┌─────────────────────────────┐    │                         │
│                         │  │ litellm.acompletion(        │    │                         │
│                         │  │   model=config.model,       │    │                         │
│                         │  │   temperature=config.temp,  │◄───┼── FROM CONFIG!          │
│                         │  │   max_tokens=config.max,    │◄───┼── FROM CONFIG!          │
│                         │  │   messages=[...],           │    │                         │
│                         │  │ )                           │    │                         │
│                         │  └─────────────────────────────┘    │                         │
│                         │                                     │                         │
│                         └─────────────────────────────────────┘                         │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘


                    ╔═══════════════════════════════════════════╗
                    ║           BENEFITS                        ║
                    ╠═══════════════════════════════════════════╣
                    ║ 1. DB config flows to actual LLM call     ║
                    ║ 2. Single variable builder for all stages ║
                    ║ 3. derived.* ALWAYS populated correctly   ║
                    ║ 4. max_tokens configurable in DB          ║
                    ║ 5. Consistent behavior across all stages  ║
                    ║ 6. Easy to test and debug                 ║
                    ╚═══════════════════════════════════════════╝
```

---

## Data Flow Comparison

### BEFORE: Fragmented Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Database   │     │   Service    │     │   Strategy   │     │   LiteLLM    │
│              │     │              │     │              │     │              │
│ temp: 0.7    │────►│ temp: 0.7    │──X──│ temp: 0.3    │────►│ temp: 0.3    │
│ (stored)     │     │ (resolved)   │     │ (HARDCODED!) │     │ (used)       │
│              │     │              │     │              │     │              │
│ max_tokens:  │     │ max_tokens:  │     │ max_tokens:  │     │ max_tokens:  │
│ (NOT STORED) │     │ (N/A)        │     │ 4096 (HARD)  │     │ 4096         │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘

                              ▲
                              │
                        BROKEN HERE!
                     Config is ignored,
                     hardcoded values used
```

### AFTER: Unified Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Database   │     │ ConfigResolver│    │  LLMGateway  │     │   LiteLLM    │
│              │     │              │     │              │     │              │
│ temp: 0.7    │────►│ temp: 0.7    │────►│ temp: 0.7    │────►│ temp: 0.7    │
│ (stored)     │     │ (resolved)   │     │ (passed)     │     │ (used!)      │
│              │     │              │     │              │     │              │
│ max_tokens:  │────►│ max_tokens:  │────►│ max_tokens:  │────►│ max_tokens:  │
│ 4096 (stored)│     │ 4096         │     │ 4096         │     │ 4096         │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘

                              │
                              │
                     UNBROKEN CHAIN!
                  Config flows through
                     entire pipeline
```

---

## Variable Availability Comparison

### BEFORE: Inconsistent

```
                    ┌─────────────┬─────────────┬─────────────┬─────────────┐
                    │  Analysis   │ Translation │Optimization │ Proofreading│
┌───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ project.title     │     ✓       │     ✓       │     ✓       │     ?       │
│ project.author    │     ✓       │     ✓       │     ✓       │     ?       │
├───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ content.source    │     ✗       │     ✓       │     ✓       │     ?       │
│ content.target    │     ✗       │     ✗       │     ✓       │     ?       │
├───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ derived.has_analysis   │  ✗    │  ✓ (diff)   │  ✓ (diff)   │     ✗       │
│ derived.writing_style  │  ✗    │  ✓ (diff)   │  ✓ (diff)   │     ✗       │
│ derived.terminology    │  ✗    │  ✓ (diff)   │  ✓ (diff)   │     ✗       │
├───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ context.previous  │     ✗       │     ✓       │     ✗       │     ✗       │
│ context.next      │     ✗       │     ?       │     ✗       │     ✗       │
├───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ meta.word_count   │     ✗       │     ✓       │     ✓       │     ✗       │
│ meta.stage        │     ✗       │     ✗       │     ✗       │     ✗       │
└───────────────────┴─────────────┴─────────────┴─────────────┴─────────────┘

Legend: ✓ = Available   ✗ = Missing   ? = Unknown/Inconsistent
        (diff) = Different extraction logic, may produce different values
```

### AFTER: Consistent

```
                    ┌─────────────┬─────────────┬─────────────┬─────────────┐
                    │  Analysis   │ Translation │Optimization │ Proofreading│
┌───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ project.title     │     ✓       │     ✓       │     ✓       │     ✓       │
│ project.author    │     ✓       │     ✓       │     ✓       │     ✓       │
├───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ content.source    │  (samples)  │     ✓       │     ✓       │     ✓       │
│ content.target    │     ✗       │     ✗       │     ✓       │     ✓       │
├───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ derived.has_analysis   │  ✗*   │     ✓       │     ✓       │     ✓       │
│ derived.writing_style  │  ✗*   │     ✓       │     ✓       │     ✓       │
│ derived.terminology    │  ✗*   │     ✓       │     ✓       │     ✓       │
├───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ context.previous  │     ✗       │     ✓       │     ✓       │     ✓       │
│ context.next      │     ✗       │     ✓       │     ✓       │     ✓       │
├───────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ meta.word_count   │     ✓       │     ✓       │     ✓       │     ✓       │
│ meta.stage        │     ✓       │     ✓       │     ✓       │     ✓       │
└───────────────────┴─────────────┴─────────────┴─────────────┴─────────────┘

Legend: ✓ = Available (SAME extraction logic everywhere)
        ✗ = Not applicable for this stage (by design)
        ✗* = Analysis stage runs BEFORE analysis exists
```

---

## Code Path Comparison

### BEFORE: Multiple Paths

```
                                 ┌─────────────────────┐
                                 │    API Request      │
                                 └──────────┬──────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
          ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
          │  Path A:        │    │  Path B:        │    │  Path C:        │
          │  VariableService│    │  ContextBuilder │    │  Strategy       │
          │  .build_context │    │  ._build_vars   │    │  .get_vars      │
          └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
                   │                      │                      │
                   ▼                      ▼                      ▼
          ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
          │ DERIVED_MAPPINGS│    │ BookAnalysisCtx │    │ Minimal vars    │
          │ + bool flags    │    │ .from_raw()     │    │ No derived.*    │
          │ + transforms    │    │ (different!)    │    │                 │
          └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
                   │                      │                      │
                   └──────────────────────┼──────────────────────┘
                                          │
                                          ▼
                              ┌─────────────────────┐
                              │  INCONSISTENT       │
                              │  VARIABLES!         │
                              └─────────────────────┘
```

### AFTER: Single Path

```
                                 ┌─────────────────────┐
                                 │    API Request      │
                                 └──────────┬──────────┘
                                            │
                                            │
                                            ▼
                              ┌─────────────────────────┐
                              │  UnifiedVariableBuilder │
                              │  .build()               │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │  Single extraction      │
                              │  Single schema          │
                              │  Single output format   │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │  CONSISTENT             │
                              │  VARIABLES!             │
                              └─────────────────────────┘
```

---

## Summary

| Aspect | BEFORE | AFTER |
|--------|--------|-------|
| Variable Builders | 3 different | 1 unified |
| Derived Extraction | 2 implementations | 1 implementation |
| Temperature Source | Hardcoded in strategy | From DB config |
| max_tokens Source | Hardcoded (not in DB) | From DB config |
| Code Paths | Multiple, divergent | Single, consistent |
| Template Variables | Often missing | Always populated |
| Testability | Hard (multiple paths) | Easy (single path) |
| Debugging | Complex (which path?) | Simple (one path) |
