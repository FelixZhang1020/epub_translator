"""Prompt management API routes."""

import uuid
from typing import Any, Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts.loader import (
    PromptLoader,
    PromptTemplate as FilePromptTemplate,
)
from app.core.prompts.variables import VariableService, StageType
from app.core.prompts.output_schemas import (
    ANALYSIS_OUTPUT_SCHEMA,
    PROOFREADING_OUTPUT_SCHEMA,
    DERIVED_MAPPING_DISPLAY,
)
from app.api.dependencies import ValidatedProject
from app.models.database import (
    get_db,
    ProjectPromptConfig,
    PromptCategory,
    BookAnalysis,
)
from app.utils.text import safe_truncate

router = APIRouter()


# ============================================================================
# Pydantic Models
# ============================================================================

class UpdatePromptRequest(BaseModel):
    """Request model for updating prompts (legacy, system prompt only)."""
    system_prompt: str


class PreviewPromptRequest(BaseModel):
    """Request model for previewing prompts.

    Both system and user prompts can be customized for preview purposes.
    """
    variables: dict[str, Any]
    custom_system_prompt: Optional[str] = None  # Custom system prompt for preview
    custom_user_prompt: Optional[str] = None  # Custom user prompt for preview


class PreviewPromptResponse(BaseModel):
    """Response model for prompt preview."""
    system_prompt: str
    user_prompt: str
    validation: Optional[dict] = None


class ValidateTemplateRequest(BaseModel):
    """Request model for validating a template."""
    template: str
    variables: dict[str, Any]


class ValidateTemplateResponse(BaseModel):
    """Response model for template validation."""
    is_valid: bool
    missing_variables: List[str]
    warnings: List[str]


class TemplateCreateRequest(BaseModel):
    """Create a new prompt template."""
    name: str
    description: Optional[str] = None
    category: str
    template_name: str  # User-provided filename (e.g., 'reformed-theology')
    system_prompt: str  # Content to save to file
    is_default: bool = False


class TemplateUpdateRequest(BaseModel):
    """Update an existing prompt template."""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None  # If provided, saves to file
    display_name: Optional[str] = None  # Custom display name (stored in metadata.json)
    is_default: Optional[bool] = None


class TemplateResponse(BaseModel):
    """Response model for prompt template (filesystem-based)."""
    category: str
    template_name: str  # e.g., 'default', 'reformed-theology'
    display_name: str  # e.g., 'Default', 'Reformed Theology'
    system_prompt: str  # Loaded from file
    user_prompt: str  # Loaded from file
    variables: List[str]  # Extracted from template
    last_modified: str


class ProjectConfigRequest(BaseModel):
    """Create or update project-specific prompt config.

    System prompts always come from global templates.
    User prompts can be customized per-project via files.
    """
    template_name: str = "default"  # Global template name (e.g., 'default', 'reformed-theology')
    custom_user_prompt: Optional[str] = None  # If provided, saves to project file


class ProjectConfigResponse(BaseModel):
    """Response model for project prompt config.

    Following 'only metadata in database' principle:
    - System prompts: Always from global templates
    - User prompts: From project files or global templates
    """
    id: str
    project_id: str
    category: str
    template_name: str  # Global template name
    has_custom_user_prompt: bool  # Whether project has custom user prompt file
    resolved_system_prompt: str  # Loaded from global template
    resolved_user_prompt: str  # Loaded from project file or global template


class ProjectVariablesRequest(BaseModel):
    """Request model for updating project variables (file-based)."""
    variables: dict[str, Any]  # Key-value pairs to save to variables.json


class ProjectVariablesResponse(BaseModel):
    """Response model for project variables (file-based)."""
    project_id: str
    variables: dict[str, Any]  # All variables from variables.json


# ============================================================================
# Parameter Review Models
# ============================================================================

class ParameterInfo(BaseModel):
    """Information about a single input parameter."""
    name: str                    # e.g., "project.title"
    namespace: str               # e.g., "project"
    short_name: str              # e.g., "title"
    value: Any                   # Current value
    value_preview: str           # Truncated preview (max 100 chars)
    is_effective: bool           # True if non-empty
    value_type: str              # "string", "list", "object", "boolean"
    description: Optional[str] = None
    stages: List[str]            # Which stages this is available in


class OutputFieldInfo(BaseModel):
    """Information about a single output field from LLM."""
    name: str                    # e.g., "writing_style"
    description: str             # What this field contains
    value_type: str              # "string", "list", "object", "boolean"
    current_value: Optional[Any] = None  # Actual value if populated
    is_populated: bool           # Whether this field has a value


