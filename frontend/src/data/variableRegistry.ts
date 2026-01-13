/**
 * Variable Registry - defines all available template variables
 *
 * This is the source of truth for what variables can be used in prompt templates.
 * Variables are organized by category (namespace) and include metadata about
 * their source, availability, and usage.
 *
 * New in v2:
 * - Canonical variable names (content.source, content.target)
 * - Legacy aliases for backward compatibility
 * - Context namespace for surrounding paragraphs
 * - Meta namespace for runtime computed values
 * - Macros for reusable template fragments
 * - Fallback syntax: {{var | default:"value"}}
 * - Type formatting: {{var:list}}, {{var:table}}, {{var:terminology}}
 * - Conditional combinations: {{#if var1 && var2}}, {{#if var1 || var2}}
 */

export type VariableCategory = 'project' | 'content' | 'context' | 'pipeline' | 'derived' | 'meta' | 'user'
export type PromptStage = 'analysis' | 'translation' | 'optimization' | 'proofreading'
export type VariableType = 'string' | 'number' | 'boolean' | 'array' | 'object' | 'markdown' | 'table' | 'terminology'

export interface VariableDefinition {
  /** Variable name (without namespace prefix) */
  name: string
  /** Full variable reference for templates: {{namespace.name}} */
  fullName: string
  /** English description */
  description: string
  /** Data type */
  type: VariableType
  /** Where this variable comes from */
  source: string
  /** Which prompt stages can use this variable */
  stages: PromptStage[]
  /** Example value for documentation */
  example: string
  /** Whether this variable is required for the stage to work */
  required?: boolean
  /** For array/object types, describe the structure */
  structure?: string
  /** If this is a legacy alias, point to canonical name */
  canonicalName?: string
  /** Whether this is a legacy alias (deprecated but still works) */
  isLegacy?: boolean
}

export interface VariableCategoryInfo {
  /** Category ID */
  id: VariableCategory
  /** English label */
  label: string
  /** Description of this category */
  description: string
  /** Icon name (lucide) */
  icon: string
  /** Variables in this category */
  variables: VariableDefinition[]
}

/**
 * Template syntax reference
 */
export const TEMPLATE_SYNTAX = {
  // Basic variable substitution
  variable: '{{var}} or {{namespace.var}}',
  fallback: '{{var | default:"fallback value"}}',

  // Conditionals
  conditional: '{{#if var}}...{{/if}}',
  conditionalElse: '{{#if var}}...{{#else}}...{{/if}}',
  conditionalAnd: '{{#if var1 && var2}}...{{/if}}',
  conditionalAndElse: '{{#if var1 && var2}}...{{#else}}...{{/if}}',
  conditionalOr: '{{#if var1 || var2}}...{{/if}}',
  conditionalOrElse: '{{#if var1 || var2}}...{{#else}}...{{/if}}',
  unless: '{{#unless var}}...{{/unless}}',

  // Loops
  loop: '{{#each array}}{{this}}{{/each}}',
  loopWithIndex: '{{#each array}}{{@index}}: {{this}}{{/each}}',
  loopDict: '{{#each dict}}{{@key}}: {{this}}{{/each}}',

  // Macros and type formatting
  macro: '{{@macro_name}}',
  typeFormat: '{{var:type}} where type is list, table, terminology, json, inline',
}

/**
 * Complete variable registry organized by category
 */
