"""Prompt template loader and renderer.

This module handles loading prompt templates from .md files and rendering
them with variable substitution.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel


class PromptTemplate(BaseModel):
    """Prompt template model."""

    type: str
    system_prompt: str
    user_prompt_template: str
    variables: list[str]
    last_modified: datetime


class PromptLoader:
    """Load and render prompt templates from .md files."""

    # Base directory for prompt templates
    PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"

    # Valid prompt types
    VALID_TYPES = ["analysis", "translation", "reasoning", "proofreading", "optimization"]

    # Variable pattern: {{variable_name}}
    VARIABLE_PATTERN = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")

    # Conditional block patterns: {{#if var}}...{{/if}}
    IF_PATTERN = re.compile(
        r"\{\{#if\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/if\}\}",
        re.DOTALL
    )

    # Each block patterns: {{#each var}}...{{/each}}
    EACH_PATTERN = re.compile(
        r"\{\{#each\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/each\}\}",
        re.DOTALL
    )

    @classmethod
    def get_prompt_path(cls, prompt_type: str, filename: str) -> Path:
        """Get the path to a prompt file.

        Args:
            prompt_type: Type of prompt (analysis, translation, etc.)
            filename: Name of the file (system.md or user.md)

        Returns:
            Path to the prompt file
        """
        return cls.PROMPTS_DIR / prompt_type / filename

    @classmethod
    def load_template(cls, prompt_type: str) -> PromptTemplate:
        """Load a prompt template from files.

        Args:
            prompt_type: Type of prompt to load

        Returns:
            PromptTemplate with system and user prompts

        Raises:
            ValueError: If prompt type is invalid
            FileNotFoundError: If prompt files don't exist
        """
        if prompt_type not in cls.VALID_TYPES:
            raise ValueError(f"Invalid prompt type: {prompt_type}. "
                           f"Valid types: {cls.VALID_TYPES}")

        system_path = cls.get_prompt_path(prompt_type, "system.md")
        user_path = cls.get_prompt_path(prompt_type, "user.md")

        if not system_path.exists():
            raise FileNotFoundError(f"System prompt not found: {system_path}")
        if not user_path.exists():
            raise FileNotFoundError(f"User prompt not found: {user_path}")

        system_prompt = system_path.read_text(encoding="utf-8")
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
        )

    @classmethod
    def extract_variables(cls, template: str) -> list[str]:
        """Extract variable names from a template.

        Args:
            template: Template string

        Returns:
            List of unique variable names
        """
        # Find all simple variables
        simple_vars = cls.VARIABLE_PATTERN.findall(template)

        # Find variables in conditional blocks
        if_vars = cls.IF_PATTERN.findall(template)
        if_var_names = [v[0] for v in if_vars]

        # Find variables in each blocks
        each_vars = cls.EACH_PATTERN.findall(template)
        each_var_names = [v[0] for v in each_vars]

        # Combine and deduplicate
        all_vars = set(simple_vars + if_var_names + each_var_names)

        # Filter out special variables like @key, this
        all_vars = {v for v in all_vars if not v.startswith("@") and v != "this"}

        return sorted(list(all_vars))

    @classmethod
    def render(cls, template: str, variables: dict[str, Any]) -> str:
        """Render a template with variables.

        Args:
            template: Template string
            variables: Dictionary of variable values

        Returns:
            Rendered template string
        """
        result = template

        # Process {{#each}} blocks first (iterate until no more matches)
        max_iterations = 10
        for _ in range(max_iterations):
            new_result = cls._process_each_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # Process {{#if}} blocks (iterate until no more matches)
        # Process innermost blocks first by iterating
        for _ in range(max_iterations):
            new_result = cls._process_if_blocks(result, variables)
            if new_result == result:
                break
            result = new_result

        # Replace simple variables
        def replace_var(match):
            var_name = match.group(1)
            value = cls._get_nested_value(variables, var_name)
            if value is None:
                return match.group(0)  # Keep original if not found
            return str(value)

        result = cls.VARIABLE_PATTERN.sub(replace_var, result)

        # Clean up empty lines
        lines = result.split("\n")
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            is_empty = not line.strip()
            if is_empty and prev_empty:
                continue
            cleaned_lines.append(line)
            prev_empty = is_empty

        return "\n".join(cleaned_lines).strip()

    @classmethod
    def _process_each_blocks(cls, template: str, variables: dict[str, Any]) -> str:
        """Process {{#each}} blocks in template."""
        def replace_each(match):
            var_name = match.group(1)
            content = match.group(2)

            value = cls._get_nested_value(variables, var_name)
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
                for item in value:
                    item_content = content.replace("{{this}}", str(item))
                    output.append(item_content)
                return "".join(output)
            return ""

        return cls.EACH_PATTERN.sub(replace_each, template)

    @classmethod
    def _process_if_blocks(cls, template: str, variables: dict[str, Any]) -> str:
        """Process {{#if}} blocks in template.

        Uses a non-greedy approach to find innermost blocks first.
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

            value = cls._get_nested_value(variables, var_name)
            if value:
                return content
            return ""

        return inner_if_pattern.sub(replace_if, template)

    @classmethod
    def _get_nested_value(cls, data: dict, key: str) -> Any:
        """Get a nested value from a dictionary using dot notation.

        Args:
            data: Dictionary to search
            key: Key with optional dot notation (e.g., "analysis.writing_style")

        Returns:
            Value if found, None otherwise
        """
        keys = key.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value

    @classmethod
    def save_template(cls, prompt_type: str, system_prompt: str, user_prompt: str) -> PromptTemplate:
        """Save a prompt template to files.

        Args:
            prompt_type: Type of prompt
            system_prompt: System prompt content
            user_prompt: User prompt content

        Returns:
            Updated PromptTemplate
        """
        if prompt_type not in cls.VALID_TYPES:
            raise ValueError(f"Invalid prompt type: {prompt_type}")

        system_path = cls.get_prompt_path(prompt_type, "system.md")
        user_path = cls.get_prompt_path(prompt_type, "user.md")

        # Ensure directory exists
        system_path.parent.mkdir(parents=True, exist_ok=True)

        system_path.write_text(system_prompt, encoding="utf-8")
        user_path.write_text(user_prompt, encoding="utf-8")

        return cls.load_template(prompt_type)

    @classmethod
    def preview(
        cls,
        prompt_type: str,
        variables: dict[str, Any],
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
    ) -> dict[str, str]:
        """Preview rendered prompts with variables.

        Args:
            prompt_type: Type of prompt
            variables: Variable values for rendering
            custom_system_prompt: Optional custom system prompt
            custom_user_prompt: Optional custom user prompt

        Returns:
            Dict with rendered system_prompt and user_prompt
        """
        template = cls.load_template(prompt_type)

        system_template = custom_system_prompt or template.system_prompt
        user_template = custom_user_prompt or template.user_prompt_template

        return {
            "system_prompt": cls.render(system_template, variables),
            "user_prompt": cls.render(user_template, variables),
        }