class DerivedMapping(BaseModel):
    """Mapping from analysis output to derived variable."""
    source: str        # Source field in raw analysis
    target: str        # Target derived variable
    transform: str     # Transform function name (empty if none)
    used_in: List[str] # Which stages use this variable


class StageParameterReview(BaseModel):
    """Parameter review for a single stage."""
    stage: str                   # "analysis", "translation", etc.
    template_name: str           # Current template being used

    # Input parameters (what goes INTO the LLM call)
    input_parameters: List[ParameterInfo]
    input_effective_count: int
    input_total_count: int

    # Output parameters (what the LLM produces - for stages with structured output)
    output_fields: Optional[List[OutputFieldInfo]] = None  # None for plain-text stages
    output_populated_count: Optional[int] = None
    has_structured_output: bool  # True for analysis/proofreading

    # For analysis stage: show mapping to derived variables
    derived_mappings: Optional[List[DerivedMapping]] = None


class ParameterReviewResponse(BaseModel):
    """Complete parameter review across all stages."""
    project_id: str
    project_name: str
    analysis_completed: bool     # Whether analysis has run
    stages: List[StageParameterReview]
    summary: dict[str, int]      # overall stats


# ============================================================================
# Helper Functions
# ============================================================================

def _template_name_to_display(template_name: str, category: str = "") -> str:
    """Get display name for a template.

    If category is provided, checks for custom display name in metadata.
    Otherwise, auto-generates from template name.
    """
    if category:
        return PromptLoader.get_display_name(category, template_name)
    return template_name.replace("-", " ").title()


# ============================================================================
# Static Routes (must come BEFORE parameterized routes)
# ============================================================================

@router.get("/prompts")
async def list_prompt_types() -> dict[str, list[str]]:
    """List all available prompt types."""
    return {"types": PromptLoader.VALID_TYPES}


@router.get("/prompts/categories")
async def list_categories() -> List[str]:
    """List all available prompt categories."""
    return [c.value for c in PromptCategory]


@router.get("/prompts/file-templates/{category}")
async def list_file_templates(category: str) -> dict:
    """List available file-based templates for a category.

    Returns template names like 'default', 'reformed-theology', etc.
    """
    if category not in PromptLoader.VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {PromptLoader.VALID_TYPES}"
        )

    templates = PromptLoader.list_available_templates(category)
    return {
        "category": category,
        "templates": templates,
    }


@router.get("/prompts/file-templates/{category}/{template_name}")
async def get_file_template(
    category: str,
    template_name: str,
    project_id: Optional[str] = None,
) -> dict:
    """Get a specific file-based template.

    Args:
        category: Prompt category (analysis, translation, etc.)
        template_name: Template name (default, reformed-theology, etc.)
        project_id: Optional project ID to load project-local user prompts
    """
    try:
        template = PromptLoader.load_template(
            category,
            template_name=template_name,
            project_id=project_id
        )
        return {
            "type": template.type,
            "template_name": template.template_name,
            "system_prompt": template.system_prompt,
            "user_prompt": template.user_prompt_template,
            "variables": template.variables,
            "last_modified": template.last_modified.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/prompts/project-resolved/{project_id}/{category}")
async def get_project_resolved_prompts(
    project_id: str,
    category: str,
) -> dict:
    """Get resolved prompts for a project based on its config.json.

    This is the new file-based approach that reads from:
    - Project config.json to determine which template to use
    - Project-local user prompts if they exist
    - Global system prompts
    """
    try:
        template = PromptLoader.load_for_project(project_id, category)
        config = PromptLoader.load_project_config(project_id)

        # Get template name from config
        template_name = "default"
        has_project_user_prompt = False
        if config and "prompts" in config:
            prompt_config = config["prompts"].get(category, {})
            template_name = prompt_config.get("system_template", "default")
            # Check if project has custom user prompt
            user_path = prompt_config.get("user")
            if user_path:
                project_user_path = PromptLoader.get_project_prompt_path(
                    project_id, category, "user"
                )
                has_project_user_prompt = project_user_path.exists()

        return {
            "project_id": project_id,
            "category": category,
            "template_name": template_name,
            "has_project_user_prompt": has_project_user_prompt,
            "system_prompt": template.system_prompt,
            "user_prompt": template.user_prompt_template,
            "variables": template.variables,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))




