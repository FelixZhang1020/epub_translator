"""Prompt management API routes."""

import json
import uuid
from typing import Any, Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts.loader import PromptLoader, PromptTemplate as FilePromptTemplate
from app.models.database import (
    get_db,
    PromptTemplate as DBPromptTemplate,
    ProjectPromptConfig,
    PromptCategory,
    ProjectVariable,
    VariableType,
)

router = APIRouter()


# ============================================================================
# Pydantic Models
# ============================================================================

class UpdatePromptRequest(BaseModel):
    """Request model for updating prompts."""
    system_prompt: str
    user_prompt: str


class PreviewPromptRequest(BaseModel):
    """Request model for previewing prompts."""
    variables: dict[str, Any]
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None


class PreviewPromptResponse(BaseModel):
    """Response model for prompt preview."""
    system_prompt: str
    user_prompt: str


class TemplateCreateRequest(BaseModel):
    """Create a new prompt template."""
    name: str
    description: Optional[str] = None
    category: str
    system_prompt: str
    default_user_prompt: Optional[str] = None
    variables: Optional[List[str]] = None
    is_default: bool = False


class TemplateUpdateRequest(BaseModel):
    """Update an existing prompt template."""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    default_user_prompt: Optional[str] = None
    variables: Optional[List[str]] = None
    is_default: Optional[bool] = None


class TemplateResponse(BaseModel):
    """Response model for prompt template."""
    id: str
    name: str
    description: Optional[str]
    category: str
    system_prompt: str
    default_user_prompt: Optional[str]
    variables: Optional[List[str]]
    is_builtin: bool
    is_default: bool
    created_at: str
    updated_at: str


class ProjectConfigRequest(BaseModel):
    """Create or update project-specific prompt config."""
    template_id: Optional[str] = None
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None
    use_custom_system: bool = False
    use_custom_user: bool = False


class ProjectConfigResponse(BaseModel):
    """Response model for project prompt config."""
    id: str
    project_id: str
    category: str
    template_id: Optional[str]
    template_name: Optional[str]
    custom_system_prompt: Optional[str]
    custom_user_prompt: Optional[str]
    use_custom_system: bool
    use_custom_user: bool
    resolved_system_prompt: str
    resolved_user_prompt: str


class ProjectVariableCreate(BaseModel):
    """Create a project variable."""
    name: str
    value: str
    value_type: str = "string"
    description: Optional[str] = None


class ProjectVariableUpdate(BaseModel):
    """Update a project variable."""
    value: Optional[str] = None
    value_type: Optional[str] = None
    description: Optional[str] = None


class ProjectVariableResponse(BaseModel):
    """Response model for project variable."""
    id: str
    project_id: str
    name: str
    value: str
    value_type: str
    description: Optional[str]
    created_at: str
    updated_at: str


# ============================================================================
# Helper Functions
# ============================================================================

def _template_to_response(template: DBPromptTemplate) -> TemplateResponse:
    """Convert template model to response."""
    variables = None
    if template.variables:
        try:
            variables = json.loads(template.variables)
        except json.JSONDecodeError:
            variables = []

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        system_prompt=template.system_prompt,
        default_user_prompt=template.default_user_prompt,
        variables=variables,
        is_builtin=template.is_builtin,
        is_default=template.is_default,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


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


