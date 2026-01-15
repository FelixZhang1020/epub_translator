"""Prompt template loader and renderer.

This module handles loading prompt templates from .md files and rendering
them with variable substitution.

Supports:
- Named templates: system.{template_name}.md (e.g., system.default.md, system.reformed-theology.md)
- Project-local user prompts from projects/{project_id}/prompts/
- Global system prompts from backend/prompts/
- Variable aliases for backward compatibility
- Fallback values: {{var | default:"value"}}
- Conditional combinations: {{#if var1 && var2}}
- Composite variables/macros: {{@macro_name}}
"""

import hashlib
import json
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# Variable Alias System
# =============================================================================
# Maps legacy/stage-specific variable names to canonical names.
# This allows templates to use consistent naming while maintaining
# backward compatibility with existing templates.

VARIABLE_ALIASES: Dict[str, str] = {
    # Content aliases - map to canonical content.source / content.target
    "source_text": "content.source",
    "content.source_text": "content.source",

    # Derived aliases for cleaner access
    "writing_style": "derived.writing_style",
    "tone": "derived.tone",
    "terminology_table": "derived.terminology_table",
}

# Reverse mapping for documentation
CANONICAL_VARIABLES: Dict[str, List[str]] = {}
for alias, canonical in VARIABLE_ALIASES.items():
    if canonical not in CANONICAL_VARIABLES:
        CANONICAL_VARIABLES[canonical] = []
    CANONICAL_VARIABLES[canonical].append(alias)


def slugify(text: str) -> str:
    """Convert text to a URL/filename-safe slug.

    Handles Chinese characters by converting to pinyin-like representation
    or using a hash fallback.

    Args:
        text: Input text (can contain Chinese, English, etc.)

    Returns:
        Lowercase slug with hyphens (e.g., "my-template-name")
    """
    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)

    # Convert to lowercase
    text = text.lower()

    # Replace common Chinese punctuation with spaces
    text = re.sub(r'[，。！？、；：""''（）【】]', ' ', text)

    # Replace any non-alphanumeric (except Chinese) with hyphen
    # Keep Chinese characters, letters, numbers
    text = re.sub(r'[^\w\u4e00-\u9fff]+', '-', text)

    # Remove leading/trailing hyphens
    text = text.strip('-')

    # Collapse multiple hyphens
    text = re.sub(r'-+', '-', text)

    # If result contains Chinese, create a hash-based slug
    if re.search(r'[\u4e00-\u9fff]', text):
        # Use first 8 chars of hash for uniqueness
        hash_suffix = hashlib.md5(text.encode()).hexdigest()[:8]
        # Extract any English parts
        english_parts = re.sub(r'[\u4e00-\u9fff]+', '-', text)
        english_parts = re.sub(r'-+', '-', english_parts).strip('-')
        if english_parts:
            return f"{english_parts}-{hash_suffix}"
        return f"template-{hash_suffix}"

    # If empty after processing, generate from hash
    if not text:
        return f"template-{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"

    return text


class PromptTemplate(BaseModel):
    """Prompt template model."""

    type: str
    system_prompt: str
    user_prompt_template: str
    variables: list[str]
    last_modified: datetime
    template_name: str = "default"


class TemplateSyntaxError(BaseModel):
    """Represents a syntax error in a template."""

    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    context: Optional[str] = None  # Snippet of the problematic area


class TemplateValidationResult(BaseModel):
    """Result of template validation."""

    is_valid: bool
    missing_variables: list[str]
    warnings: list[str]
    syntax_errors: list[TemplateSyntaxError] = []