@router.post("/prompts/validate")
async def validate_template(
    request: ValidateTemplateRequest,
) -> ValidateTemplateResponse:
    """Validate a template against provided variables.

    Checks for:
    - Missing variables (used in template but not provided)
    - Empty critical variables
    - Conditional variables that will be skipped

    Args:
        request: Template string and available variables

    Returns:
        Validation result with missing variables and warnings
    """
    result = PromptLoader.validate_template(request.template, request.variables)
    return ValidateTemplateResponse(
        is_valid=result.is_valid,
        missing_variables=result.missing_variables,
        warnings=result.warnings,
    )


# ============================================================================
# Template Routes (specific paths before parameterized)
# ============================================================================

@router.get("/prompts/templates")
async def list_templates(
    category: Optional[str] = None,
) -> List[TemplateResponse]:
    """List all prompt templates from filesystem, optionally filtered by category.

    Templates are read directly from backend/prompts/{category}/ directories.
    No database sync needed.
    """
    templates: List[TemplateResponse] = []

    # Determine which categories to scan
    categories = [category] if category else [c.value for c in PromptCategory]

    for cat in categories:
        if cat not in PromptLoader.VALID_TYPES:
            continue

        template_names = PromptLoader.list_available_templates(cat)
        for template_name in template_names:
            try:
                file_template = PromptLoader.load_template(cat, template_name=template_name)
                templates.append(TemplateResponse(
                    category=cat,
                    template_name=template_name,
                    display_name=_template_name_to_display(template_name, cat),
                    system_prompt=file_template.system_prompt,
                    user_prompt=file_template.user_prompt_template,
                    variables=file_template.variables,
                    last_modified=file_template.last_modified.isoformat(),
                ))
            except (ValueError, FileNotFoundError):
                pass

    return templates


@router.post("/prompts/templates")
async def create_template(
    request: TemplateCreateRequest,
) -> TemplateResponse:
    """Create a new prompt template.

    Creates the file-based template in backend/prompts/{category}/.
    """
    valid_categories = [c.value for c in PromptCategory]
    if request.category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )

    # Validate template_name format (lowercase, hyphens, no spaces)
    import re
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', request.template_name):
        raise HTTPException(
            status_code=400,
            detail="Template name must be lowercase letters, numbers, and hyphens only (e.g., 'my-template')"
        )

    if request.template_name == "default":
        raise HTTPException(
            status_code=400,
            detail="Cannot use 'default' as template name (reserved)"
        )

    # Check if template name already exists
    existing_templates = PromptLoader.list_available_templates(request.category)
    if request.template_name in existing_templates:
        raise HTTPException(
            status_code=400,
            detail=f"Template '{request.template_name}' already exists for {request.category}"
        )

    # Save system prompt to file
    file_template = PromptLoader.save_template(
        request.category,
        request.system_prompt,
        template_name=request.template_name
    )

    # Save custom display name if provided (name field)
    if request.name and request.name != _template_name_to_display(request.template_name):
        PromptLoader.set_display_name(request.category, request.template_name, request.name)

    return TemplateResponse(
        category=request.category,
        template_name=request.template_name,
        display_name=_template_name_to_display(request.template_name, request.category),
        system_prompt=file_template.system_prompt,
        user_prompt=file_template.user_prompt_template,
        variables=file_template.variables,
        last_modified=file_template.last_modified.isoformat(),
    )


@router.get("/prompts/templates/{category}/{template_name}")
async def get_template(
    category: str,
    template_name: str,
) -> TemplateResponse:
    """Get a specific prompt template by category and name."""
    if category not in PromptLoader.VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {PromptLoader.VALID_TYPES}"
        )

    try:
        file_template = PromptLoader.load_template(category, template_name=template_name)
        return TemplateResponse(
            category=category,
            template_name=template_name,
            display_name=_template_name_to_display(template_name, category),
            system_prompt=file_template.system_prompt,
            user_prompt=file_template.user_prompt_template,
            variables=file_template.variables,
            last_modified=file_template.last_modified.isoformat(),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")


@router.put("/prompts/templates/{category}/{template_name}")
async def update_template(
    category: str,
    template_name: str,
    request: TemplateUpdateRequest,
) -> TemplateResponse:
    """Update an existing prompt template.

    Updates the system prompt file content.
    """
    if category not in PromptLoader.VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {PromptLoader.VALID_TYPES}"
        )

    # Check template exists
    existing_templates = PromptLoader.list_available_templates(category)
    if template_name not in existing_templates:
        raise HTTPException(status_code=404, detail="Template not found")

    # If system_prompt provided, update file
    if request.system_prompt is not None:
        file_template = PromptLoader.save_template(
            category,
            request.system_prompt,
            template_name=template_name
        )
    else:
        file_template = PromptLoader.load_template(category, template_name=template_name)

    # If display_name provided, save to metadata
    if request.display_name is not None:
        PromptLoader.set_display_name(category, template_name, request.display_name)

    return TemplateResponse(
        category=category,
        template_name=template_name,
        display_name=_template_name_to_display(template_name, category),
        system_prompt=file_template.system_prompt,
        user_prompt=file_template.user_prompt_template,
        variables=file_template.variables,
        last_modified=file_template.last_modified.isoformat(),
    )


