"""Database models package."""

from app.models.database.base import Base, get_db
from app.models.database.project import Project
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.models.database.translation import Translation, TranslationTask
from app.models.database.book_analysis import BookAnalysis
from app.models.database.analysis_task import AnalysisTask
from app.models.database.reference_epub import ReferenceEPUB
from app.models.database.paragraph_match import ParagraphMatch
from app.models.database.translation_conversation import (
    TranslationConversation,
    ConversationMessage,
)
from app.models.database.proofreading import (
    ProofreadingSession,
    ProofreadingSuggestion,
)
from app.models.database.llm_configuration import LLMConfiguration
from app.models.database.prompt_template import (
    PromptTemplate,
    ProjectPromptConfig,
)
# Centralized enums
from app.models.database.enums import (
    TranslationMode,
    TaskStatus,
    ChapterType,
    ContentType,
    ProofreadingStatus,
    SuggestionStatus,
    ImprovementLevel,
    PromptCategory,
)
# NOTE: ProjectVariable and VariableType removed - variables are now file-based

__all__ = [
    # Base
    "Base",
    "get_db",
    # Models
    "Project",
    "Chapter",
    "Paragraph",
    "Translation",
    "TranslationTask",
    "BookAnalysis",
    "AnalysisTask",
    "ReferenceEPUB",
    "ParagraphMatch",
    "TranslationConversation",
    "ConversationMessage",
    "ProofreadingSession",
    "ProofreadingSuggestion",
    "LLMConfiguration",
    "PromptTemplate",
    "ProjectPromptConfig",
    # Enums
    "TranslationMode",
    "TaskStatus",
    "ChapterType",
    "ContentType",
    "ProofreadingStatus",
    "SuggestionStatus",
    "ImprovementLevel",
    "PromptCategory",
]