export const VARIABLE_REGISTRY: VariableCategoryInfo[] = [
  {
    id: 'project',
    label: 'Project',
    description: 'Static metadata from the ePub project',
    icon: 'BookOpen',
    variables: [
      {
        name: 'title',
        fullName: 'project.title',
        description: 'Book title from ePub metadata',
        type: 'string',
        source: 'project.epub_title',
        stages: ['analysis', 'translation', 'optimization', 'proofreading'],
        example: 'Knowing God',
      },
      {
        name: 'author',
        fullName: 'project.author',
        description: 'Author name from ePub metadata',
        type: 'string',
        source: 'project.epub_author',
        stages: ['analysis', 'translation', 'optimization', 'proofreading'],
        example: 'J.I. Packer',
      },
      {
        name: 'author_background',
        fullName: 'project.author_background',
        description: 'Custom author background information provided by user',
        type: 'string',
        source: 'project.author_background',
        stages: ['translation'],
        example: 'J.I. Packer (1926-2020) was a British-born Canadian evangelical theologian...',
      },
      {
        name: 'source_language',
        fullName: 'project.source_language',
        description: 'Source language of the book',
        type: 'string',
        source: 'project.epub_language',
        stages: ['analysis', 'translation'],
        example: 'en',
      },
      {
        name: 'target_language',
        fullName: 'project.target_language',
        description: 'Target translation language',
        type: 'string',
        source: 'settings.target_language',
        stages: ['translation', 'optimization'],
        example: 'zh-CN',
      },
    ],
  },
  {
    id: 'content',
    label: 'Content',
    description: 'Current paragraph or text being processed',
    icon: 'FileText',
    variables: [
      // Canonical names (preferred)
      {
        name: 'source',
        fullName: 'content.source',
        description: 'Source text to be translated (canonical name)',
        type: 'string',
        source: 'paragraph.source_text',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'The grace of God is infinite and eternal.',
        required: true,
      },
      {
        name: 'target',
        fullName: 'content.target',
        description: 'Current translation (canonical name)',
        type: 'string',
        source: 'paragraph.target_text',
        stages: ['optimization', 'proofreading'],
        example: 'The grace of God is infinite and eternal. (translated)',
      },
      {
        name: 'chapter_title',
        fullName: 'content.chapter_title',
        description: 'Title of the current chapter',
        type: 'string',
        source: 'chapter.title',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'Chapter 1: Knowing and Being Known',
      },
      // Legacy aliases (deprecated but still work)
      {
        name: 'source_text',
        fullName: 'content.source_text',
        description: 'Source text (legacy alias for content.source)',
        type: 'string',
        source: 'paragraph.source_text',
        stages: ['translation', 'optimization'],
        example: 'The grace of God is infinite and eternal.',
        canonicalName: 'content.source',
        isLegacy: true,
      },
    ],
  },
  {
    id: 'context',
    label: 'Context',
    description: 'Surrounding paragraphs for translation continuity',
    icon: 'Layers',
    variables: [
      {
        name: 'previous_source',
        fullName: 'context.previous_source',
        description: 'Previous paragraph source text',
        type: 'string',
        source: 'context_window.before_source',
        stages: ['translation'],
        example: 'In the previous chapter, we discussed...',
      },
      {
        name: 'previous_target',
        fullName: 'context.previous_target',
        description: 'Previous paragraph translation',
        type: 'string',
        source: 'context_window.before_target',
        stages: ['translation'],
        example: 'In the previous chapter, we discussed... (translated)',
      },
    ],
  },
  {
    id: 'pipeline',
    label: 'Pipeline',
    description: 'Output from previous processing steps',
    icon: 'GitBranch',
    variables: [
      {
        name: 'reference_translation',
        fullName: 'pipeline.reference_translation',
        description: 'Reference translation from existing sources',
        type: 'string',
        source: 'reference_match.result',
        stages: ['translation'],
        example: 'The grace of God is boundless. (reference)',
      },
      {
        name: 'suggested_changes',
        fullName: 'pipeline.suggested_changes',
        description: 'User-confirmed suggestions for optimization',
        type: 'string',
        source: 'proofreading_step.suggestions',
        stages: ['optimization'],
        example: 'Change wording for better accuracy and flow.',
      },
    ],
  },
  {
    id: 'derived',
    label: 'Derived',
    description: 'Values extracted from analysis results',
    icon: 'Sparkles',
    variables: [
      {
        name: 'author_name',
        fullName: 'derived.author_name',
        description: 'Author name extracted from analysis',
        type: 'string',
        source: 'analysis_result.author_name',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'J.I. Packer',
      },
      {
        name: 'author_biography',
        fullName: 'derived.author_biography',
        description: 'Author biography extracted from analysis',
        type: 'string',
        source: 'analysis_result.author_biography',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'British-born Canadian evangelical theologian (1926-2020)',
      },
      {
        name: 'writing_style',
        fullName: 'derived.writing_style',
        description: 'Writing style extracted from analysis',
        type: 'string',
        source: 'analysis_result.writing_style',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'Academic theological prose with pastoral warmth',
      },
      {
        name: 'tone',
        fullName: 'derived.tone',
        description: 'Tone of the writing extracted from analysis',
        type: 'string',
        source: 'analysis_result.tone',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'Reverent, instructive, encouraging',
      },
      {
        name: 'target_audience',
        fullName: 'derived.target_audience',
        description: 'Target audience identified in analysis',
        type: 'string',
        source: 'analysis_result.target_audience',
        stages: ['translation'],
        example: 'Seminary students and lay theologians',
      },
      {
        name: 'genre_conventions',
        fullName: 'derived.genre_conventions',
        description: 'Genre conventions identified in analysis',
        type: 'string',
        source: 'analysis_result.genre_conventions',
        stages: ['translation'],
        example: 'Systematic theology with scriptural exposition',
      },
      {
        name: 'terminology_table',
        fullName: 'derived.terminology_table',
        description: 'Formatted terminology table from analysis',
        type: 'terminology',
        source: 'analysis_result.key_terminology (formatted)',
        stages: ['translation', 'optimization', 'proofreading'],
        example: '- grace: [translated term]\n- covenant: [translated term]\n- redemption: [translated term]',
      },
      {
        name: 'priority_order',
        fullName: 'derived.priority_order',
        description: 'Translation priority order from analysis',
        type: 'array',
        source: 'analysis_result.translation_principles.priority_order',
        stages: ['translation'],
        example: '["faithfulness", "expressiveness", "elegance"]',
        structure: 'string[]',
      },
      {
        name: 'faithfulness_boundary',
        fullName: 'derived.faithfulness_boundary',
        description: 'Content that must be translated literally',
        type: 'string',
        source: 'analysis_result.translation_principles.faithfulness_boundary',
        stages: ['translation'],
        example: 'Technical terms, Scripture quotes, data',
      },
      {
        name: 'permissible_adaptation',
        fullName: 'derived.permissible_adaptation',
        description: 'Areas where adaptation is allowed',
        type: 'string',
        source: 'analysis_result.translation_principles.permissible_adaptation',
        stages: ['translation'],
        example: 'Sentence restructuring, connector optimization',
      },
      {
        name: 'red_lines',
        fullName: 'derived.red_lines',
        description: 'Prohibited translation behaviors',
        type: 'string',
        source: 'analysis_result.translation_principles.red_lines',
        stages: ['translation'],
        example: 'Adding commentary, omitting content, changing stance',
      },
      {
        name: 'style_constraints',
        fullName: 'derived.style_constraints',
        description: 'Style and tone constraints from analysis',
        type: 'string',
        source: 'analysis_result.translation_principles.style_constraints',
        stages: ['translation'],
        example: 'Avoid colloquialisms, maintain formal register',
      },
      {
        name: 'custom_guidelines',
        fullName: 'derived.custom_guidelines',
        description: 'Custom translation guidelines from analysis',
        type: 'array',
        source: 'analysis_result.custom_guidelines',
        stages: ['translation'],
        example: '["Always capitalize references to God", "Use traditional terms for sacraments"]',
        structure: 'string[]',
      },
      // Boolean flags for conditional rendering
      {
        name: 'has_analysis',
        fullName: 'derived.has_analysis',
        description: 'Whether analysis exists for this project',
        type: 'boolean',
        source: 'computed',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'true',
      },
      {
        name: 'has_writing_style',
        fullName: 'derived.has_writing_style',
        description: 'Whether writing style is defined',
        type: 'boolean',
        source: 'computed',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'true',
      },
      {
        name: 'has_tone',
        fullName: 'derived.has_tone',
        description: 'Whether tone is defined',
        type: 'boolean',
        source: 'computed',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'true',
      },
      {
        name: 'has_terminology',
        fullName: 'derived.has_terminology',
        description: 'Whether terminology table exists',
        type: 'boolean',
        source: 'computed',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'true',
      },
      {
        name: 'has_target_audience',
        fullName: 'derived.has_target_audience',
        description: 'Whether target audience is defined',
        type: 'boolean',
        source: 'computed',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'true',
      },
      {
        name: 'has_genre_conventions',
        fullName: 'derived.has_genre_conventions',
        description: 'Whether genre conventions are defined',
        type: 'boolean',
        source: 'computed',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'true',
      },
      {
        name: 'has_translation_principles',
        fullName: 'derived.has_translation_principles',
        description: 'Whether translation principles are defined',
        type: 'boolean',
        source: 'computed',
        stages: ['translation'],
        example: 'true',
      },
      {
        name: 'has_custom_guidelines',
        fullName: 'derived.has_custom_guidelines',
        description: 'Whether custom guidelines exist',
        type: 'boolean',
        source: 'computed',
        stages: ['translation'],
        example: 'false',
      },
      {
        name: 'has_style_constraints',
        fullName: 'derived.has_style_constraints',
        description: 'Whether style constraints exist',
        type: 'boolean',
        source: 'computed',
        stages: ['translation'],
        example: 'false',
      },
    ],
  },
  {
    id: 'meta',
    label: 'Meta',
    description: 'Runtime computed values',
    icon: 'Calculator',
    variables: [
      {
        name: 'word_count',
        fullName: 'meta.word_count',
        description: 'Word count of the source text',
        type: 'number',
        source: 'computed',
        stages: ['translation', 'optimization'],
        example: '156',
      },
      {
        name: 'char_count',
        fullName: 'meta.char_count',
        description: 'Character count of the source text',
        type: 'number',
        source: 'computed',
        stages: ['translation', 'optimization'],
        example: '892',
      },
      {
        name: 'paragraph_index',
        fullName: 'meta.paragraph_index',
        description: 'Index of current paragraph within chapter',
        type: 'number',
        source: 'paragraph.order_index',
        stages: ['translation', 'proofreading'],
        example: '5',
      },
      {
        name: 'chapter_index',
        fullName: 'meta.chapter_index',
        description: 'Index of current chapter',
        type: 'number',
        source: 'chapter.order_index',
        stages: ['translation', 'proofreading'],
        example: '3',
      },
      {
        name: 'stage',
        fullName: 'meta.stage',
        description: 'Current processing stage',
        type: 'string',
        source: 'runtime',
        stages: ['analysis', 'translation', 'optimization', 'proofreading'],
        example: 'translation',
      },
    ],
  },
  {
    id: 'user',
    label: 'Custom',
    description: 'User-defined variables for project-specific needs',
    icon: 'User',
    variables: [
      {
        name: 'glossary',
        fullName: 'user.glossary',
        description: 'Custom terminology glossary for the project',
        type: 'object',
        source: 'project_variables.glossary',
        stages: ['translation', 'proofreading'],
        example: '{"covenant": "translated_term", "redemption": "translated_term"}',
        structure: 'Record<string, string>',
      },
      {
        name: 'special_instructions',
        fullName: 'user.special_instructions',
        description: 'Special handling instructions for this project',
        type: 'string',
        source: 'project_variables.special_instructions',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'This book contains many Puritan-era references...',
      },
      {
        name: 'macros',
        fullName: 'user.macros',
        description: 'Custom macro definitions for reuse',
        type: 'object',
        source: 'project_variables.macros',
        stages: ['analysis', 'translation', 'optimization', 'proofreading'],
        example: '{"book_info": "{{project.title}}"}',
        structure: 'Record<string, string>',
      },
    ],
  },
]

