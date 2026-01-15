"""Project storage management utilities.

This module provides centralized functions for managing project-scoped storage.
Each project has its own directory structure:

projects/{project_id}/
├── config.json           # Project configuration
├── variables.json        # Custom template variables (optional)
├── prompts/              # Custom prompt templates
├── uploads/              # Original and reference EPUBs
├── exports/              # Generated output files
├── content/              # Reserved for future use
└── cache/                # Reserved for future use (LLM caching)
"""

from pathlib import Path
from typing import Optional
import json
import shutil


class ProjectStorage:
    """Manage project-scoped file storage."""

    # Base directory for all projects
    PROJECTS_BASE = Path(__file__).parent.parent.parent.parent / "projects"

    # Standard subdirectory names
    UPLOADS_DIR = "uploads"
    EXPORTS_DIR = "exports"
    PROMPTS_DIR = "prompts"
    CONTENT_DIR = "content"
    CACHE_DIR = "cache"

    # Standard file names
    CONFIG_FILE = "config.json"
    VARIABLES_FILE = "variables.json"
    ORIGINAL_EPUB = "original.epub"
    REFERENCE_EPUB = "reference.epub"

    @classmethod
    def get_project_dir(cls, project_id: str) -> Path:
        """Get the root directory for a project.

        Args:
            project_id: Project UUID

        Returns:
            Path to project directory
        """
        return cls.PROJECTS_BASE / project_id

    @classmethod
    def get_uploads_dir(cls, project_id: str) -> Path:
        """Get the uploads directory for a project.

        Args:
            project_id: Project UUID

        Returns:
            Path to uploads directory
        """
        return cls.get_project_dir(project_id) / cls.UPLOADS_DIR

    @classmethod
    def get_exports_dir(cls, project_id: str) -> Path:
        """Get the exports directory for a project.

        Args:
            project_id: Project UUID

        Returns:
            Path to exports directory
        """
        return cls.get_project_dir(project_id) / cls.EXPORTS_DIR

    @classmethod
    def get_prompts_dir(cls, project_id: str) -> Path:
        """Get the prompts directory for a project.

        Args:
            project_id: Project UUID

        Returns:
            Path to prompts directory
        """
        return cls.get_project_dir(project_id) / cls.PROMPTS_DIR

    @classmethod
    def get_cache_dir(cls, project_id: str) -> Path:
        """Get the cache directory for a project.

        Args:
            project_id: Project UUID

        Returns:
            Path to cache directory
        """
        return cls.get_project_dir(project_id) / cls.CACHE_DIR

    @classmethod
    def get_original_epub_path(cls, project_id: str) -> Path:
        """Get the path to the original EPUB file.

        Args:
            project_id: Project UUID

        Returns:
            Path to original EPUB file
        """
        return cls.get_uploads_dir(project_id) / cls.ORIGINAL_EPUB

    @classmethod
    def get_reference_epub_path(cls, project_id: str) -> Path:
        """Get the path to the reference EPUB file.

        Args:
            project_id: Project UUID

        Returns:
            Path to reference EPUB file
        """
        return cls.get_uploads_dir(project_id) / cls.REFERENCE_EPUB

    @classmethod
    def get_translated_epub_path(cls, project_id: str) -> Path:
        """Get the path to the translated EPUB export.

        Args:
            project_id: Project UUID

        Returns:
            Path to translated EPUB file
        """
        return cls.get_exports_dir(project_id) / "translated.epub"

    @classmethod
    def get_bilingual_epub_path(cls, project_id: str) -> Path:
        """Get the path to the bilingual EPUB export.

        Args:
            project_id: Project UUID

        Returns:
            Path to bilingual EPUB file
        """
        return cls.get_exports_dir(project_id) / "bilingual.epub"

    @classmethod
    def initialize_project_structure(cls, project_id: str) -> None:
        """Initialize the directory structure for a new project.

        Creates all necessary subdirectories.

        Args:
            project_id: Project UUID
        """
        project_dir = cls.get_project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        cls.get_uploads_dir(project_id).mkdir(exist_ok=True)
        cls.get_exports_dir(project_id).mkdir(exist_ok=True)
        cls.get_prompts_dir(project_id).mkdir(exist_ok=True)

        # Create prompt subdirectories
        prompts_dir = cls.get_prompts_dir(project_id)
        (prompts_dir / "analysis").mkdir(exist_ok=True)
        (prompts_dir / "translation").mkdir(exist_ok=True)
        (prompts_dir / "optimization").mkdir(exist_ok=True)
        (prompts_dir / "proofreading").mkdir(exist_ok=True)

        # Reserved directories (not created by default)
        # cls.get_content_dir(project_id).mkdir(exist_ok=True)
        # cls.get_cache_dir(project_id).mkdir(exist_ok=True)

    @classmethod
    def delete_project(cls, project_id: str) -> None:
        """Delete all files and directories for a project.

        Args:
            project_id: Project UUID
        """
        project_dir = cls.get_project_dir(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)

    @classmethod
    def project_exists(cls, project_id: str) -> bool:
        """Check if a project directory exists.

        Args:
            project_id: Project UUID

        Returns:
            True if project directory exists
        """
        return cls.get_project_dir(project_id).exists()

    @classmethod
    def get_config_path(cls, project_id: str) -> Path:
        """Get the path to the project config file.

        Args:
            project_id: Project UUID

        Returns:
            Path to config.json
        """
        return cls.get_project_dir(project_id) / cls.CONFIG_FILE

    @classmethod
    def load_config(cls, project_id: str) -> Optional[dict]:
        """Load project configuration from config.json.

        Args:
            project_id: Project UUID

        Returns:
            Project config dict or None if not found
        """
        config_path = cls.get_config_path(project_id)
        if not config_path.exists():
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    @classmethod
    def save_config(cls, project_id: str, config: dict) -> None:
        """Save project configuration to config.json.

        Args:
            project_id: Project UUID
            config: Configuration dictionary
        """
        config_path = cls.get_config_path(project_id)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_project_size(cls, project_id: str) -> int:
        """Get the total size of all project files in bytes.

        Args:
            project_id: Project UUID

        Returns:
            Total size in bytes
        """
        project_dir = cls.get_project_dir(project_id)
        if not project_dir.exists():
            return 0

        total_size = 0
        for path in project_dir.rglob("*"):
            if path.is_file():
                total_size += path.stat().st_size
        return total_size

    @classmethod
    def list_exports(cls, project_id: str) -> list[dict]:
        """List all export files for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of dicts with file info (name, size, modified_at)
        """
        exports_dir = cls.get_exports_dir(project_id)
        if not exports_dir.exists():
            return []

        exports = []
        for file_path in exports_dir.glob("*.epub"):
            stat = file_path.stat()
            exports.append({
                "name": file_path.name,
                "size": stat.st_size,
                "modified_at": stat.st_mtime,
            })

        return sorted(exports, key=lambda x: x["modified_at"], reverse=True)


# Convenience instance for direct import
project_storage = ProjectStorage()