class PromptLoader:
    """Load and render prompt templates from .md files."""

    # Base directory for global prompt templates
    PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"

    # Base directory for projects (relative to repo root)
    PROJECTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "projects"

    # Valid prompt types
    VALID_TYPES = ["analysis", "translation", "proofreading", "optimization"]

    # Variable pattern: {{variable_name}}
    VARIABLE_PATTERN = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")

    # Fallback pattern: {{var | default:"value"}} or {{var | default:'value'}}
    FALLBACK_PATTERN = re.compile(
        r"\{\{(\w+(?:\.\w+)*)\s*\|\s*default:\s*[\"']([^\"']*)[\"']\}\}"
    )

    # Macro pattern: {{@macro_name}}
    MACRO_PATTERN = re.compile(r"\{\{@(\w+)\}\}")

    # Conditional block patterns: {{#if var}}...{{/if}}
    IF_PATTERN = re.compile(
        r"\{\{#if\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/if\}\}",
        re.DOTALL
    )

    # Conditional with else: {{#if var}}...{{#else}}...{{/if}}
    IF_ELSE_PATTERN = re.compile(
        r"\{\{#if\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{#else\}\}(.*?)\{\{/if\}\}",
        re.DOTALL
    )

    # Conditional with AND: {{#if var1 && var2}}...{{/if}}
    IF_AND_PATTERN = re.compile(
        r"\{\{#if\s+([\w.]+(?:\s*&&\s*[\w.]+)+)\}\}(.*?)\{\{/if\}\}",
        re.DOTALL
    )

    # Conditional with AND and else: {{#if var1 && var2}}...{{#else}}...{{/if}}
    IF_AND_ELSE_PATTERN = re.compile(
        r"\{\{#if\s+([\w.]+(?:\s*&&\s*[\w.]+)+)\}\}(.*?)\{\{#else\}\}(.*?)\{\{/if\}\}",
        re.DOTALL
    )

    # Conditional with OR: {{#if var1 || var2}}...{{/if}}
    IF_OR_PATTERN = re.compile(
        r"\{\{#if\s+([\w.]+(?:\s*\|\|\s*[\w.]+)+)\}\}(.*?)\{\{/if\}\}",
        re.DOTALL
    )

    # Conditional with OR and else: {{#if var1 || var2}}...{{#else}}...{{/if}}
    IF_OR_ELSE_PATTERN = re.compile(
        r"\{\{#if\s+([\w.]+(?:\s*\|\|\s*[\w.]+)+)\}\}(.*?)\{\{#else\}\}(.*?)\{\{/if\}\}",
        re.DOTALL
    )

    # Unless block: {{#unless var}}...{{/unless}} (negative conditional)
    UNLESS_PATTERN = re.compile(
        r"\{\{#unless\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/unless\}\}",
        re.DOTALL
    )

    # Each block patterns: {{#each var}}...{{/each}}
    EACH_PATTERN = re.compile(
        r"\{\{#each\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/each\}\}",
        re.DOTALL
    )

    # Type formatting hints: {{var:type}} e.g., {{terms:table}}
    TYPED_VAR_PATTERN = re.compile(
        r"\{\{(\w+(?:\.\w+)*):(\w+)\}\}"
    )

    @classmethod
    def get_prompt_path(
        cls,
        prompt_type: str,
        filename: str,
        template_name: str = "default"
    ) -> Path:
        """Get the path to a global prompt file.

        Args:
            prompt_type: Type of prompt (analysis, translation, etc.)
            filename: Base name of the file (system or user)
            template_name: Name of the template (default, reformed-theology, etc.)

        Returns:
            Path to the prompt file
        """
        full_filename = f"{filename}.{template_name}.md"
        return cls.PROMPTS_DIR / prompt_type / full_filename

    @classmethod
    def get_project_prompt_path(
        cls,
        project_id: str,
        prompt_type: str,
        filename: str = "user"
    ) -> Path:
        """Get the path to a project-local prompt file.

        Args:
            project_id: Project UUID
            prompt_type: Type of prompt (analysis, translation, etc.)
            filename: Name of the file (usually 'user')

        Returns:
            Path to the project prompt file
        """
        return cls.PROJECTS_DIR / project_id / "prompts" / prompt_type / f"{filename}.md"

    @classmethod
    def list_available_templates(cls, prompt_type: str) -> list[str]:
        """List available template names for a prompt type.

        Args:
            prompt_type: Type of prompt

        Returns:
            List of template names (e.g., ['default', 'reformed-theology'])
        """
        if prompt_type not in cls.VALID_TYPES:
            return []

        prompt_dir = cls.PROMPTS_DIR / prompt_type
        if not prompt_dir.exists():
            return []

        templates = set()
        for f in prompt_dir.glob("system.*.md"):
            # Extract template name from system.{name}.md
            name = f.stem.replace("system.", "")
            templates.add(name)

        return sorted(templates)

    @classmethod
    def load_project_config(cls, project_id: str) -> Optional[dict]:
        """Load project configuration from config.json.

        Args:
            project_id: Project UUID

        Returns:
            Project config dict or None if not found
        """
        config_path = cls.PROJECTS_DIR / project_id / "config.json"
        if not config_path.exists():
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load project config: {e}")
            return None

    @classmethod
    def load_project_variables(cls, project_id: str) -> Dict[str, Any]:
        """Load project variables from variables.json.

        Variables are used in templates via {{user.variable_name}} syntax.

        Args:
            project_id: Project UUID

        Returns:
            Dict of variable name to value, empty dict if file not found
        """
        variables_path = cls.PROJECTS_DIR / project_id / "variables.json"
        if not variables_path.exists():
            return {}

        try:
            with open(variables_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load project variables: {e}")
            return {}

    @classmethod
    def save_project_variables(cls, project_id: str, variables: Dict[str, Any]) -> None:
        """Save project variables to variables.json.

        Args:
            project_id: Project UUID
            variables: Dict of variable name to value
        """
        variables_path = cls.PROJECTS_DIR / project_id / "variables.json"

        # Ensure directory exists
        variables_path.parent.mkdir(parents=True, exist_ok=True)

        with open(variables_path, "w", encoding="utf-8") as f:
            json.dump(variables, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved project variables to: {variables_path}")

    @classmethod
    def load_template(
        cls,
        prompt_type: str,
        template_name: str = "default",
        project_id: Optional[str] = None
    ) -> PromptTemplate:
        """Load a prompt template from files.

        Priority order:
        1. Project-local user prompt (if project_id provided and file exists)
        2. Global template with specified name
        3. Falls back to 'default' if named template not found

        Args:
            prompt_type: Type of prompt to load
            template_name: Template name (default, reformed-theology, etc.)
            project_id: Optional project ID for project-local prompts

        Returns:
            PromptTemplate with system and user prompts

        Raises:
            ValueError: If prompt type is invalid
            FileNotFoundError: If prompt files don't exist
        """
        if prompt_type not in cls.VALID_TYPES:
            raise ValueError(f"Invalid prompt type: {prompt_type}. "
                           f"Valid types: {cls.VALID_TYPES}")

        # Load system prompt from global templates
        system_path = cls.get_prompt_path(prompt_type, "system", template_name)
        if not system_path.exists():
            # Fall back to default
            system_path = cls.get_prompt_path(prompt_type, "system", "default")

        if not system_path.exists():
            raise FileNotFoundError(f"System prompt not found: {system_path}")

        system_prompt = system_path.read_text(encoding="utf-8")

        # Load user prompt - check project-local first if project_id provided
        user_prompt = None
        user_path = None

        if project_id:
            project_user_path = cls.get_project_prompt_path(
                project_id, prompt_type, "user"
            )
            if project_user_path.exists():
                user_prompt = project_user_path.read_text(encoding="utf-8")
                user_path = project_user_path

        # Fall back to global user template
        if user_prompt is None:
            user_path = cls.get_prompt_path(prompt_type, "user", template_name)
            if not user_path.exists():
                user_path = cls.get_prompt_path(prompt_type, "user", "default")

            if not user_path.exists():
                raise FileNotFoundError(f"User prompt not found: {user_path}")

            user_prompt = user_path.read_text(encoding="utf-8")

        # Extract variables from both prompts
        variables = cls.extract_variables(system_prompt + user_prompt)

        # Get last modified time
        system_mtime = datetime.fromtimestamp(system_path.stat().st_mtime)
        user_mtime = datetime.fromtimestamp(user_path.stat().st_mtime)
        last_modified = max(system_mtime, user_mtime)

        return PromptTemplate(
            type=prompt_type,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt,
            variables=variables,
            last_modified=last_modified,
            template_name=template_name,
        )

    @classmethod
    def load_for_project(cls, project_id: str, prompt_type: str) -> PromptTemplate:
        """Load prompts configured for a specific project.

        Reads project config.json to determine which template to use.

        Args:
            project_id: Project UUID
            prompt_type: Type of prompt (analysis, translation, etc.)

        Returns:
            PromptTemplate configured for the project
        """
        config = cls.load_project_config(project_id)

        # Determine template name from config
        # Priority: project config > global defaults.json > "default"
        template_name = cls.get_default_template(prompt_type)  # Use global default
        if config and "prompts" in config:
            prompt_config = config["prompts"].get(prompt_type, {})
            # Only override if project has explicit config
            if "system_template" in prompt_config:
                template_name = prompt_config["system_template"]

        return cls.load_template(
            prompt_type,
            template_name=template_name,
            project_id=project_id
        )

    @classmethod
    def extract_variables(cls, template: str) -> list[str]:
        """Extract variable names from a template.

        Handles all variable patterns:
        - Simple: {{var}} or {{namespace.var}}
        - Fallback: {{var | default:"value"}}
        - Typed: {{var:type}}
        - Conditionals: {{#if var}}, {{#if var1 && var2}}, {{#if var1 || var2}}
        - Loops: {{#each var}}

        Args:
            template: Template string

        Returns:
            List of unique variable names
        """
        all_vars: set[str] = set()

        # 1. Find all simple variables: {{var}}
        simple_vars = cls.VARIABLE_PATTERN.findall(template)
        all_vars.update(simple_vars)

        # 2. Find variables in fallback patterns: {{var | default:"value"}}
        fallback_vars = cls.FALLBACK_PATTERN.findall(template)
        all_vars.update(v[0] for v in fallback_vars)

        # 3. Find variables in typed patterns: {{var:type}}
        typed_vars = cls.TYPED_VAR_PATTERN.findall(template)
        all_vars.update(v[0] for v in typed_vars)

        # 4. Find variables in simple conditionals: {{#if var}}
        if_vars = cls.IF_PATTERN.findall(template)
        all_vars.update(v[0] for v in if_vars)

        # 5. Find variables in AND conditionals: {{#if var1 && var2}}
        if_and_matches = cls.IF_AND_PATTERN.findall(template)
        for match in if_and_matches:
            condition_str = match[0] if isinstance(match, tuple) else match
            conditions = [c.strip() for c in condition_str.split("&&")]
            all_vars.update(conditions)

        # 6. Find variables in OR conditionals: {{#if var1 || var2}}
        if_or_matches = cls.IF_OR_PATTERN.findall(template)
        for match in if_or_matches:
            condition_str = match[0] if isinstance(match, tuple) else match
            conditions = [c.strip() for c in condition_str.split("||")]
            all_vars.update(conditions)

        # 7. Find variables in each blocks: {{#each var}}
        each_vars = cls.EACH_PATTERN.findall(template)
        all_vars.update(v[0] for v in each_vars)

        # Filter out special variables like @key, @index, this
        all_vars = {v for v in all_vars if not v.startswith("@") and v != "this"}

        return sorted(list(all_vars))

    # Maximum depth for macro expansion to prevent infinite recursion
    MAX_MACRO_DEPTH = 10

    @classmethod
    def render(
        cls,
        template: str,
        variables: dict[str, Any],
        macros: Optional[Dict[str, str]] = None,
        _macro_depth: int = 0
    ) -> str:
        """Render a template with variables.

        Supports:
        - Simple variables: {{var}} or {{namespace.var}}
        - Fallback values: {{var | default:"fallback"}}
        - Macros: {{@macro_name}}
        - Conditionals: {{#if var}}...{{/if}}
        - AND conditions: {{#if var1 && var2}}...{{/if}}
        - OR conditions: {{#if var1 || var2}}...{{/if}}
        - Loops: {{#each var}}...{{/each}}
        - Type formatting: {{var:table}}, {{var:list}}, {{var:terminology}}
        - Variable aliases for backward compatibility

        Args:
            template: Template string
            variables: Dictionary of variable values
            macros: Optional dictionary of macro definitions
            _macro_depth: Internal counter for recursion depth (do not set manually)

        Returns:
            Rendered template string

        Raises:
            ValueError: If macro expansion exceeds maximum depth
        """
        result = template
        macros = macros or {}

        # Step 1: Expand macros first {{@macro_name}}
        result = cls._process_macros(result, macros, variables, _macro_depth)

        # Step 2: Process {{#each}} blocks (iterate until no more matches)
        max_iterations = 10
        for _ in range(max_iterations):
            new_result = cls._process_each_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # Step 3: Process {{#unless}} blocks (negative conditionals)
        for _ in range(max_iterations):
            new_result = cls._process_unless_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # Step 4: Process {{#if}} blocks with else first (more specific patterns)
        # AND with else
        for _ in range(max_iterations):
            new_result = cls._process_if_and_else_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # OR with else
        for _ in range(max_iterations):
            new_result = cls._process_if_or_else_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # Simple if with else
        for _ in range(max_iterations):
            new_result = cls._process_if_else_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # Step 5: Process {{#if}} blocks without else (AND/OR conditions)
        for _ in range(max_iterations):
            new_result = cls._process_if_and_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        for _ in range(max_iterations):
            new_result = cls._process_if_or_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # Step 6: Process simple {{#if}} blocks
        for _ in range(max_iterations):
            new_result = cls._process_if_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # Step 7: Process typed variables {{var:type}}
        result = cls._process_typed_variables(result, variables)

        # Step 8: Process fallback variables {{var | default:"value"}}
        result = cls._process_fallback_variables(result, variables)

        # Step 9: Replace simple variables with alias resolution
        def replace_var(match):
            var_name = match.group(1)
            value = cls._get_value_with_alias(variables, var_name)
            if value is None:
                return match.group(0)  # Keep original if not found
            return cls._format_value(value)

        result = cls.VARIABLE_PATTERN.sub(replace_var, result)

        # Step 8: Clean up empty lines
        result = cls._clean_empty_lines(result)

        return result.strip()

    @classmethod
    def _get_value_with_alias(cls, variables: dict, var_name: str) -> Any:
        """Get value with alias resolution.

        First tries the exact variable name, then checks aliases.

        Args:
            variables: Variable dictionary
            var_name: Variable name (may be an alias)

        Returns:
            Value if found, None otherwise
        """
        # Try direct lookup first
        value = cls._get_nested_value(variables, var_name)
        if value is not None:
            return value

        # Try alias resolution
        canonical = VARIABLE_ALIASES.get(var_name)
        if canonical:
            return cls._get_nested_value(variables, canonical)

        return None

    @classmethod
    def _process_macros(
        cls,
        template: str,
        macros: Dict[str, str],
        variables: dict,
        depth: int = 0
    ) -> str:
        """Process macro expansions {{@macro_name}}.

        Args:
            template: Template string
            macros: Dictionary of macro name to template
            variables: Variables for macro expansion
            depth: Current recursion depth

        Returns:
            Template with macros expanded

        Raises:
            ValueError: If recursion depth exceeds MAX_MACRO_DEPTH
        """
        if depth >= cls.MAX_MACRO_DEPTH:
            raise ValueError(
                f"Macro expansion exceeded maximum depth ({cls.MAX_MACRO_DEPTH}). "
                "This may indicate circular macro references."
            )

        def replace_macro(match: re.Match[str]) -> str:
            macro_name = match.group(1)
            if macro_name in macros:
                # Recursively render the macro template with incremented depth
                return cls.render(macros[macro_name], variables, macros, depth + 1)
            return match.group(0)  # Keep original if macro not found

        return cls.MACRO_PATTERN.sub(replace_macro, template)

    @classmethod
    def _process_fallback_variables(cls, template: str, variables: dict) -> str:
        """Process variables with fallback values.

        Pattern: {{var | default:"fallback value"}}

        Args:
            template: Template string
            variables: Variable dictionary

        Returns:
            Template with fallback variables resolved
        """
        def replace_fallback(match):
            var_name = match.group(1)
            default_value = match.group(2)

            value = cls._get_value_with_alias(variables, var_name)
            if value is not None and value != "":
                return cls._format_value(value)
            return default_value

        return cls.FALLBACK_PATTERN.sub(replace_fallback, template)

    @classmethod
    def _process_typed_variables(cls, template: str, variables: dict) -> str:
        """Process variables with type formatting hints.

        Pattern: {{var:type}} where type is table, list, terminology, etc.

        Args:
            template: Template string
            variables: Variable dictionary

        Returns:
            Template with typed variables formatted
        """
        def replace_typed(match):
            var_name = match.group(1)
            var_type = match.group(2)

            value = cls._get_value_with_alias(variables, var_name)
            if value is None:
                return match.group(0)

            return cls._format_value_by_type(value, var_type)

        return cls.TYPED_VAR_PATTERN.sub(replace_typed, template)

    @classmethod
    def _process_if_and_blocks(cls, template: str, variables: dict) -> str:
        """Process {{#if var1 && var2}} blocks.

        All conditions must be truthy for content to render.

        Args:
            template: Template string
            variables: Variable dictionary

        Returns:
            Template with AND conditional blocks processed
        """
        def replace_if_and(match):
            condition_str = match.group(1)
            content = match.group(2)

            # Split by && and check all conditions
            conditions = [c.strip() for c in condition_str.split("&&")]
            all_true = all(
                cls._get_value_with_alias(variables, cond)
                for cond in conditions
            )

            return content if all_true else ""

        return cls.IF_AND_PATTERN.sub(replace_if_and, template)

    @classmethod
    def _process_if_or_blocks(cls, template: str, variables: dict) -> str:
        """Process {{#if var1 || var2}} blocks.

        Any condition being truthy will render content.

        Args:
            template: Template string
            variables: Variable dictionary

        Returns:
            Template with OR conditional blocks processed
        """
        def replace_if_or(match):
            condition_str = match.group(1)
            content = match.group(2)

            # Split by || and check any condition
            conditions = [c.strip() for c in condition_str.split("||")]
            any_true = any(
                cls._get_value_with_alias(variables, cond)
                for cond in conditions
            )

            return content if any_true else ""

        return cls.IF_OR_PATTERN.sub(replace_if_or, template)

    @classmethod
    def _process_unless_blocks(cls, template: str, variables: dict) -> str:
        """Process {{#unless var}} blocks (negative conditionals).

        Renders content only when variable is falsy.

        Args:
            template: Template string
            variables: Variable dictionary

        Returns:
            Template with unless blocks processed
        """
        def replace_unless(match: re.Match[str]) -> str:
            var_name = match.group(1)
            content = match.group(2)

            value = cls._get_value_with_alias(variables, var_name)
            # Render content only if value is falsy
            return content if not value else ""

        return cls.UNLESS_PATTERN.sub(replace_unless, template)

    @classmethod
    def _process_if_else_blocks(cls, template: str, variables: dict) -> str:
        """Process {{#if var}}...{{#else}}...{{/if}} blocks.

        Args:
            template: Template string
            variables: Variable dictionary

        Returns:
            Template with if-else blocks processed
        """
        def replace_if_else(match: re.Match[str]) -> str:
            var_name = match.group(1)
            if_content = match.group(2)
            else_content = match.group(3)

            value = cls._get_value_with_alias(variables, var_name)
            return if_content if value else else_content

        return cls.IF_ELSE_PATTERN.sub(replace_if_else, template)

    @classmethod
    def _process_if_and_else_blocks(cls, template: str, variables: dict) -> str:
        """Process {{#if var1 && var2}}...{{#else}}...{{/if}} blocks.

        Args:
            template: Template string
            variables: Variable dictionary

        Returns:
            Template with AND conditional else blocks processed
        """
        def replace_if_and_else(match: re.Match[str]) -> str:
            condition_str = match.group(1)
            if_content = match.group(2)
            else_content = match.group(3)

            conditions = [c.strip() for c in condition_str.split("&&")]
            all_true = all(
                cls._get_value_with_alias(variables, cond)
                for cond in conditions
            )

            return if_content if all_true else else_content

        return cls.IF_AND_ELSE_PATTERN.sub(replace_if_and_else, template)

    @classmethod
    def _process_if_or_else_blocks(cls, template: str, variables: dict) -> str:
        """Process {{#if var1 || var2}}...{{#else}}...{{/if}} blocks.

        Args:
            template: Template string
            variables: Variable dictionary

        Returns:
            Template with OR conditional else blocks processed
        """
        def replace_if_or_else(match: re.Match[str]) -> str:
            condition_str = match.group(1)
            if_content = match.group(2)
            else_content = match.group(3)

            conditions = [c.strip() for c in condition_str.split("||")]
            any_true = any(
                cls._get_value_with_alias(variables, cond)
                for cond in conditions
            )

            return if_content if any_true else else_content

        return cls.IF_OR_ELSE_PATTERN.sub(replace_if_or_else, template)

    @classmethod
    def _format_value(cls, value: Any) -> str:
        """Format a value for template output.

        Args:
            value: Value to format

        Returns:
            String representation
        """
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)

    @classmethod
    def _format_value_by_type(cls, value: Any, var_type: str) -> str:
        """Format value according to specified type.

        Supported types:
        - table: Format dict/list as markdown table
        - list: Format as bullet list
        - terminology: Format as term: translation list
        - json: Format as JSON
        - inline: Format list as comma-separated inline

        Args:
            value: Value to format
            var_type: Type hint

        Returns:
            Formatted string
        """
        if var_type == "table":
            return cls._format_as_table(value)
        elif var_type == "list":
            return cls._format_as_list(value)
        elif var_type == "terminology":
            return cls._format_as_terminology(value)
        elif var_type == "json":
            return json.dumps(value, ensure_ascii=False, indent=2)
        elif var_type == "inline":
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return str(value)
        else:
            return cls._format_value(value)

    @classmethod
    def _format_as_table(cls, value: Any) -> str:
        """Format value as markdown table.

        Args:
            value: Dict or list of dicts

        Returns:
            Markdown table string
        """
        if isinstance(value, dict):
            # Simple key-value table
            lines = ["| Key | Value |", "| --- | --- |"]
            for k, v in value.items():
                lines.append(f"| {k} | {v} |")
            return "\n".join(lines)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # List of dicts - use first item's keys as headers
            headers = list(value[0].keys())
            lines = [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(["---"] * len(headers)) + " |"
            ]
            for item in value:
                row = [str(item.get(h, "")) for h in headers]
                lines.append("| " + " | ".join(row) + " |")
            return "\n".join(lines)
        return str(value)

    @classmethod
    def _format_as_list(cls, value: Any) -> str:
        """Format value as bullet list.

        Args:
            value: List or dict

        Returns:
            Bullet list string
        """
        if isinstance(value, list):
            return "\n".join(f"- {item}" for item in value)
        elif isinstance(value, dict):
            return "\n".join(f"- {k}: {v}" for k, v in value.items())
        return f"- {value}"

    @classmethod
    def _format_as_terminology(cls, value: Any) -> str:
        """Format value as terminology list.

        Args:
            value: Dict of english -> chinese or list of term objects

        Returns:
            Terminology list string
        """
        # Placeholder values to filter out
        invalid_placeholders = {"undefined", "null", "n/a", "none", "tbd", ""}
        
        def is_valid(zh: Any) -> bool:
            return zh and str(zh).strip().lower() not in invalid_placeholders
        
        if isinstance(value, dict):
            return "\n".join(f"- {en}: {zh}" for en, zh in value.items() if is_valid(zh))
        elif isinstance(value, list):
            lines = []
            for term in value:
                if isinstance(term, dict):
                    en = term.get("english_term") or term.get("english", "")
                    zh = term.get("chinese_translation") or term.get("chinese", "")
                    if en and is_valid(zh):
                        lines.append(f"- {en}: {zh}")
                else:
                    lines.append(f"- {term}")
            return "\n".join(lines)
        return str(value)

    @classmethod
    def _clean_empty_lines(cls, text: str) -> str:
        """Clean up excessive empty lines.

        Args:
            text: Input text

        Returns:
            Text with at most one consecutive empty line
        """
        lines = text.split("\n")
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            is_empty = not line.strip()
            if is_empty and prev_empty:
                continue
            cleaned_lines.append(line)
            prev_empty = is_empty
        return "\n".join(cleaned_lines)

    @classmethod
    def _process_each_blocks(cls, template: str, variables: dict[str, Any]) -> str:
        """Process {{#each}} blocks in template.

        Supports alias resolution for variable names.
        """
        def replace_each(match):
            var_name = match.group(1)
            content = match.group(2)

            value = cls._get_value_with_alias(variables, var_name)
            if not value:
                return ""

            if isinstance(value, dict):
                # For dict, iterate over key-value pairs
                output = []
                for key, val in value.items():
                    item_content = content
                    item_content = item_content.replace("{{@key}}", str(key))
                    item_content = item_content.replace("{{this}}", str(val))
                    output.append(item_content)
                return "".join(output)
            elif isinstance(value, list):
                # For list, iterate over items
                output = []
                for idx, item in enumerate(value):
                    item_content = content
                    item_content = item_content.replace("{{this}}", str(item))
                    item_content = item_content.replace("{{@index}}", str(idx))
                    output.append(item_content)
                return "".join(output)
            return ""

        return cls.EACH_PATTERN.sub(replace_each, template)

    @classmethod
    def _process_if_blocks(cls, template: str, variables: dict[str, Any]) -> str:
        """Process {{#if}} blocks in template.

        Uses a non-greedy approach to find innermost blocks first.
        Supports alias resolution for variable names.
        """
        # Find blocks that don't contain nested {{#if}} tags
        # This pattern matches {{#if var}}content{{/if}} where content has no {{#if}}
        inner_if_pattern = re.compile(
            r"\{\{#if\s+(\w+(?:\.\w+)*)\}\}((?:(?!\{\{#if).)*?)\{\{/if\}\}",
            re.DOTALL
        )

        def replace_if(match):
            var_name = match.group(1)
            content = match.group(2)

            value = cls._get_value_with_alias(variables, var_name)
            if value:
                return content
            return ""

        return inner_if_pattern.sub(replace_if, template)

    @classmethod
    def _get_nested_value(cls, data: dict, key: str) -> Any:
        """Get a value from a dictionary using dot notation.

        Supports both flat keys (e.g., data["project.author"]) and
        nested structures (e.g., data["project"]["author"]).

        Args:
            data: Dictionary to search (can be flat or nested)
            key: Key with optional dot notation (e.g., "project.author")

        Returns:
            Value if found, None otherwise
        """
        # First try direct/flat lookup (for to_flat_dict() output)
        if key in data:
            return data[key]

        # Then try nested lookup (for to_nested_dict() output)
        keys = key.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value

    @classmethod
    def save_template(
        cls,
        prompt_type: str,
        system_prompt: str,
        template_name: str = "default"
    ) -> PromptTemplate:
        """Save a system prompt template to file.

        Only saves the system prompt file (system.{template_name}.md).
        User prompt templates are shared per category (user.default.md).

        Args:
            prompt_type: Type of prompt (analysis, translation, etc.)
            system_prompt: System prompt content
            template_name: Template name (e.g., 'reformed-theology')

        Returns:
            Updated PromptTemplate
        """
        if prompt_type not in cls.VALID_TYPES:
            raise ValueError(f"Invalid prompt type: {prompt_type}")

        system_path = cls.get_prompt_path(prompt_type, "system", template_name)

        # Ensure directory exists
        system_path.parent.mkdir(parents=True, exist_ok=True)

        # Only save system prompt file
        system_path.write_text(system_prompt, encoding="utf-8")
        logger.info(f"Saved system prompt to: {system_path}")

        return cls.load_template(prompt_type, template_name=template_name)

    @classmethod
    def delete_template(
        cls,
        prompt_type: str,
        template_name: str
    ) -> bool:
        """Delete a system prompt template file.

        Only deletes the system prompt file (system.{template_name}.md).
        User prompt templates (user.default.md) are shared and never deleted.

        Args:
            prompt_type: Type of prompt
            template_name: Template name (e.g., 'reformed-theology')

        Returns:
            True if file was deleted, False if not found

        Raises:
            ValueError: If trying to delete 'default' template
        """
        if template_name == "default":
            raise ValueError("Cannot delete default template files")

        if prompt_type not in cls.VALID_TYPES:
            raise ValueError(f"Invalid prompt type: {prompt_type}")

        system_path = cls.get_prompt_path(prompt_type, "system", template_name)

        if system_path.exists():
            system_path.unlink()
            logger.info(f"Deleted template file: {system_path}")
            return True

        return False

    @classmethod
    def rename_template(
        cls,
        prompt_type: str,
        old_name: str,
        new_name: str
    ) -> bool:
        """Rename a template by renaming its files.

        Args:
            prompt_type: Type of prompt (analysis, translation, etc.)
            old_name: Current template name
            new_name: New template name

        Returns:
            True if renamed successfully

        Raises:
            ValueError: If invalid names or template doesn't exist
        """
        if old_name == "default":
            raise ValueError("Cannot rename default template")

        if new_name == "default":
            raise ValueError("Cannot rename to 'default'")

        if prompt_type not in cls.VALID_TYPES:
            raise ValueError(f"Invalid prompt type: {prompt_type}")

        # Validate new name format
        import re
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', new_name):
            raise ValueError(
                "Template name must be lowercase letters, numbers, and hyphens only"
            )

        # Check if new name already exists
        existing = cls.list_available_templates(prompt_type)
        if new_name in existing:
            raise ValueError(f"Template '{new_name}' already exists")

        if old_name not in existing:
            raise ValueError(f"Template '{old_name}' not found")

        # Rename the system prompt file
        old_path = cls.get_prompt_path(prompt_type, "system", old_name)
        new_path = cls.get_prompt_path(prompt_type, "system", new_name)

        if old_path.exists():
            old_path.rename(new_path)
            logger.info(f"Renamed template: {old_path} -> {new_path}")
            return True

        return False

    @classmethod
    def save_project_user_prompt(
        cls,
        project_id: str,
        prompt_type: str,
        user_prompt: str
    ) -> None:
        """Save a user prompt to a project folder.

        Args:
            project_id: Project UUID
            prompt_type: Type of prompt
            user_prompt: User prompt content
        """
        if prompt_type not in cls.VALID_TYPES:
            raise ValueError(f"Invalid prompt type: {prompt_type}")

        user_path = cls.get_project_prompt_path(project_id, prompt_type, "user")

        # Ensure directory exists
        user_path.parent.mkdir(parents=True, exist_ok=True)

        user_path.write_text(user_prompt, encoding="utf-8")

    @classmethod
    def delete_project_user_prompt(
        cls,
        project_id: str,
        prompt_type: str
    ) -> bool:
        """Delete a project's custom user prompt file.

        Args:
            project_id: Project UUID
            prompt_type: Type of prompt

        Returns:
            True if file was deleted, False if it didn't exist
        """
        if prompt_type not in cls.VALID_TYPES:
            raise ValueError(f"Invalid prompt type: {prompt_type}")

        user_path = cls.get_project_prompt_path(project_id, prompt_type, "user")

        if user_path.exists():
            user_path.unlink()
            return True
        return False

    @classmethod
    def preview(
        cls,
        prompt_type: str,
        variables: dict[str, Any],
        custom_user_prompt: Optional[str] = None,
        template_name: str = "default",
        project_id: Optional[str] = None,
    ) -> dict[str, str]:
        """Preview rendered prompts with variables.

        System prompts always come from global templates (not customizable per-project).
        User prompts can be customized per-project via files.

        Args:
            prompt_type: Type of prompt
            variables: Variable values for rendering
            custom_user_prompt: Optional custom user prompt for preview
            template_name: Template name (default, reformed-theology, etc.)
            project_id: Optional project ID for project-local user prompts

        Returns:
            Dict with rendered system_prompt and user_prompt
        """
        template = cls.load_template(
            prompt_type,
            template_name=template_name,
            project_id=project_id
        )

        # System prompt always from global template
        system_template = template.system_prompt
        # User prompt can be customized (for preview) or loaded from template
        user_template = custom_user_prompt or template.user_prompt_template

        return {
            "system_prompt": cls.render(system_template, variables),
            "user_prompt": cls.render(user_template, variables),
        }

    # Stage-specific variable availability mapping
    # Variables not listed here are assumed available in all stages
    # Note: content.sample_paragraphs is internal (auto-populated during analysis) and not listed here
    STAGE_VARIABLES: Dict[str, List[str]] = {
        "content.source": ["translation", "optimization", "proofreading"],
        "content.target": ["optimization", "proofreading"],
        "content.source_text": ["translation", "optimization"],
        "context.previous_source": ["translation"],
        "context.previous_target": ["translation"],
        "pipeline.reference_translation": ["translation"],
        "pipeline.suggested_changes": ["optimization"],
    }

    @classmethod
    def validate_template(
        cls,
        template: str,
        available_variables: dict[str, Any],
        stage: Optional[str] = None,
    ) -> TemplateValidationResult:
        """Validate a template against available variables.

        Args:
            template: Template string to validate
            available_variables: Dictionary of available variable values
            stage: Optional stage to validate against (analysis, translation, etc.)

        Returns:
            TemplateValidationResult with validation status and warnings
        """
        # Extract all variables from the template
        template_vars = cls.extract_variables(template)

        # Find missing variables
        missing = []
        warnings = []

        for var in template_vars:
            # Check stage availability first
            if stage and var in cls.STAGE_VARIABLES:
                if stage not in cls.STAGE_VARIABLES[var]:
                    warnings.append(
                        f"Variable '{var}' is not available in '{stage}' stage "
                        f"(available in: {', '.join(cls.STAGE_VARIABLES[var])})"
                    )
                    continue

            value = cls._get_nested_value(available_variables, var)
            if value is None:
                # Check alias resolution
                value = cls._get_value_with_alias(available_variables, var)

            if value is None:
                # Check if it's a conditional variable (used in {{#if}})
                if cls._is_conditional_only(template, var):
                    # Conditional variables are optional - just warn
                    warnings.append(
                        f"Conditional variable '{var}' is not defined - "
                        f"block will be skipped"
                    )
                else:
                    missing.append(var)

        # Check for empty critical variables
        critical_vars = ["source_text", "content.source_text", "content.source"]
        for var in critical_vars:
            value = cls._get_nested_value(available_variables, var)
            if var in template_vars and not value:
                warnings.append(f"Critical variable '{var}' is empty")

        is_valid = len(missing) == 0

        if missing:
            logger.warning(
                f"Template has {len(missing)} missing variable(s): {missing}"
            )
        if warnings:
            for warning in warnings:
                logger.debug(f"Template validation warning: {warning}")

        # Also check for syntax errors
        syntax_errors = cls.validate_syntax(template)

        # Include syntax errors in validity check
        is_valid = len(missing) == 0 and len(syntax_errors) == 0

        return TemplateValidationResult(
            is_valid=is_valid,
            missing_variables=missing,
            warnings=warnings,
            syntax_errors=syntax_errors,
        )

    @classmethod
    def validate_syntax(cls, template: str) -> list[TemplateSyntaxError]:
        """Validate template syntax for common errors.

        Checks for:
        - Unmatched {{ and }}
        - Unmatched {{#if}} and {{/if}}
        - Unmatched {{#each}} and {{/each}}
        - Unmatched {{#unless}} and {{/unless}}
        - Invalid block nesting

        Args:
            template: Template string to validate

        Returns:
            List of TemplateSyntaxError objects (empty if no errors)
        """
        errors: list[TemplateSyntaxError] = []

        def get_line_col(text: str, pos: int) -> tuple[int, int]:
            """Get line and column number for a position in text."""
            lines = text[:pos].split('\n')
            return len(lines), len(lines[-1]) + 1 if lines else 1

        def get_context(text: str, pos: int, length: int = 40) -> str:
            """Get context snippet around a position."""
            start = max(0, pos - 20)
            end = min(len(text), pos + length)
            snippet = text[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
            return snippet.replace('\n', '\\n')

        # Check for unmatched braces
        open_count = template.count('{{')
        close_count = template.count('}}')
        if open_count != close_count:
            errors.append(TemplateSyntaxError(
                message=f"Unmatched braces: {open_count} '{{{{' but {close_count} '}}}}'",
            ))

        # Check for matching block pairs
        block_pairs = [
            (r'\{\{#if\s+', r'\{\{/if\}\}', 'if'),
            (r'\{\{#each\s+', r'\{\{/each\}\}', 'each'),
            (r'\{\{#unless\s+', r'\{\{/unless\}\}', 'unless'),
        ]

        for open_pattern, close_pattern, block_name in block_pairs:
            opens = list(re.finditer(open_pattern, template))
            closes = list(re.finditer(close_pattern, template))

            if len(opens) != len(closes):
                errors.append(TemplateSyntaxError(
                    message=f"Unmatched {{{{#{block_name}}}}}: {len(opens)} opening, {len(closes)} closing",
                ))

        # Check for proper nesting using a stack-based approach
        # Find all block starts and ends
        block_pattern = re.compile(
            r'\{\{(#if|#each|#unless|/if|/each|/unless)\b[^}]*\}\}'
        )

        stack: list[tuple[str, int, re.Match[str]]] = []
        for match in block_pattern.finditer(template):
            tag = match.group(1)
            pos = match.start()

            if tag.startswith('#'):
                # Opening tag
                block_type = tag[1:]  # Remove #
                stack.append((block_type, pos, match))
            else:
                # Closing tag
                block_type = tag[1:]  # Remove /
                if not stack:
                    line, col = get_line_col(template, pos)
                    errors.append(TemplateSyntaxError(
                        message=f"Unexpected {{{{/{block_type}}}}} with no matching opening tag",
                        line=line,
                        column=col,
                        context=get_context(template, pos),
                    ))
                elif stack[-1][0] != block_type:
                    line, col = get_line_col(template, pos)
                    expected = stack[-1][0]
                    errors.append(TemplateSyntaxError(
                        message=f"Mismatched block: expected {{{{/{expected}}}}}, found {{{{/{block_type}}}}}",
                        line=line,
                        column=col,
                        context=get_context(template, pos),
                    ))
                else:
                    stack.pop()

        # Check for unclosed blocks
        for block_type, pos, match in stack:
            line, col = get_line_col(template, pos)
            errors.append(TemplateSyntaxError(
                message=f"Unclosed {{{{#{block_type}}}}} block",
                line=line,
                column=col,
                context=get_context(template, pos),
            ))

        # Check for {{#else}} outside of {{#if}} block (basic check)
        else_pattern = re.compile(r'\{\{#else\}\}')
        if_block_pattern = re.compile(r'\{\{#if\s+.*?\}\}.*?\{\{/if\}\}', re.DOTALL)

        # Find all else tags
        else_matches = list(else_pattern.finditer(template))
        # Find content of all if blocks
        if_blocks = list(if_block_pattern.finditer(template))

        for else_match in else_matches:
            else_pos = else_match.start()
            in_if_block = False
            for if_block in if_blocks:
                if if_block.start() < else_pos < if_block.end():
                    in_if_block = True
                    break
            if not in_if_block:
                line, col = get_line_col(template, else_pos)
                errors.append(TemplateSyntaxError(
                    message="{{#else}} found outside of {{#if}} block",
                    line=line,
                    column=col,
                    context=get_context(template, else_pos),
                ))

        return errors

    @classmethod
    def _is_conditional_only(cls, template: str, var_name: str) -> bool:
        """Check if a variable is only used in conditional blocks.

        A variable is NOT conditional-only if it appears in:
        - Simple variable: {{var}}
        - Fallback: {{var | default:"value"}}
        - Typed: {{var:type}}
        - Each loop: {{#each var}}

        Args:
            template: Template string
            var_name: Variable name to check

        Returns:
            True if variable is only used in {{#if}} conditions
        """
        escaped_name = re.escape(var_name)

        # Pattern for direct variable usage: {{var_name}} (not followed by | or :)
        direct_pattern = re.compile(
            r"\{\{" + escaped_name + r"\}\}"
        )
        if direct_pattern.search(template):
            return False

        # Pattern for fallback usage: {{var | default:"value"}}
        fallback_pattern = re.compile(
            r"\{\{" + escaped_name + r"\s*\|"
        )
        if fallback_pattern.search(template):
            return False

        # Pattern for typed usage: {{var:type}}
        typed_pattern = re.compile(
            r"\{\{" + escaped_name + r":\w+\}\}"
        )
        if typed_pattern.search(template):
            return False

        # Pattern for each loop: {{#each var}}
        each_pattern = re.compile(
            r"\{\{#each\s+" + escaped_name + r"\}\}"
        )
        if each_pattern.search(template):
            return False

        # Check if used in any conditional form
        # Simple: {{#if var}}
        if_simple = re.compile(r"\{\{#if\s+" + escaped_name + r"\}\}")
        # AND: {{#if var && ...}} or {{#if ... && var}}
        if_and = re.compile(r"\{\{#if\s+[^}]*\b" + escaped_name + r"\b[^}]*&&|\{\{#if\s+[^}]*&&[^}]*\b" + escaped_name + r"\b")
        # OR: {{#if var || ...}} or {{#if ... || var}}
        if_or = re.compile(r"\{\{#if\s+[^}]*\b" + escaped_name + r"\b[^}]*\|\||\{\{#if\s+[^}]*\|\|[^}]*\b" + escaped_name + r"\b")

        return bool(if_simple.search(template) or if_and.search(template) or if_or.search(template))

    @classmethod
    def render_with_validation(
        cls,
        template: str,
        variables: dict[str, Any],
        strict: bool = False,
    ) -> tuple[str, TemplateValidationResult]:
        """Render template with validation.

        Args:
            template: Template string
            variables: Variable values
            strict: If True, raise error for missing variables

        Returns:
            Tuple of (rendered_template, validation_result)

        Raises:
            ValueError: If strict=True and validation fails
        """
        validation = cls.validate_template(template, variables)

        if strict and not validation.is_valid:
            raise ValueError(
                f"Template validation failed. Missing variables: "
                f"{validation.missing_variables}"
            )

        rendered = cls.render(template, variables)
        return rendered, validation

    @classmethod
    def get_undefined_variables(
        cls,
        template: str,
        variables: dict[str, Any],
    ) -> list[str]:
        """Get list of undefined variables in a template.

        Args:
            template: Template string
            variables: Available variable values

        Returns:
            List of variable names that are used but not defined
        """
        validation = cls.validate_template(template, variables)
        return validation.missing_variables

    # =========================================================================
    # Default Template Management
    # =========================================================================

    @classmethod
    def get_defaults(cls) -> Dict[str, str]:
        """Load default template configuration from defaults.json.

        Returns:
            Dict mapping category to default template name
        """
        defaults_path = cls.PROMPTS_DIR / "defaults.json"
        if not defaults_path.exists():
            # Return standard defaults if file doesn't exist
            return {t: "default" for t in cls.VALID_TYPES}

        try:
            with open(defaults_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load defaults.json: {e}")
            return {t: "default" for t in cls.VALID_TYPES}

    @classmethod
    def get_default_template(cls, category: str) -> str:
        """Get the default template name for a category.

        Args:
            category: Prompt category (analysis, translation, etc.)

        Returns:
            Template name (e.g., 'default', 'reformed-theology')
        """
        defaults = cls.get_defaults()
        return defaults.get(category, "default")

    @classmethod
    def set_default_template(cls, category: str, template_name: str) -> None:
        """Set the default template for a category.

        Args:
            category: Prompt category (analysis, translation, etc.)
            template_name: Template name to set as default

        Raises:
            ValueError: If category is invalid or template doesn't exist
        """
        if category not in cls.VALID_TYPES:
            raise ValueError(f"Invalid category: {category}. "
                           f"Valid categories: {cls.VALID_TYPES}")

        # Verify template exists
        available = cls.list_available_templates(category)
        if template_name not in available:
            raise ValueError(f"Template '{template_name}' not found for category '{category}'. "
                           f"Available: {available}")

        # Load current defaults
        defaults = cls.get_defaults()

        # Update the category
        defaults[category] = template_name

        # Save back
        defaults_path = cls.PROMPTS_DIR / "defaults.json"
        with open(defaults_path, "w", encoding="utf-8") as f:
            json.dump(defaults, f, ensure_ascii=False, indent=2)

        logger.info(f"Set default template for {category} to {template_name}")

    # =========================================================================
    # Template Metadata (Display Names)
    # =========================================================================

    @classmethod
    def _get_metadata_path(cls) -> Path:
        """Get the path to the template metadata file."""
        return cls.PROMPTS_DIR / "metadata.json"

    @classmethod
    def get_template_metadata(cls) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Load template metadata from metadata.json.

        Returns:
            Dict mapping category -> template_name -> metadata
            Example: {"translation": {"reformed-theology": {"display_name": "My Custom Name"}}}
        """
        metadata_path = cls._get_metadata_path()
        if not metadata_path.exists():
            return {}

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load template metadata: {e}")
            return {}

    @classmethod
    def _save_template_metadata(cls, metadata: Dict[str, Dict[str, Dict[str, str]]]) -> None:
        """Save template metadata to metadata.json."""
        metadata_path = cls._get_metadata_path()
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_display_name(cls, category: str, template_name: str) -> str:
        """Get the display name for a template.

        Returns custom display name if set, otherwise auto-generates from template_name.

        Args:
            category: Template category (e.g., 'translation')
            template_name: Template file name (e.g., 'reformed-theology')

        Returns:
            Display name (e.g., 'My Custom Name' or 'Reformed Theology')
        """
        metadata = cls.get_template_metadata()
        category_meta = metadata.get(category, {})
        template_meta = category_meta.get(template_name, {})

        if "display_name" in template_meta:
            return template_meta["display_name"]

        # Auto-generate from template name
        return template_name.replace("-", " ").title()

    @classmethod
    def set_display_name(cls, category: str, template_name: str, display_name: str) -> None:
        """Set a custom display name for a template.

        Args:
            category: Template category
            template_name: Template file name
            display_name: Custom display name to set
        """
        metadata = cls.get_template_metadata()

        if category not in metadata:
            metadata[category] = {}
        if template_name not in metadata[category]:
            metadata[category][template_name] = {}

        metadata[category][template_name]["display_name"] = display_name
        cls._save_template_metadata(metadata)
        logger.info(f"Set display name for {category}/{template_name} to '{display_name}'")

    @classmethod
    def rename_template_metadata(cls, category: str, old_name: str, new_name: str) -> None:
        """Update metadata when a template is renamed.

        Moves the metadata from old_name to new_name.
        """
        metadata = cls.get_template_metadata()
        category_meta = metadata.get(category, {})

        if old_name in category_meta:
            # Move metadata to new name
            metadata[category][new_name] = category_meta[old_name]
            del metadata[category][old_name]
            cls._save_template_metadata(metadata)
            logger.info(f"Renamed metadata for {category}/{old_name} to {new_name}")

    @classmethod
    def delete_template_metadata(cls, category: str, template_name: str) -> None:
        """Delete metadata for a template."""
        metadata = cls.get_template_metadata()
        category_meta = metadata.get(category, {})

        if template_name in category_meta:
            del metadata[category][template_name]
            cls._save_template_metadata(metadata)
            logger.info(f"Deleted metadata for {category}/{template_name}")