@router.delete("/prompts/templates/{category}/{template_name}")
async def delete_template(
    category: str,
    template_name: str,
):
    """Delete a prompt template.

    Deletes the template file from the filesystem.
    """
    if category not in PromptLoader.VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {PromptLoader.VALID_TYPES}"
        )

    if template_name == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default template")

    # Check template exists
    existing_templates = PromptLoader.list_available_templates(category)
    if template_name not in existing_templates:
        raise HTTPException(status_code=404, detail="Template not found")

    # Delete files
    try:
        files_deleted = PromptLoader.delete_template(category, template_name)
        # Also delete metadata (display name, etc.)
        PromptLoader.delete_template_metadata(category, template_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "Template deleted",
        "files_deleted": files_deleted
    }


class RenameTemplateRequest(BaseModel):
    """Request model for renaming a template."""
    new_name: str


@router.post("/prompts/templates/{category}/{template_name}/rename")
async def rename_template(
    category: str,
    template_name: str,
    request: RenameTemplateRequest,
) -> TemplateResponse:
    """Rename a prompt template.

    Renames the template file and returns the updated template info.
    """
    if category not in PromptLoader.VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {PromptLoader.VALID_TYPES}"
        )

    try:
        PromptLoader.rename_template(category, template_name, request.new_name)
        # Also rename metadata (preserve display name, etc.)
        PromptLoader.rename_template_metadata(category, template_name, request.new_name)

        # Load and return the renamed template
        file_template = PromptLoader.load_template(category, template_name=request.new_name)
        return TemplateResponse(
            category=category,
            template_name=request.new_name,
            display_name=_template_name_to_display(request.new_name, category),
            system_prompt=file_template.system_prompt,
            user_prompt=file_template.user_prompt_template,
            variables=file_template.variables,
            last_modified=file_template.last_modified.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================================
# Default Template Routes
# ============================================================================

class DefaultsResponse(BaseModel):
    """Response model for default templates."""
    defaults: dict[str, str]  # category -> template_name


class SetDefaultRequest(BaseModel):
    """Request model for setting default template."""
    template_name: str


@router.get("/prompts/defaults")
async def get_defaults() -> DefaultsResponse:
    """Get the default templates for all categories.

    Returns:
        Dict mapping category to default template name
    """
    defaults = PromptLoader.get_defaults()
    return DefaultsResponse(defaults=defaults)


@router.get("/prompts/defaults/{category}")
async def get_default_for_category(category: str) -> dict:
    """Get the default template for a specific category.

    Args:
        category: Prompt category (analysis, translation, etc.)

    Returns:
        Default template name for the category
    """
    if category not in PromptLoader.VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {PromptLoader.VALID_TYPES}"
        )

    template_name = PromptLoader.get_default_template(category)
    return {
        "category": category,
        "template_name": template_name,
    }


