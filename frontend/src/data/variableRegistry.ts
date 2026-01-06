/**
 * Variable Registry - defines all available template variables
 *
 * This is the source of truth for what variables can be used in prompt templates.
 * Variables are organized by category (namespace) and include metadata about
 * their source, availability, and usage.
 */

export type VariableCategory = 'project' | 'content' | 'pipeline' | 'derived' | 'user'
export type PromptStage = 'analysis' | 'translation' | 'optimization' | 'proofreading' | 'reasoning'
export type VariableType = 'string' | 'number' | 'boolean' | 'array' | 'object'

export interface VariableDefinition {
  /** Variable name (without namespace prefix) */
  name: string
  /** Full variable reference for templates: {{namespace.name}} */
  fullName: string
  /** English description */
  description: string
  /** Chinese description */
  descriptionZh: string
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
}

export interface VariableCategoryInfo {
  /** Category ID */
  id: VariableCategory
  /** English label */
  label: string
  /** Chinese label */
  labelZh: string
  /** Description of this category */
  description: string
  /** Description in Chinese */
  descriptionZh: string
  /** Icon name (lucide) */
  icon: string
  /** Variables in this category */
  variables: VariableDefinition[]
}

/**
 * Complete variable registry organized by category
 */
export const VARIABLE_REGISTRY: VariableCategoryInfo[] = [
  {
    id: 'project',
    label: 'Project',
    labelZh: '项目',
    description: 'Static metadata from the EPUB project',
    descriptionZh: '来自 EPUB 项目的静态元数据',
    icon: 'BookOpen',
    variables: [
      {
        name: 'title',
        fullName: 'project.title',
        description: 'Book title from EPUB metadata',
        descriptionZh: 'EPUB 元数据中的书名',
        type: 'string',
        source: 'project.epub_title',
        stages: ['analysis', 'translation', 'optimization', 'proofreading', 'reasoning'],
        example: 'Knowing God',
      },
      {
        name: 'author',
        fullName: 'project.author',
        description: 'Author name from EPUB metadata',
        descriptionZh: 'EPUB 元数据中的作者名',
        type: 'string',
        source: 'project.epub_author',
        stages: ['analysis', 'translation', 'optimization', 'proofreading', 'reasoning'],
        example: 'J.I. Packer',
      },
      {
        name: 'author_background',
        fullName: 'project.author_background',
        description: 'Custom author background information provided by user',
        descriptionZh: '用户提供的作者背景资料',
        type: 'string',
        source: 'project.author_background',
        stages: ['translation'],
        example: 'J.I. Packer (1926-2020) was a British-born Canadian evangelical theologian...',
      },
      {
        name: 'source_language',
        fullName: 'project.source_language',
        description: 'Source language of the book',
        descriptionZh: '书籍的源语言',
        type: 'string',
        source: 'project.epub_language',
        stages: ['analysis', 'translation'],
        example: 'en',
      },
      {
        name: 'target_language',
        fullName: 'project.target_language',
        description: 'Target translation language',
        descriptionZh: '翻译的目标语言',
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
    labelZh: '内容',
    description: 'Current paragraph or text being processed',
    descriptionZh: '当前正在处理的段落或文本',
    icon: 'FileText',
    variables: [
      {
        name: 'source_text',
        fullName: 'content.source_text',
        description: 'Current paragraph source text to be translated',
        descriptionZh: '当前待翻译的段落原文',
        type: 'string',
        source: 'paragraph.source_text',
        stages: ['translation', 'optimization'],
        example: 'The grace of God is infinite and eternal, reaching to the depths of human need.',
        required: true,
      },
      {
        name: 'original_text',
        fullName: 'content.original_text',
        description: 'Original English text (alias for source_text in review stages)',
        descriptionZh: '原始英文文本（校对阶段使用的别名）',
        type: 'string',
        source: 'paragraph.source_text',
        stages: ['proofreading', 'reasoning'],
        example: 'The grace of God is infinite and eternal.',
        required: true,
      },
      {
        name: 'translated_text',
        fullName: 'content.translated_text',
        description: 'Current Chinese translation of the paragraph',
        descriptionZh: '当前段落的中文翻译',
        type: 'string',
        source: 'paragraph.target_text',
        stages: ['optimization', 'proofreading', 'reasoning'],
        example: '神的恩典是无限而永恒的，触及人类需要的最深处。',
      },
      {
        name: 'current_translation',
        fullName: 'content.current_translation',
        description: 'Alias for translated_text used in proofreading',
        descriptionZh: '校对阶段使用的 translated_text 别名',
        type: 'string',
        source: 'paragraph.target_text',
        stages: ['proofreading'],
        example: '神的恩典是无限而永恒的。',
      },
      {
        name: 'existing_translation',
        fullName: 'content.existing_translation',
        description: 'Existing translation to be optimized',
        descriptionZh: '待优化的现有翻译',
        type: 'string',
        source: 'paragraph.target_text',
        stages: ['optimization'],
        example: '上帝的恩典是无穷无尽的。',
      },
      {
        name: 'chapter_title',
        fullName: 'content.chapter_title',
        description: 'Title of the current chapter',
        descriptionZh: '当前章节的标题',
        type: 'string',
        source: 'chapter.title',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'Chapter 1: Knowing and Being Known',
      },
      {
        name: 'paragraph_index',
        fullName: 'content.paragraph_index',
        description: 'Index of current paragraph within chapter',
        descriptionZh: '当前段落在章节中的索引',
        type: 'number',
        source: 'paragraph.order_index',
        stages: ['translation'],
        example: '5',
      },
      {
        name: 'sample_paragraphs',
        fullName: 'content.sample_paragraphs',
        description: 'Sample paragraphs for book analysis',
        descriptionZh: '用于分析书籍的样本段落',
        type: 'string',
        source: 'extracted_samples',
        stages: ['analysis'],
        example: 'Paragraph 1: The knowledge of God...\n\nParagraph 2: To know God is...',
        required: true,
      },
    ],
  },
  {
    id: 'pipeline',
    label: 'Pipeline',
    labelZh: '流水线',
    description: 'Output from previous processing steps',
    descriptionZh: '来自前序处理步骤的输出',
    icon: 'GitBranch',
    variables: [
      {
        name: 'analysis_result',
        fullName: 'pipeline.analysis_result',
        description: 'Raw JSON result from analysis step',
        descriptionZh: '分析步骤输出的原始 JSON 结果',
        type: 'object',
        source: 'analysis_step.result',
        stages: ['translation'],
        example: '{"meta": {...}, "terminology_policy": {...}}',
        structure: 'Translation Execution Spec JSON structure',
      },
      {
        name: 'analysis_text',
        fullName: 'pipeline.analysis_text',
        description: 'Formatted analysis result for inclusion in prompts',
        descriptionZh: '格式化的分析结果，用于插入提示词',
        type: 'string',
        source: 'analysis_step.formatted_result',
        stages: ['translation'],
        example: '## Translation Guidelines\n\n### Terminology\n...',
      },
      {
        name: 'previous_translation',
        fullName: 'pipeline.previous_translation',
        description: 'Translation from previous iteration (for refinement)',
        descriptionZh: '前一次迭代的翻译结果（用于优化）',
        type: 'string',
        source: 'previous_step.result',
        stages: ['optimization'],
        example: '神的恩典是无限的。',
      },
      {
        name: 'context_before',
        fullName: 'pipeline.context_before',
        description: 'Translated text from preceding paragraphs for context',
        descriptionZh: '前文已翻译的段落，提供上下文',
        type: 'string',
        source: 'context_window.before',
        stages: ['translation'],
        example: '在前一章中，作者讨论了...',
      },
      {
        name: 'context_after',
        fullName: 'pipeline.context_after',
        description: 'Source text from following paragraphs for context',
        descriptionZh: '后文的原文段落，提供上下文',
        type: 'string',
        source: 'context_window.after',
        stages: ['translation'],
        example: 'In the next section, the author explores...',
      },
    ],
  },
  {
    id: 'derived',
    label: 'Derived',
    labelZh: '派生',
    description: 'Values computed or extracted from other data',
    descriptionZh: '从其他数据计算或提取的值',
    icon: 'Sparkles',
    variables: [
      {
        name: 'writing_style',
        fullName: 'derived.writing_style',
        description: 'Writing style extracted from analysis result',
        descriptionZh: '从分析结果中提取的写作风格',
        type: 'string',
        source: 'analysis_result.style_and_register.overall_register',
        stages: ['proofreading'],
        example: 'Academic theological prose with pastoral warmth',
      },
      {
        name: 'tone',
        fullName: 'derived.tone',
        description: 'Tone of the writing extracted from analysis',
        descriptionZh: '从分析结果中提取的语气',
        type: 'string',
        source: 'analysis_result.style_and_register.tone',
        stages: ['proofreading'],
        example: 'Reverent, instructive, encouraging',
      },
      {
        name: 'terminology_table',
        fullName: 'derived.terminology_table',
        description: 'Formatted terminology table from analysis',
        descriptionZh: '从分析结果中提取的术语表',
        type: 'string',
        source: 'analysis_result.terminology_policy.termbase_seed',
        stages: ['translation', 'proofreading'],
        example: '| English | Chinese | Notes |\n| grace | 恩典 | ... |',
      },
      {
        name: 'word_count',
        fullName: 'derived.word_count',
        description: 'Word count of the source text',
        descriptionZh: '源文本的词数',
        type: 'number',
        source: 'computed',
        stages: ['translation', 'optimization'],
        example: '156',
      },
    ],
  },
  {
    id: 'user',
    label: 'Custom',
    labelZh: '自定义',
    description: 'User-defined variables for project-specific needs',
    descriptionZh: '用户为项目特定需求定义的变量',
    icon: 'User',
    variables: [
      {
        name: 'custom_prompts',
        fullName: 'user.custom_prompts',
        description: 'Array of custom instruction strings',
        descriptionZh: '自定义指令字符串数组',
        type: 'array',
        source: 'project.custom_prompts',
        stages: ['translation'],
        example: '["Use formal register", "Preserve biblical quotes"]',
        structure: 'string[]',
      },
      {
        name: 'glossary',
        fullName: 'user.glossary',
        description: 'Custom terminology glossary for the project',
        descriptionZh: '项目的自定义术语表',
        type: 'object',
        source: 'project_variables.glossary',
        stages: ['translation', 'proofreading'],
        example: '{"covenant": "圣约", "redemption": "救赎"}',
        structure: 'Record<string, string>',
      },
      {
        name: 'special_instructions',
        fullName: 'user.special_instructions',
        description: 'Special handling instructions for this project',
        descriptionZh: '项目的特殊处理指令',
        type: 'string',
        source: 'project_variables.special_instructions',
        stages: ['translation', 'optimization', 'proofreading'],
        example: 'This book contains many Puritan-era references...',
      },
    ],
  },
]

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
 */
export function extractVariableReferences(template: string): string[] {
  const pattern = /\{\{(\w+(?:\.\w+)*)\}\}/g
  const matches: string[] = []
  let match
  while ((match = pattern.exec(template)) !== null) {
    const varName = match[1]
    // Skip special variables like @key, this
    if (!varName.startsWith('@') && varName !== 'this') {
      matches.push(varName)
    }
  }
  return [...new Set(matches)]
}

/**
 * Validate variable references in a template
 */
export function validateTemplateVariables(
  template: string,
  stage: PromptStage
): { valid: string[]; invalid: string[]; warnings: string[] } {
  const references = extractVariableReferences(template)
  const availableVars = getVariablesForStage(stage)
  const availableNames = new Set(availableVars.flatMap((v) => [v.fullName, v.name]))

  const valid: string[] = []
  const invalid: string[] = []
  const warnings: string[] = []

  for (const ref of references) {
    if (availableNames.has(ref)) {
      valid.push(ref)
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

  return { valid, invalid, warnings }
}