/**
 * Default macros available in all templates
 * Note: Use English labels here; Chinese text should be in prompt templates
 */
export const DEFAULT_MACROS: Record<string, string> = {
  book_info: '{{project.title}} by {{project.author}}',
  style_guide: '{{#if derived.writing_style}}**Style**: {{derived.writing_style}}\n{{/if}}{{#if derived.tone}}**Tone**: {{derived.tone}}{{/if}}',
  terminology_section: '{{#if derived.has_terminology}}### Terminology\n{{derived.terminology_table}}{{/if}}',
}

/**
 * Get all variables available for a specific stage
 */
export function getVariablesForStage(stage: PromptStage): VariableDefinition[] {
  const result: VariableDefinition[] = []
  for (const category of VARIABLE_REGISTRY) {
    for (const variable of category.variables) {
      if (variable.stages.includes(stage)) {
        result.push(variable)
      }
    }
  }
  return result
}

/**
 * Get variables grouped by category for a specific stage
 */
export function getVariablesByCategory(stage: PromptStage): VariableCategoryInfo[] {
  return VARIABLE_REGISTRY.map((category) => ({
    ...category,
    variables: category.variables.filter((v) => v.stages.includes(stage)),
  })).filter((category) => category.variables.length > 0)
}

/**
 * Find a variable by its full name (e.g., "project.title")
 */