@router.put("/prompts/defaults/{category}")
async def set_default_for_category(
    category: str,
    request: SetDefaultRequest,
) -> dict:
    """Set the default template for a specific category.

    Args:
        category: Prompt category (analysis, translation, etc.)
        request: Template name to set as default

    Returns:
        Updated default template info
    """
    try:
        PromptLoader.set_default_template(category, request.template_name)
        return {
            "category": category,
            "template_name": request.template_name,
            "message": f"Default template for {category} set to {request.template_name}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Project Config Routes
# ============================================================================

@router.get("/prompts/projects/{project_id}")
async def list_project_configs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[ProjectConfigResponse]:
    """List all prompt configs for a project.

    System prompts always come from global templates.
    User prompts come from project files if they exist, otherwise global templates.

    Always returns all 4 categories. For categories without a database row,
    returns a default config.
    """
    result = await db.execute(
        select(ProjectPromptConfig)
        .where(ProjectPromptConfig.project_id == project_id)
        .order_by(ProjectPromptConfig.category)
    )
    configs = result.scalars().all()

    # Create a map of existing configs by category
    config_map = {config.category: config for config in configs}

    responses = []

    # Always return all categories
    for category in [c.value for c in PromptCategory]:
        config = config_map.get(category)

        if config:
            template_name = config.template_name or "default"
            config_id = config.id
        else:
            # No config exists - use defaults
            template_name = "default"
            config_id = ""

        # Check if project has custom user prompt FILE (filesystem is source of truth)
        project_user_path = PromptLoader.get_project_prompt_path(
            project_id, category, "user"
        )
        has_custom_user_prompt = project_user_path.exists()

        # Sync database flag if out of sync with filesystem
        if config and config.has_custom_user_prompt != has_custom_user_prompt:
            config.has_custom_user_prompt = has_custom_user_prompt
            await db.commit()

        # Load template from filesystem (system prompt always from global)
        try:
            template_content = PromptLoader.load_template(
                category,
                template_name=template_name,
                project_id=project_id  # This checks for project-local user prompts
            )
        except (ValueError, FileNotFoundError):
            template_content = None

        # System prompt: always from global template
        resolved_system = template_content.system_prompt if template_content else ""

        # User prompt: from project file (via load_template) or global template
        resolved_user = template_content.user_prompt_template if template_content else ""

        responses.append(ProjectConfigResponse(
            id=config_id,
            project_id=project_id,
            category=category,
            template_name=template_name,
            has_custom_user_prompt=has_custom_user_prompt,
            resolved_system_prompt=resolved_system,
            resolved_user_prompt=resolved_user,
        ))

    return responses


@router.get("/prompts/projects/{project_id}/available-variables")
async def get_available_variables(
    project_id: str,
    stage: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, List[dict[str, Any]]]:
    """Get all available variables for a project.

    This includes:
    - Project variables (title, author, etc.)
    - Content variables (source_text, paragraph_index, etc.)
    - Pipeline variables (existing_translation, reference_translation, etc.)
    - Derived variables (extracted from analysis)
    - User-defined variables (from variables.json)

    Args:
        project_id: Project ID
        stage: Optional stage filter (analysis, translation, optimization, proofreading)

    Returns:
        Dictionary with variable categories and their variables
    """
    from app.core.prompts.variables import VariableService, StageType

    # Cast stage string to StageType if provided
    stage_type: Optional[StageType] = None
    if stage and stage in ["analysis", "translation", "optimization", "proofreading"]:
        stage_type = stage  # type: ignore

    return await VariableService.get_available_variables(db, project_id, stage_type)


@router.get("/prompts/projects/{project_id}/parameter-review")
async def get_parameter_review(
    project: ValidatedProject,
    db: AsyncSession = Depends(get_db),
) -> ParameterReviewResponse:
    """Get comprehensive parameter review for all workflow stages.

    Returns:
        - Input parameters for each stage with effectiveness status
        - Output parameters for structured stages (analysis/proofreading)
        - Derived variable mappings showing how analysis output flows to other stages
    """
    project_id = project.id

    # Load analysis
    result = await db.execute(
        select(BookAnalysis).where(BookAnalysis.project_id == project_id)
    )
    analysis = result.scalar_one_or_none()
    analysis_completed = analysis is not None and analysis.raw_analysis is not None

    # Get project config to determine template names
    config = PromptLoader.load_project_config(project_id)

    # Build stage reviews
    stages: List[StageParameterReview] = []

    # Process each stage
    for stage_name in ["analysis", "translation", "optimization", "proofreading"]:
        stage_type: StageType = stage_name  # type: ignore

        # Get template name for this stage
        template_name = "default"
        if config and "prompts" in config:
            prompt_config = config["prompts"].get(stage_name, {})
            template_name = prompt_config.get("system_template", "default")

        # Get input parameters
        input_params: List[ParameterInfo] = []
        available_vars = await VariableService.get_available_variables(
            db, project_id, stage_type
        )

        # Convert available variables to ParameterInfo
        for namespace, vars_list in available_vars.items():
            if namespace == "macros":
                continue  # Skip macros for now

            for var_info in vars_list:
                value = var_info.get("current_value")
                is_effective = VariableService.is_value_effective(value)

                # Create value preview (truncate if too long)
                if value is None:
                    value_preview = "(empty)"
                elif isinstance(value, str):
                    value_preview = safe_truncate(value, 100) if len(value) > 100 else value
                elif isinstance(value, (list, dict)):
                    value_str = str(value)
                    value_preview = safe_truncate(value_str, 100) if len(value_str) > 100 else value_str
                else:
                    value_preview = str(value)

                # Determine value type
                value_type = var_info.get("type", "string")
                if value_type is None:
                    if isinstance(value, bool):
                        value_type = "boolean"
                    elif isinstance(value, (int, float)):
                        value_type = "number"
                    elif isinstance(value, list):
                        value_type = "list"
                    elif isinstance(value, dict):
                        value_type = "object"
                    else:
                        value_type = "string"

                # Extract short name from full name
                full_name = var_info.get("name", "")
                short_name = full_name.split(".")[-1] if "." in full_name else full_name

                input_params.append(ParameterInfo(
                    name=full_name,
                    namespace=namespace,
                    short_name=short_name,
                    value=value,
                    value_preview=value_preview,
                    is_effective=is_effective,
                    value_type=value_type,
                    description=var_info.get("description"),
                    stages=var_info.get("stages", [stage_name]),
                ))

        # Count effective input parameters
        input_effective_count = sum(1 for p in input_params if p.is_effective)
        input_total_count = len(input_params)

        # Get output fields for stages with structured output
        output_fields: Optional[List[OutputFieldInfo]] = None
        output_populated_count: Optional[int] = None
        has_structured_output = False
        derived_mappings: Optional[List[DerivedMapping]] = None

        if stage_name == "analysis":
            has_structured_output = True
            # Get schema for this template
            schema = ANALYSIS_OUTPUT_SCHEMA.get(template_name, ANALYSIS_OUTPUT_SCHEMA["default"])

            output_fields = []
            for field_schema in schema:
                field_name = field_schema["name"]
                # Get current value from analysis.raw_analysis
                current_value = None
                is_populated = False
                if analysis and analysis.raw_analysis:
                    # Navigate nested dict for field names like "translation_principles.priority_order"
                    parts = field_name.split(".")
                    value = analysis.raw_analysis
                    for part in parts:
                        if isinstance(value, dict) and part in value:
                            value = value[part]
                        else:
                            value = None
                            break
                    current_value = value
                    is_populated = VariableService.is_value_effective(value)

                output_fields.append(OutputFieldInfo(
                    name=field_name,
                    description=field_schema["description"],
                    value_type=field_schema["type"],
                    current_value=current_value,
                    is_populated=is_populated,
                ))

            output_populated_count = sum(1 for f in output_fields if f.is_populated)

            # Add derived mappings
            derived_mappings = [
                DerivedMapping(
                    source=m["source"],
                    target=m["target"],
                    transform=m["transform"],
                    used_in=m["used_in"],
                )
                for m in DERIVED_MAPPING_DISPLAY
            ]

        elif stage_name == "proofreading":
            has_structured_output = True
            output_fields = []
            for field_schema in PROOFREADING_OUTPUT_SCHEMA:
                # For proofreading, we don't show current values since they're per-paragraph
                output_fields.append(OutputFieldInfo(
                    name=field_schema["name"],
                    description=field_schema["description"],
                    value_type=field_schema["type"],
                    current_value=None,
                    is_populated=False,
                ))
            output_populated_count = 0

        stages.append(StageParameterReview(
            stage=stage_name,
            template_name=template_name,
            input_parameters=input_params,
            input_effective_count=input_effective_count,
            input_total_count=input_total_count,
            output_fields=output_fields,
            output_populated_count=output_populated_count,
            has_structured_output=has_structured_output,
            derived_mappings=derived_mappings,
        ))

    # Calculate summary stats
    total_input_effective = sum(s.input_effective_count for s in stages)
    total_input_count = sum(s.input_total_count for s in stages)

    return ParameterReviewResponse(
        project_id=project_id,
        project_name=project.name,
        analysis_completed=analysis_completed,
        stages=stages,
        summary={
            "total_input_effective": total_input_effective,
            "total_input_count": total_input_count,
        },
    )


@router.get("/prompts/projects/{project_id}/{category}")
async def get_project_config(
    project_id: str,
    category: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectConfigResponse:
    """Get prompt config for a specific project and category.

    System prompts always come from global templates.
    User prompts come from project files if they exist, otherwise global templates.
    """
    result = await db.execute(
        select(ProjectPromptConfig)
        .where(ProjectPromptConfig.project_id == project_id)
        .where(ProjectPromptConfig.category == category)
    )
    config = result.scalar_one_or_none()

    if not config:
        # No project config - use default template
        try:
            file_template = PromptLoader.load_template(category, project_id=project_id)
            return ProjectConfigResponse(
                id="",
                project_id=project_id,
                category=category,
                template_name="default",
                has_custom_user_prompt=False,
                resolved_system_prompt=file_template.system_prompt,
                resolved_user_prompt=file_template.user_prompt_template,
            )
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail=f"No template for category: {category}")

    # Load template from filesystem with project context
    template_name = config.template_name or "default"
    try:
        template_content = PromptLoader.load_template(
            category,
            template_name=template_name,
            project_id=project_id
        )
    except (ValueError, FileNotFoundError):
        # Fallback to default if specified template not found
        try:
            template_content = PromptLoader.load_template(category, project_id=project_id)
            template_name = "default"
        except (ValueError, FileNotFoundError):
            template_content = None

    # System prompt: always from global template
    resolved_system = template_content.system_prompt if template_content else ""

    # User prompt: from project file (via load_template) or global template
    resolved_user = template_content.user_prompt_template if template_content else ""

    return ProjectConfigResponse(
        id=config.id,
        project_id=config.project_id,
        category=config.category,
        template_name=template_name,
        has_custom_user_prompt=config.has_custom_user_prompt,
        resolved_system_prompt=resolved_system,
        resolved_user_prompt=resolved_user,
    )


@router.put("/prompts/projects/{project_id}/{category}")
async def update_project_config(
    project_id: str,
    category: str,
    request: ProjectConfigRequest,
    db: AsyncSession = Depends(get_db),
) -> ProjectConfigResponse:
    """Create or update prompt config for a project and category.

    System prompts always come from global templates (not customizable per-project).
    User prompts can be customized by saving to project files.
    """
    valid_categories = [c.value for c in PromptCategory]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )

    # Verify template exists in filesystem
    template_name = request.template_name or "default"
    existing_templates = PromptLoader.list_available_templates(category)
    if template_name not in existing_templates:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_name}' not found for {category}"
        )

    # First, check if config already exists to preserve existing flag
    result = await db.execute(
        select(ProjectPromptConfig)
        .where(ProjectPromptConfig.project_id == project_id)
        .where(ProjectPromptConfig.category == category)
    )
    config = result.scalar_one_or_none()

    # Determine has_custom_user_prompt flag:
    # - If new custom prompt is provided, save it and set flag to True
    # - Otherwise, preserve existing flag (or False if no config exists)
    if request.custom_user_prompt:
        PromptLoader.save_project_user_prompt(project_id, category, request.custom_user_prompt)
        has_custom_user_prompt = True
    else:
        # Preserve existing flag if config exists, otherwise False
        has_custom_user_prompt = config.has_custom_user_prompt if config else False

    if config:
        config.template_name = template_name
        config.has_custom_user_prompt = has_custom_user_prompt
    else:
        config = ProjectPromptConfig(
            id=str(uuid.uuid4()),
            project_id=project_id,
            category=category,
            template_name=template_name,
            has_custom_user_prompt=has_custom_user_prompt,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)

    # Load template with project context (includes project user prompt if exists)
    try:
        template_content = PromptLoader.load_template(
            category,
            template_name=template_name,
            project_id=project_id
        )
        resolved_system = template_content.system_prompt
        resolved_user = template_content.user_prompt_template
    except (ValueError, FileNotFoundError):
        resolved_system = ""
        resolved_user = ""

    return ProjectConfigResponse(
        id=config.id,
        project_id=config.project_id,
        category=config.category,
        template_name=config.template_name,
        has_custom_user_prompt=config.has_custom_user_prompt,
        resolved_system_prompt=resolved_system,
        resolved_user_prompt=resolved_user,
    )


