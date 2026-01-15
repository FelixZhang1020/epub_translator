"""Output schemas for LLM stages with structured JSON output.

This module defines the expected JSON output structure for stages that
produce structured data (Analysis and Proofreading).
"""

from typing import Dict, List, TypedDict


class OutputFieldSchema(TypedDict):
    """Schema definition for a single output field."""
    name: str           # Field name (e.g., "writing_style", "translation_principles.priority_order")
    description: str    # Human-readable description
    type: str          # "string", "list", "object", "boolean"


# =============================================================================
# Analysis Output Schemas
# =============================================================================

ANALYSIS_OUTPUT_SCHEMA: Dict[str, List[OutputFieldSchema]] = {
    "default": [
        {
            "name": "author_biography",
            "description": "Author background and context",
            "type": "string",
        },
        {
            "name": "writing_style",
            "description": "Writing style characteristics",
            "type": "string",
        },
        {
            "name": "tone",
            "description": "Tone of writing",
            "type": "string",
        },
        {
            "name": "target_audience",
            "description": "Intended audience",
            "type": "string",
        },
        {
            "name": "genre_conventions",
            "description": "Genre conventions and patterns",
            "type": "string",
        },
        {
            "name": "key_terminology",
            "description": "Key terms to translate consistently",
            "type": "object",
        },
        {
            "name": "translation_principles.priority_order",
            "description": "Translation priority: faithfulness/expressiveness/elegance",
            "type": "list",
        },
        {
            "name": "translation_principles.faithfulness_boundary",
            "description": "What must be literally translated",
            "type": "string",
        },
        {
            "name": "translation_principles.permissible_adaptation",
            "description": "What can be adapted or paraphrased",
            "type": "string",
        },
        {
            "name": "translation_principles.style_constraints",
            "description": "Style rules and constraints",
            "type": "string",
        },
        {
            "name": "translation_principles.red_lines",
            "description": "Prohibited translation behaviors",
            "type": "string",
        },
        {
            "name": "custom_guidelines",
            "description": "Custom translation guidelines",
            "type": "list",
        },
    ],
    "reformed-theology": [
        # Meta information
        {
            "name": "meta.book_title",
            "description": "Book title",
            "type": "string",
        },
        {
            "name": "meta.author",
            "description": "Author name",
            "type": "string",
        },
        {
            "name": "meta.assumed_tradition",
            "description": "Assumed theological tradition",
            "type": "string",
        },
        {
            "name": "meta.target_chinese_bible_version",
            "description": "Target Chinese Bible version",
            "type": "string",
        },
        {
            "name": "meta.intended_use",
            "description": "Intended use cases",
            "type": "list",
        },
        # Author biography
        {
            "name": "author_biography.theological_identity",
            "description": "Theological position and denominational background",
            "type": "string",
        },
        {
            "name": "author_biography.historical_context",
            "description": "Historical context and theological controversies",
            "type": "string",
        },
        {
            "name": "author_biography.influence_on_translation",
            "description": "How background influences translation decisions",
            "type": "string",
        },
        # Work profile
        {
            "name": "work_profile.genre",
            "description": "Work genre (systematic theology, devotional, etc.)",
            "type": "string",
        },
        {
            "name": "work_profile.writing_style",
            "description": "Writing style and syntactic complexity",
            "type": "string",
        },
        {
            "name": "work_profile.tone",
            "description": "Tone (pastoral, doctrinal, academic, etc.)",
            "type": "string",
        },
        {
            "name": "work_profile.target_audience",
            "description": "Original target audience",
            "type": "string",
        },
        # Key terminology
        {
            "name": "key_terminology",
            "description": "List of key theological terms",
            "type": "list",
        },
        # Translation principles
        {
            "name": "translation_principles.priority_order",
            "description": "Translation priority order",
            "type": "list",
        },
        {
            "name": "translation_principles.must_be_literal",
            "description": "What must be literally translated",
            "type": "string",
        },
        {
            "name": "translation_principles.allowed_adjustment",
            "description": "What can be adapted",
            "type": "string",
        },
        {
            "name": "translation_principles.style_constraints",
            "description": "Style constraints",
            "type": "string",
        },
        {
            "name": "translation_principles.absolute_red_lines",
            "description": "Absolute prohibited actions",
            "type": "string",
        },
        # Custom watchlist
        {
            "name": "custom_watchlist",
            "description": "Custom items to watch for",
            "type": "list",
        },
    ],
}


# =============================================================================
# Proofreading Output Schema
# =============================================================================