export function findVariable(fullName: string): VariableDefinition | undefined {
  for (const category of VARIABLE_REGISTRY) {
    const found = category.variables.find((v) => v.fullName === fullName)
    if (found) return found
  }
  return undefined
}

/**
 * Get all variable full names for validation
 */
export function getAllVariableNames(): string[] {
  const names: string[] = []
  for (const category of VARIABLE_REGISTRY) {
    for (const variable of category.variables) {
      names.push(variable.fullName)
      // Also add short names for backward compatibility
      names.push(variable.name)
    }
  }
  return names
}

/**
 * Extract variable references from a template string
 *
 * Handles all variable patterns:
 * - Simple: {{var}} or {{namespace.var}}
 * - Fallback: {{var | default:"value"}}
 * - Typed: {{var:type}}
 * - Conditionals: {{#if var}}, {{#if var1 && var2}}, {{#if var1 || var2}}
 * - Loops: {{#each var}}
 */
export function extractVariableReferences(template: string): string[] {
  const allVars = new Set<string>()

  // 1. Simple variables: {{var}}
  const simplePattern = /\{\{(\w+(?:\.\w+)*)\}\}/g
  let match
  while ((match = simplePattern.exec(template)) !== null) {
    const varName = match[1]
    if (!varName.startsWith('@') && varName !== 'this') {
      allVars.add(varName)
    }
  }

  // 2. Fallback variables: {{var | default:"value"}}
  const fallbackPattern = /\{\{(\w+(?:\.\w+)*)\s*\|/g
  while ((match = fallbackPattern.exec(template)) !== null) {
    allVars.add(match[1])
  }

  // 3. Typed variables: {{var:type}}
  const typedPattern = /\{\{(\w+(?:\.\w+)*):\w+\}\}/g
  while ((match = typedPattern.exec(template)) !== null) {
    allVars.add(match[1])
  }

  // 4. Simple conditionals: {{#if var}}
  const ifPattern = /\{\{#if\s+(\w+(?:\.\w+)*)\}\}/g
  while ((match = ifPattern.exec(template)) !== null) {
    allVars.add(match[1])
  }

  // 5. AND conditionals: {{#if var1 && var2}}
  const ifAndPattern = /\{\{#if\s+([\w.]+(?:\s*&&\s*[\w.]+)+)\}\}/g
  while ((match = ifAndPattern.exec(template)) !== null) {
    const conditions = match[1].split('&&').map((c) => c.trim())
    conditions.forEach((c) => allVars.add(c))
  }

  // 6. OR conditionals: {{#if var1 || var2}}
  const ifOrPattern = /\{\{#if\s+([\w.]+(?:\s*\|\|\s*[\w.]+)+)\}\}/g
  while ((match = ifOrPattern.exec(template)) !== null) {
    const conditions = match[1].split('||').map((c) => c.trim())
    conditions.forEach((c) => allVars.add(c))
  }

  // 7. Each blocks: {{#each var}}
  const eachPattern = /\{\{#each\s+(\w+(?:\.\w+)*)\}\}/g
  while ((match = eachPattern.exec(template)) !== null) {
    allVars.add(match[1])
  }

  return [...allVars]
}

/**
 * Validate variable references in a template
 */
export function validateTemplateVariables(
  template: string,
  stage: PromptStage
): { valid: string[]; invalid: string[]; warnings: string[]; legacy: string[] } {
  const references = extractVariableReferences(template)
  const availableVars = getVariablesForStage(stage)
  const availableNames = new Set(availableVars.flatMap((v) => [v.fullName, v.name]))

  const valid: string[] = []
  const invalid: string[] = []
  const warnings: string[] = []
  const legacy: string[] = []

  for (const ref of references) {
    if (availableNames.has(ref)) {
      valid.push(ref)
      // Check if using legacy alias
      const varDef = availableVars.find((v) => v.fullName === ref || v.name === ref)
      if (varDef?.isLegacy) {
        legacy.push(ref)
      }
    } else {
      // Check if it exists in other stages
      const allVar = findVariable(ref) ||
        VARIABLE_REGISTRY.flatMap(c => c.variables).find(v => v.name === ref)
      if (allVar) {
        warnings.push(ref) // Variable exists but not available in this stage
      } else {
        invalid.push(ref)
      }
    }
  }

  return { valid, invalid, warnings, legacy }
}

/**
 * Get canonical name for a variable (resolves legacy aliases)
 */
export function getCanonicalName(varName: string): string {
  for (const category of VARIABLE_REGISTRY) {
    const varDef = category.variables.find((v) => v.fullName === varName || v.name === varName)
    if (varDef?.canonicalName) {
      return varDef.canonicalName
    }
    if (varDef) {
      return varDef.fullName
    }
  }
  return varName
}

/**
 * Represents a syntax error in a template
 */
export interface TemplateSyntaxError {
  message: string
  line?: number
  column?: number
  context?: string
}

/**
 * Validate template syntax for common errors
 *
 * Checks for:
 * - Unmatched {{ and }}
 * - Unmatched {{#if}} and {{/if}}
 * - Unmatched {{#each}} and {{/each}}
 * - Unmatched {{#unless}} and {{/unless}}
 * - Invalid block nesting
 */
export function validateTemplateSyntax(template: string): TemplateSyntaxError[] {
  const errors: TemplateSyntaxError[] = []

  const getLineCol = (text: string, pos: number): [number, number] => {
    const lines = text.slice(0, pos).split('\n')
    return [lines.length, (lines[lines.length - 1]?.length ?? 0) + 1]
  }

  const getContext = (text: string, pos: number, length = 40): string => {
    const start = Math.max(0, pos - 20)
    const end = Math.min(text.length, pos + length)
    let snippet = text.slice(start, end)
    if (start > 0) snippet = '...' + snippet
    if (end < text.length) snippet = snippet + '...'
    return snippet.replace(/\n/g, '\\n')
  }

  // Check for unmatched braces
  const openCount = (template.match(/\{\{/g) || []).length
  const closeCount = (template.match(/\}\}/g) || []).length
  if (openCount !== closeCount) {
    errors.push({
      message: `Unmatched braces: ${openCount} '{{' but ${closeCount} '}}'`,
    })
  }

  // Check for matching block pairs
  const blockPairs = [
    { open: /\{\{#if\s+/g, close: /\{\{\/if\}\}/g, name: 'if' },
    { open: /\{\{#each\s+/g, close: /\{\{\/each\}\}/g, name: 'each' },
    { open: /\{\{#unless\s+/g, close: /\{\{\/unless\}\}/g, name: 'unless' },
  ]

  for (const { open, close, name } of blockPairs) {
    const opens = (template.match(open) || []).length
    const closes = (template.match(close) || []).length
    if (opens !== closes) {
      errors.push({
        message: `Unmatched {{#${name}}}: ${opens} opening, ${closes} closing`,
      })
    }
  }

  // Check for proper nesting using stack
  const blockPattern = /\{\{(#if|#each|#unless|\/if|\/each|\/unless)\b[^}]*\}\}/g
  const stack: Array<{ type: string; pos: number }> = []
  let match

  while ((match = blockPattern.exec(template)) !== null) {
    const tag = match[1]
    const pos = match.index

    if (tag.startsWith('#')) {
      stack.push({ type: tag.slice(1), pos })
    } else {
      const blockType = tag.slice(1)
      if (stack.length === 0) {
        const [line, col] = getLineCol(template, pos)
        errors.push({
          message: `Unexpected {{/${blockType}}} with no matching opening tag`,
          line,
          column: col,
          context: getContext(template, pos),
        })
      } else if (stack[stack.length - 1].type !== blockType) {
        const [line, col] = getLineCol(template, pos)
        const expected = stack[stack.length - 1].type
        errors.push({
          message: `Mismatched block: expected {{/${expected}}}, found {{/${blockType}}}`,
          line,
          column: col,
          context: getContext(template, pos),
        })
      } else {
        stack.pop()
      }
    }
  }

  // Check for unclosed blocks
  for (const { type, pos } of stack) {
    const [line, col] = getLineCol(template, pos)
    errors.push({
      message: `Unclosed {{#${type}}} block`,
      line,
      column: col,
      context: getContext(template, pos),
    })
  }

  return errors
}