@router.delete("/prompts/projects/{project_id}/{category}")
async def delete_project_config(
    project_id: str,
    category: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete prompt config for a project (revert to defaults)."""
    result = await db.execute(
        select(ProjectPromptConfig)
        .where(ProjectPromptConfig.project_id == project_id)
        .where(ProjectPromptConfig.category == category)
    )
    config = result.scalar_one_or_none()

    if config:
        await db.delete(config)
        await db.commit()

    return {"message": "Config deleted, reverted to defaults"}


@router.delete("/prompts/projects/{project_id}/{category}/user-prompt")
async def reset_project_user_prompt(
    project_id: str,
    category: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectConfigResponse:
    """Reset a project's custom user prompt to the default template.

    Deletes the project's custom user prompt file and updates the database flag.
    Returns the updated config with the default user prompt.
    """
    valid_categories = [c.value for c in PromptCategory]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )

    # Delete the project's custom user prompt file
    deleted = PromptLoader.delete_project_user_prompt(project_id, category)

    # Update database flag
    result = await db.execute(
        select(ProjectPromptConfig)
        .where(ProjectPromptConfig.project_id == project_id)
        .where(ProjectPromptConfig.category == category)
    )
    config = result.scalar_one_or_none()

    if config:
        config.has_custom_user_prompt = False
        await db.commit()
        await db.refresh(config)
        template_name = config.template_name or "default"
        config_id = config.id
    else:
        template_name = "default"
        config_id = ""

    # Load the default template
    try:
        template_content = PromptLoader.load_template(
            category,
            template_name=template_name,
            project_id=None  # Don't load project-local (we just deleted it)
        )
        resolved_system = template_content.system_prompt
        resolved_user = template_content.user_prompt_template
    except (ValueError, FileNotFoundError):
        resolved_system = ""
        resolved_user = ""

    return ProjectConfigResponse(
        id=config_id,
        project_id=project_id,
        category=category,
        template_name=template_name,
        has_custom_user_prompt=False,
        resolved_system_prompt=resolved_system,
        resolved_user_prompt=resolved_user,
    )


# ============================================================================
# Project Variables Routes (File-based)
# ============================================================================

@router.get("/prompts/projects/{project_id}/variables")
async def get_project_variables(
    project_id: str,
) -> ProjectVariablesResponse:
    """Get all variables for a project from variables.json file.

    Variables are stored in: projects/{project_id}/variables.json
    """
    variables = PromptLoader.load_project_variables(project_id)
    return ProjectVariablesResponse(
        project_id=project_id,
        variables=variables,
    )


@router.put("/prompts/projects/{project_id}/variables")
async def update_project_variables(
    project_id: str,
    request: ProjectVariablesRequest,
) -> ProjectVariablesResponse:
    """Update all variables for a project (saves to variables.json file).

    Replaces the entire variables.json file with the provided variables.
    Variables are stored in: projects/{project_id}/variables.json
    """
    PromptLoader.save_project_variables(project_id, request.variables)
    return ProjectVariablesResponse(
        project_id=project_id,
        variables=request.variables,
    )


# ============================================================================
# Legacy File-based Routes (parameterized - must be LAST)
# ============================================================================

@router.get("/prompts/{prompt_type}")
async def get_prompt_template(prompt_type: str) -> FilePromptTemplate:
    """Get a prompt template by type (file-based).

    Args:
        prompt_type: Type of prompt (analysis, translation, optimization, proofreading)

    Returns:
        PromptTemplate with system and user prompts
    """
    try:
        return PromptLoader.load_template(prompt_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/prompts/{prompt_type}")
async def update_prompt_template(
    prompt_type: str,
    request: UpdatePromptRequest,
) -> FilePromptTemplate:
    """Update a prompt template (file-based, system prompt only).

    Args:
        prompt_type: Type of prompt to update
        request: New prompt content

    Returns:
        Updated PromptTemplate
    """
    try:
        return PromptLoader.save_template(
            prompt_type,
            request.system_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/prompts/{prompt_type}/preview")
async def preview_prompt(
    prompt_type: str,
    request: PreviewPromptRequest,
) -> PreviewPromptResponse:
    """Preview rendered prompts with variables.

    Both system and user prompts can be customized for preview purposes.

    Args:
        prompt_type: Type of prompt
        request: Variables and optional custom prompts

    Returns:
        Rendered system and user prompts with validation info
    """
    try:
        # Load default template for fallback
        template = PromptLoader.load_template(prompt_type)

        # Use custom prompts if provided, otherwise use template defaults
        system_template = request.custom_system_prompt or template.system_prompt
        user_template = request.custom_user_prompt or template.user_prompt_template

        # Validate before rendering
        system_validation = PromptLoader.validate_template(
            system_template, request.variables
        )
        user_validation = PromptLoader.validate_template(
            user_template, request.variables
        )

        # Combine validation results
        combined_validation = {
            "system": {
                "is_valid": system_validation.is_valid,
                "missing_variables": system_validation.missing_variables,
                "warnings": system_validation.warnings,
            },
            "user": {
                "is_valid": user_validation.is_valid,
                "missing_variables": user_validation.missing_variables,
                "warnings": user_validation.warnings,
            },
            "is_valid": system_validation.is_valid and user_validation.is_valid,
        }

        # Render templates with variable substitution
        rendered_system = PromptLoader.render(system_template, request.variables)
        rendered_user = PromptLoader.render(user_template, request.variables)

        return PreviewPromptResponse(
            system_prompt=rendered_system,
            user_prompt=rendered_user,
            validation=combined_validation,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

