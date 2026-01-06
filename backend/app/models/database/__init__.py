"""Database models package."""

from app.models.database.base import Base, get_db
from app.models.database.project import Project
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.models.database.translation import Translation, TranslationTask
from app.models.database.book_analysis import BookAnalysis
from app.models.database.reference_epub import ReferenceEPUB
from app.models.database.paragraph_match import ParagraphMatch
from app.models.database.translation_reasoning import TranslationReasoning
from app.models.database.translation_conversation import (
    TranslationConversation,
    ConversationMessage,
)
from app.models.database.proofreading import (
    ProofreadingSession,
    ProofreadingSuggestion,
    ProofreadingStatus,
    SuggestionStatus,
)
from app.models.database.llm_configuration import LLMConfiguration
from app.models.database.prompt_template import (
    PromptTemplate,
    ProjectPromptConfig,
    PromptCategory,
    ProjectVariable,
    VariableType,
)

__all__ = [
    "Base",
    "get_db",
    "Project",
    "Chapter",
    "Paragraph",
    "Translation",
    "TranslationTask",
    "BookAnalysis",
    "ReferenceEPUB",
    "ParagraphMatch",
    "TranslationReasoning",
    "TranslationConversation",
    "ConversationMessage",
    "ProofreadingSession",
    "ProofreadingSuggestion",
    "ProofreadingStatus",
    "SuggestionStatus",
    "LLMConfiguration",
    "PromptTemplate",
    "ProjectPromptConfig",
    "PromptCategory",
    "ProjectVariable",
    "VariableType",
]
