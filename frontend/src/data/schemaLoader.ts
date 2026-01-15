/**
 * Schema Loader - loads shared variable schema
 *
 * This module loads the shared variable schema from the shared directory.
 * It provides type-safe access to variable definitions that are consistent
 * with the backend.
 *
 * Note: In a production setup, this schema would typically be loaded from
 * an API endpoint or bundled at build time. For now, we define the types
 * and provide utilities that match the schema structure.
 */

import type { PromptStage, VariableType } from './variableRegistry'

/**
 * Variable definition from shared schema
 */
export interface SchemaVariable {
  name: string
  fullName: string
  category: string
  type: VariableType
  description: string
  source: string
  stages: PromptStage[]
  example: string
  required?: boolean
  structure?: string
  canonicalName?: string
  isLegacy?: boolean
}

/**
 * Category definition from shared schema
 */
export interface SchemaCategory {
  label: string
  description: string
  icon: string
}

/**
 * Full schema structure
 */
export interface VariableSchemaType {
  version: string
  stages: PromptStage[]
  categories: Record<string, SchemaCategory>
  variables: SchemaVariable[]
  aliases: Record<string, string>
  defaultMacros: Record<string, string>
  templateSyntax: Record<string, string>
  typeFormats: Record<string, string>
}

/**
 * Get variable by full name from schema
 */
export function getSchemaVariable(
  schema: VariableSchemaType,
  fullName: string
): SchemaVariable | undefined {
  return schema.variables.find((v) => v.fullName === fullName)
}

/**
 * Get variables for a specific stage from schema
 */
export function getSchemaVariablesForStage(
  schema: VariableSchemaType,
  stage: PromptStage
): SchemaVariable[] {
  return schema.variables.filter((v) => v.stages.includes(stage))
}

/**
 * Get variables by category from schema
 */
export function getSchemaVariablesByCategory(
  schema: VariableSchemaType,
  category: string
): SchemaVariable[] {
  return schema.variables.filter((v) => v.category === category)
}

/**
 * Resolve alias to canonical name
 */
export function resolveAlias(schema: VariableSchemaType, varName: string): string {
  if (varName in schema.aliases) {
    return schema.aliases[varName]
  }

  // Check if it's a legacy variable with canonicalName
  const legacyVar = schema.variables.find(
    (v) => v.isLegacy && v.fullName === varName && v.canonicalName
  )
  if (legacyVar?.canonicalName) {
    return legacyVar.canonicalName
  }

  return varName
}

/**
 * Check if variable is valid for a stage
 */
export function isVariableValidForStage(
  schema: VariableSchemaType,
  varName: string,
  stage: PromptStage
): boolean {
  const variable = getSchemaVariable(schema, varName)
  if (variable) {
    return variable.stages.includes(stage)
  }
  return false
}

/**
 * Get all legacy variables from schema
 */
export function getLegacyVariables(schema: VariableSchemaType): SchemaVariable[] {
  return schema.variables.filter((v) => v.isLegacy === true)
}

/**
 * Validate that a variable exists in the schema
 */
export function variableExists(schema: VariableSchemaType, varName: string): boolean {
  // Check direct match
  if (schema.variables.some((v) => v.fullName === varName || v.name === varName)) {
    return true
  }

  // Check aliases
  if (varName in schema.aliases) {
    return true
  }

  return false
}