@router.post("/prompts/sync-builtin")
async def sync_builtin_templates(
    db: AsyncSession = Depends(get_db),
):
    """Sync built-in templates from the file system prompts directory."""
    synced = []
    for category in PromptCategory:
        try:
            file_template = PromptLoader.load_template(category.value)

            result = await db.execute(
                select(DBPromptTemplate)
                .where(DBPromptTemplate.category == category.value)
                .where(DBPromptTemplate.is_builtin == True)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.system_prompt = file_template.system_prompt
                existing.default_user_prompt = file_template.user_prompt_template
                existing.variables = json.dumps(file_template.variables)
            else:
                template = DBPromptTemplate(
                    id=str(uuid.uuid4()),
                    name=f"Default {category.value.title()}",
                    description=f"Built-in {category.value} prompt template",
                    category=category.value,
                    system_prompt=file_template.system_prompt,
                    default_user_prompt=file_template.user_prompt_template,
                    variables=json.dumps(file_template.variables),
                    is_builtin=True,
                    is_default=True,
                )
                db.add(template)

            synced.append(category.value)
        except ValueError:
            pass

    await db.commit()
    return {"synced": synced}


# ============================================================================
# Template Routes (specific paths before parameterized)
# ============================================================================

@router.get("/prompts/templates")
async def list_templates(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[TemplateResponse]:
    """List all prompt templates, optionally filtered by category."""
    query = select(DBPromptTemplate)
    if category:
        query = query.where(DBPromptTemplate.category == category)
    query = query.order_by(DBPromptTemplate.category, DBPromptTemplate.name)

    result = await db.execute(query)
    templates = result.scalars().all()

    return [_template_to_response(t) for t in templates]


@router.post("/prompts/templates")
async def create_template(
    request: TemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Create a new prompt template."""
    valid_categories = [c.value for c in PromptCategory]
    if request.category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )

    if request.is_default:
        result = await db.execute(
            select(DBPromptTemplate)
            .where(DBPromptTemplate.category == request.category)
            .where(DBPromptTemplate.is_default == True)
        )
        for t in result.scalars().all():
            t.is_default = False

    template = DBPromptTemplate(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        category=request.category,
        system_prompt=request.system_prompt,
        default_user_prompt=request.default_user_prompt,
        variables=json.dumps(request.variables) if request.variables else None,
        is_builtin=False,
        is_default=request.is_default,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return _template_to_response(template)


@router.get("/prompts/templates/{template_id}")
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Get a specific prompt template."""
    result = await db.execute(
        select(DBPromptTemplate).where(DBPromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return _template_to_response(template)


@router.put("/prompts/templates/{template_id}")
async def update_template(
    template_id: str,
    request: TemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Update an existing prompt template."""
    result = await db.execute(
        select(DBPromptTemplate).where(DBPromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if request.name is not None:
        template.name = request.name
    if request.description is not None:
        template.description = request.description
    if request.system_prompt is not None:
        template.system_prompt = request.system_prompt
    if request.default_user_prompt is not None:
        template.default_user_prompt = request.default_user_prompt
    if request.variables is not None:
        template.variables = json.dumps(request.variables)
    if request.is_default is not None:
        if request.is_default and not template.is_default:
            result = await db.execute(
                select(DBPromptTemplate)
                .where(DBPromptTemplate.category == template.category)
                .where(DBPromptTemplate.is_default == True)
                .where(DBPromptTemplate.id != template_id)
            )
            for t in result.scalars().all():
                t.is_default = False
        template.is_default = request.is_default

    await db.commit()
    await db.refresh(template)

    return _template_to_response(template)


@router.delete("/prompts/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a prompt template."""
    result = await db.execute(
        select(DBPromptTemplate).where(DBPromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_builtin:
        raise HTTPException(status_code=400, detail="Cannot delete built-in template")

    await db.delete(template)
    await db.commit()

    return {"message": "Template deleted"}


# ============================================================================
# Project Config Routes
# ============================================================================

@router.get("/prompts/projects/{project_id}")
async def list_project_configs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[ProjectConfigResponse]:
    """List all prompt configs for a project."""
    result = await db.execute(
        select(ProjectPromptConfig)
        .where(ProjectPromptConfig.project_id == project_id)
        .order_by(ProjectPromptConfig.category)
    )
    configs = result.scalars().all()

    responses = []
    for config in configs:
        template = None
        if config.template_id:
            result = await db.execute(
                select(DBPromptTemplate).where(DBPromptTemplate.id == config.template_id)
            )
            template = result.scalar_one_or_none()

        resolved_system = config.custom_system_prompt if config.use_custom_system else (
            template.system_prompt if template else ""
        )
        resolved_user = config.custom_user_prompt if config.use_custom_user else (
            template.default_user_prompt if template else ""
        )

        responses.append(ProjectConfigResponse(
            id=config.id,
            project_id=config.project_id,
            category=config.category,
            template_id=config.template_id,
            template_name=template.name if template else None,
            custom_system_prompt=config.custom_system_prompt,
            custom_user_prompt=config.custom_user_prompt,
            use_custom_system=config.use_custom_system,
            use_custom_user=config.use_custom_user,
            resolved_system_prompt=resolved_system or "",
            resolved_user_prompt=resolved_user or "",
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
    - User-defined variables

    Args:
        project_id: Project ID
        stage: Optional stage filter (analysis, translation, optimization, proofreading)

    Returns:
        Dictionary with variable categories and their variables
    """
    from app.core.prompts.variables import VariableService

    return await VariableService.get_available_variables(db, project_id, stage)


@router.get("/prompts/projects/{project_id}/{category}")
async def get_project_config(
    project_id: str,
    category: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectConfigResponse:
    """Get prompt config for a specific project and category."""
    result = await db.execute(
        select(ProjectPromptConfig)
        .where(ProjectPromptConfig.project_id == project_id)
        .where(ProjectPromptConfig.category == category)
    )
    config = result.scalar_one_or_none()

    if not config:
        try:
            file_template = PromptLoader.load_template(category)
            return ProjectConfigResponse(
                id="",
                project_id=project_id,
                category=category,
                template_id=None,
                template_name="Default (from file)",
                custom_system_prompt=None,
                custom_user_prompt=None,
                use_custom_system=False,
                use_custom_user=False,
                resolved_system_prompt=file_template.system_prompt,
                resolved_user_prompt=file_template.user_prompt_template,
            )
        except ValueError:
            raise HTTPException(status_code=404, detail=f"No config for category: {category}")

    template = None
    if config.template_id:
        result = await db.execute(
            select(DBPromptTemplate).where(DBPromptTemplate.id == config.template_id)
        )
        template = result.scalar_one_or_none()

    if config.use_custom_system:
        resolved_system = config.custom_system_prompt or ""
    elif template:
        resolved_system = template.system_prompt
    else:
        try:
            file_template = PromptLoader.load_template(category)
            resolved_system = file_template.system_prompt
        except ValueError:
            resolved_system = ""

    if config.use_custom_user:
        resolved_user = config.custom_user_prompt or ""
    elif template:
        resolved_user = template.default_user_prompt or ""
    else:
        try:
            file_template = PromptLoader.load_template(category)
            resolved_user = file_template.user_prompt_template
        except ValueError:
            resolved_user = ""

    return ProjectConfigResponse(
        id=config.id,
        project_id=config.project_id,
        category=config.category,
        template_id=config.template_id,
        template_name=template.name if template else None,
        custom_system_prompt=config.custom_system_prompt,
        custom_user_prompt=config.custom_user_prompt,
        use_custom_system=config.use_custom_system,
        use_custom_user=config.use_custom_user,
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
    """Create or update prompt config for a project and category."""
    valid_categories = [c.value for c in PromptCategory]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )

    template = None
    if request.template_id:
        result = await db.execute(
            select(DBPromptTemplate).where(DBPromptTemplate.id == request.template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if template.category != category:
            raise HTTPException(
                status_code=400,
                detail=f"Template category mismatch"
            )

    result = await db.execute(
        select(ProjectPromptConfig)
        .where(ProjectPromptConfig.project_id == project_id)
        .where(ProjectPromptConfig.category == category)
    )
    config = result.scalar_one_or_none()

    if config:
        config.template_id = request.template_id
        config.custom_system_prompt = request.custom_system_prompt
        config.custom_user_prompt = request.custom_user_prompt
        config.use_custom_system = request.use_custom_system
        config.use_custom_user = request.use_custom_user
    else:
        config = ProjectPromptConfig(
            id=str(uuid.uuid4()),
            project_id=project_id,
            category=category,
            template_id=request.template_id,
            custom_system_prompt=request.custom_system_prompt,
            custom_user_prompt=request.custom_user_prompt,
            use_custom_system=request.use_custom_system,
            use_custom_user=request.use_custom_user,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)

    if config.use_custom_system:
        resolved_system = config.custom_system_prompt or ""
    elif template:
        resolved_system = template.system_prompt
    else:
        try:
            file_template = PromptLoader.load_template(category)
            resolved_system = file_template.system_prompt
        except ValueError:
            resolved_system = ""

    if config.use_custom_user:
        resolved_user = config.custom_user_prompt or ""
    elif template:
        resolved_user = template.default_user_prompt or ""
    else:
        try:
            file_template = PromptLoader.load_template(category)
            resolved_user = file_template.user_prompt_template
        except ValueError:
            resolved_user = ""

    return ProjectConfigResponse(
        id=config.id,
        project_id=config.project_id,
        category=config.category,
        template_id=config.template_id,
        template_name=template.name if template else None,
        custom_system_prompt=config.custom_system_prompt,
        custom_user_prompt=config.custom_user_prompt,
        use_custom_system=config.use_custom_system,
        use_custom_user=config.use_custom_user,
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


# ============================================================================
# Project Variables Routes
# ============================================================================

def _variable_to_response(var: ProjectVariable) -> ProjectVariableResponse:
    """Convert variable model to response."""
    return ProjectVariableResponse(
        id=var.id,
        project_id=var.project_id,
        name=var.name,
        value=var.value,
        value_type=var.value_type,
        description=var.description,
        created_at=var.created_at.isoformat(),
        updated_at=var.updated_at.isoformat(),
    )


@router.get("/prompts/projects/{project_id}/variables")
async def list_project_variables(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[ProjectVariableResponse]:
    """List all variables for a project."""
    result = await db.execute(
        select(ProjectVariable)
        .where(ProjectVariable.project_id == project_id)
        .order_by(ProjectVariable.name)
    )
    variables = result.scalars().all()
    return [_variable_to_response(v) for v in variables]


@router.post("/prompts/projects/{project_id}/variables")
async def create_project_variable(
    project_id: str,
    request: ProjectVariableCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectVariableResponse:
    """Create a new variable for a project."""
    # Validate variable type
    valid_types = [t.value for t in VariableType]
    if request.value_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value_type. Must be one of: {valid_types}"
        )

    # Check for duplicate name
    result = await db.execute(
        select(ProjectVariable)
        .where(ProjectVariable.project_id == project_id)
        .where(ProjectVariable.name == request.name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Variable '{request.name}' already exists for this project"
        )

    # Validate JSON if type is json
    if request.value_type == VariableType.JSON.value:
        try:
            json.loads(request.value)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Value must be valid JSON for json type"
            )

    variable = ProjectVariable(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=request.name,
        value=request.value,
        value_type=request.value_type,
        description=request.description,
    )
    db.add(variable)
    await db.commit()
    await db.refresh(variable)

    return _variable_to_response(variable)


@router.get("/prompts/projects/{project_id}/variables/{variable_name}")
async def get_project_variable(
    project_id: str,
    variable_name: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectVariableResponse:
    """Get a specific variable for a project."""
    result = await db.execute(
        select(ProjectVariable)
        .where(ProjectVariable.project_id == project_id)
        .where(ProjectVariable.name == variable_name)
    )
    variable = result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    return _variable_to_response(variable)


@router.put("/prompts/projects/{project_id}/variables/{variable_name}")
async def update_project_variable(
    project_id: str,
    variable_name: str,
    request: ProjectVariableUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectVariableResponse:
    """Update a variable for a project."""
    result = await db.execute(
        select(ProjectVariable)
        .where(ProjectVariable.project_id == project_id)
        .where(ProjectVariable.name == variable_name)
    )
    variable = result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    if request.value_type is not None:
        valid_types = [t.value for t in VariableType]
        if request.value_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid value_type. Must be one of: {valid_types}"
            )
        variable.value_type = request.value_type

    if request.value is not None:
        # Validate JSON if type is json
        if variable.value_type == VariableType.JSON.value:
            try:
                json.loads(request.value)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Value must be valid JSON for json type"
                )
        variable.value = request.value

    if request.description is not None:
        variable.description = request.description

    await db.commit()
    await db.refresh(variable)

    return _variable_to_response(variable)


@router.delete("/prompts/projects/{project_id}/variables/{variable_name}")
async def delete_project_variable(
    project_id: str,
    variable_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a variable from a project."""
    result = await db.execute(
        select(ProjectVariable)
        .where(ProjectVariable.project_id == project_id)
        .where(ProjectVariable.name == variable_name)
    )
    variable = result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    await db.delete(variable)
    await db.commit()

    return {"message": f"Variable '{variable_name}' deleted"}


# ============================================================================
# Legacy File-based Routes (parameterized - must be LAST)
# ============================================================================

@router.get("/prompts/{prompt_type}")
async def get_prompt_template(prompt_type: str) -> FilePromptTemplate:
    """Get a prompt template by type (file-based).

    Args:
        prompt_type: Type of prompt (analysis, translation, reasoning, proofreading)

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
    """Update a prompt template (file-based).

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
            request.user_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/prompts/{prompt_type}/preview")
async def preview_prompt(
    prompt_type: str,
    request: PreviewPromptRequest,
) -> PreviewPromptResponse:
    """Preview rendered prompts with variables.

    Args:
        prompt_type: Type of prompt
        request: Variables and optional custom prompts

    Returns:
        Rendered system and user prompts
    """
    try:
        result = PromptLoader.preview(
            prompt_type,
            request.variables,
            request.custom_system_prompt,
            request.custom_user_prompt,
        )
        return PreviewPromptResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