PROOFREADING_OUTPUT_SCHEMA: List[OutputFieldSchema] = [
    {
        "name": "needs_improvement",
        "description": "Whether changes are recommended",
        "type": "boolean",
    },
    {
        "name": "improvement_level",
        "description": "Severity level: none/optional/recommended/critical",
        "type": "string",
    },
    {
        "name": "issue_types",
        "description": "Types of issues found (accuracy, naturalness, etc.)",
        "type": "list",
    },
    {
        "name": "suggested_translation",
        "description": "Improved translation text",
        "type": "string",
    },
    {
        "name": "explanation",
        "description": "Explanation of changes",
        "type": "string",
    },
]


# =============================================================================
# Derived Variable Mappings for Display
# =============================================================================

class DerivedMappingDisplay(TypedDict):
    """Display information for derived variable mappings."""
    source: str        # Source field in raw analysis (e.g., "writing_style")
    target: str        # Target derived variable (e.g., "derived.writing_style")
    transform: str     # Optional transform function name
    used_in: List[str] # Which stages use this variable


DERIVED_MAPPING_DISPLAY: List[DerivedMappingDisplay] = [
    # Author info (both schemas)
    {
        "source": "author_name",
        "target": "derived.author_name",
        "transform": "",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    {
        "source": "author_biography",
        "target": "derived.author_biography",
        "transform": "",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    {
        "source": "author_background",
        "target": "derived.author_biography",
        "transform": "format_author_biography",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    # Work profile (both schemas)
    {
        "source": "writing_style",
        "target": "derived.writing_style",
        "transform": "",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    {
        "source": "tone",
        "target": "derived.tone",
        "transform": "",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    {
        "source": "target_audience",
        "target": "derived.target_audience",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "genre_conventions",
        "target": "derived.genre_conventions",
        "transform": "",
        "used_in": ["translation"],
    },
    # Terminology (both schemas)
    {
        "source": "key_terminology",
        "target": "derived.key_terminology",
        "transform": "",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    {
        "source": "key_terminology",
        "target": "derived.terminology_table",
        "transform": "format_terminology",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    # Translation principles - default schema names
    {
        "source": "translation_principles.priority_order",
        "target": "derived.priority_order",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "translation_principles.faithfulness_boundary",
        "target": "derived.faithfulness_boundary",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "translation_principles.permissible_adaptation",
        "target": "derived.permissible_adaptation",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "translation_principles.style_constraints",
        "target": "derived.style_constraints",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "translation_principles.red_lines",
        "target": "derived.red_lines",
        "transform": "",
        "used_in": ["translation"],
    },
    # Translation principles - reformed-theology schema alternate names
    {
        "source": "translation_principles.must_be_literal",
        "target": "derived.faithfulness_boundary",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "translation_principles.allowed_adjustment",
        "target": "derived.permissible_adaptation",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "translation_principles.absolute_red_lines",
        "target": "derived.red_lines",
        "transform": "",
        "used_in": ["translation"],
    },
    # Custom guidelines (both schemas)
    {
        "source": "custom_guidelines",
        "target": "derived.custom_guidelines",
        "transform": "",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    {
        "source": "custom_watchlist",
        "target": "derived.custom_guidelines",
        "transform": "",
        "used_in": ["translation", "optimization", "proofreading"],
    },
    # Reformed-theology specific
    {
        "source": "meta.book_title",
        "target": "derived.book_title",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "meta.assumed_tradition",
        "target": "derived.assumed_tradition",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "meta.target_chinese_bible_version",
        "target": "derived.bible_version",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "author_biography.theological_identity",
        "target": "derived.author_theological_identity",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "author_biography.historical_context",
        "target": "derived.author_historical_context",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "author_biography.influence_on_translation",
        "target": "derived.author_influence",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "bible_reference_policy",
        "target": "derived.bible_reference_policy",
        "transform": "format_bible_policy",
        "used_in": ["translation"],
    },
    {
        "source": "syntax_and_logic.sentence_splitting_rules",
        "target": "derived.sentence_splitting_rules",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "syntax_and_logic.logical_connectors",
        "target": "derived.logical_connectors",
        "transform": "",
        "used_in": ["translation"],
    },
    {
        "source": "notes_policy.allowed",
        "target": "derived.notes_allowed",
        "transform": "format_list",
        "used_in": ["translation"],
    },
    {
        "source": "notes_policy.forbidden",
        "target": "derived.notes_forbidden",
        "transform": "format_list",
        "used_in": ["translation"],
    },
]

