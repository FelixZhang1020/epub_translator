# Translation LLM Flow Redesign

## Executive Summary

This document proposes a redesign of the LLM input/output pipeline for the EPUB translation system. The goal is to create a cleaner, more maintainable, and extensible architecture that properly separates concerns and enables advanced translation features.

## Current Architecture Issues

### 1. Scattered Data Flow
- `TranslationRequest` defined in `adapter.py`
- Prompt building split between `prompts.py` and `loader.py`
- Context assembly happens in `orchestrator.py`
- No clear contract between layers

### 2. Weak Mode Abstraction
- `author_based` and `optimization` modes hardcoded across multiple files
- No clear extension mechanism for new translation modes
- Mode-specific logic scattered throughout the codebase

### 3. Inconsistent Context Injection
- `analysis_text` passed as raw JSON string
- `author_background` and `custom_prompts` handled separately
- No unified context model

### 4. Simplistic Output Handling
- Direct extraction of `response.choices[0].message.content`
- No structured output validation
- No post-processing pipeline

### 5. Service Layer Redundancy
- `llm/service.py` (LiteLLM wrapper) overlaps with `llm/adapter.py`
- Unclear which layer to use when

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRANSLATION PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  CONTEXT    │───▶│   PROMPT    │───▶│    LLM      │───▶│   OUTPUT    │  │
│  │  BUILDER    │    │   ENGINE    │    │   GATEWAY   │    │  PROCESSOR  │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│        │                  │                  │                  │          │
│        ▼                  ▼                  ▼                  ▼          │
│  TranslationContext  PromptBundle      LLMResponse      TranslationResult  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Data Models

### 1. Translation Context (Input Assembly)

```python
# backend/app/core/translation/models/context.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class TranslationMode(str, Enum):
    """Supported translation modes"""
    DIRECT = "direct"                    # Simple direct translation
    AUTHOR_AWARE = "author_aware"        # Style-preserving with author context
    OPTIMIZATION = "optimization"         # Improve existing translation
    COMPARATIVE = "comparative"           # Multiple versions comparison
    ITERATIVE = "iterative"              # Multi-pass refinement

class SourceMaterial(BaseModel):
    """Content to be translated"""
    text: str
    language: str = "en"
    word_count: int = Field(default=0)
    paragraph_index: Optional[int] = None
    chapter_index: Optional[int] = None

    def model_post_init(self, __context):
        if not self.word_count:
            self.word_count = len(self.text.split())

class ExistingTranslation(BaseModel):
    """Previous translation for optimization mode"""
    text: str
    provider: Optional[str] = None
    model: Optional[str] = None
    version: int = 1
    quality_score: Optional[float] = None

class BookAnalysisContext(BaseModel):
    """Structured book analysis data"""
    author_name: Optional[str] = None
    author_biography: Optional[str] = None
    writing_style: Optional[str] = None
    tone: Optional[str] = None
    genre: Optional[str] = None
    target_audience: Optional[str] = None
    key_terminology: Dict[str, str] = Field(default_factory=dict)

    # For prompt injection
    custom_guidelines: List[str] = Field(default_factory=list)

    @classmethod
    def from_raw_analysis(cls, raw: Dict[str, Any]) -> "BookAnalysisContext":
        """Factory from raw analysis JSON"""
        return cls(
            author_name=raw.get("author_name"),
            author_biography=raw.get("author_biography"),
            writing_style=raw.get("writing_style"),
            tone=raw.get("tone"),
            genre=raw.get("genre"),
            target_audience=raw.get("target_audience"),
            key_terminology=raw.get("key_terminology", {}),
            custom_guidelines=raw.get("custom_guidelines", []),
        )

class AdjacentContext(BaseModel):
    """Surrounding paragraphs for coherence"""
    previous_original: Optional[str] = None
    previous_translation: Optional[str] = None
    next_original: Optional[str] = None
    # Enables context-aware translation

class TranslationContext(BaseModel):
    """
    Complete context for a single translation request.
    This is the PRIMARY input contract for the translation pipeline.
    """
    # Core content
    source: SourceMaterial
    target_language: str = "zh"

    # Mode configuration
    mode: TranslationMode = TranslationMode.DIRECT

    # Rich context
    book_analysis: Optional[BookAnalysisContext] = None
    adjacent: Optional[AdjacentContext] = None
    existing: Optional[ExistingTranslation] = None  # For optimization mode

    # Custom overrides
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None

    # Processing hints
    preserve_formatting: bool = True
    preserve_proper_nouns: bool = True

    def validate_for_mode(self) -> None:
        """Validate context completeness for selected mode"""
        if self.mode == TranslationMode.OPTIMIZATION and not self.existing:
            raise ValueError("Optimization mode requires existing_translation")
        if self.mode == TranslationMode.AUTHOR_AWARE and not self.book_analysis:
            raise ValueError("Author-aware mode requires book_analysis")
```

### 2. Prompt Bundle (LLM Input)

```python
# backend/app/core/translation/models/prompt.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class Message(BaseModel):
    """Single message in conversation"""
    role: str  # "system" | "user" | "assistant"
    content: str

class PromptBundle(BaseModel):
    """
    Complete prompt package ready for LLM.
    This is the output of the PromptEngine.
    """
    messages: List[Message]

    # Model configuration
    temperature: float = 0.3
    max_tokens: int = 4096

    # Response format
    response_format: Optional[Dict[str, Any]] = None  # For JSON mode

    # Metadata for logging
    mode: str = "direct"
    estimated_input_tokens: int = 0

    @property
    def system_prompt(self) -> Optional[str]:
        for msg in self.messages:
            if msg.role == "system":
                return msg.content
        return None

    @property
    def user_prompt(self) -> Optional[str]:
        for msg in self.messages:
            if msg.role == "user":
                return msg.content
        return None

    def to_openai_format(self) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def to_anthropic_format(self) -> tuple[str, List[Dict]]:
        system = self.system_prompt or ""
        messages = [
            {"role": m.role, "content": m.content}
            for m in self.messages if m.role != "system"
        ]
        return system, messages
```

### 3. LLM Response (Raw Output)

```python
# backend/app/core/translation/models/response.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class TokenUsage(BaseModel):
    """Token consumption details"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def estimated_cost_usd(self) -> float:
        # Simplified cost estimation
        return (self.prompt_tokens * 0.003 + self.completion_tokens * 0.015) / 1000

class LLMResponse(BaseModel):
    """
    Raw response from LLM provider.
    Provider-agnostic representation.
    """
    content: str

    # Provider info
    provider: str
    model: str

    # Usage
    usage: TokenUsage = Field(default_factory=TokenUsage)

    # Timing
    latency_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Raw response for debugging
    raw_response: Optional[Dict[str, Any]] = None

    # Streaming metadata
    is_complete: bool = True
    chunk_index: Optional[int] = None
```

### 4. Translation Result (Processed Output)

```python
# backend/app/core/translation/models/result.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class QualityFlag(str, Enum):
    """Quality indicators"""
    CONFIDENT = "confident"
    UNCERTAIN = "uncertain"
    NEEDS_REVIEW = "needs_review"
    FORMATTING_LOST = "formatting_lost"

class TranslationResult(BaseModel):
    """
    Final processed translation output.
    This is the output contract of the translation pipeline.
    """
    # Core output
    translated_text: str

    # Quality metadata
    quality_flag: QualityFlag = QualityFlag.CONFIDENT
    confidence_score: Optional[float] = None

    # Processing metadata
    mode_used: str
    provider: str
    model: str

    # Cost tracking
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0

    # Formatting preservation
    preserved_elements: List[str] = Field(default_factory=list)

    # For debugging
    raw_llm_response: Optional[str] = None

    # Chain information (for multi-step)
    step_index: int = 0
    total_steps: int = 1
```

---

## Pipeline Components

### 1. Context Builder

```python
# backend/app/core/translation/pipeline/context_builder.py

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.context import (
    TranslationContext,
    TranslationMode,
    SourceMaterial,
    BookAnalysisContext,
    AdjacentContext,
    ExistingTranslation,
)
from app.models.database import Paragraph, Project, BookAnalysis


class ContextBuilder:
    """
    Builds TranslationContext from database entities.
    Single responsibility: Context assembly.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build(
        self,
        paragraph: Paragraph,
        project: Project,
        mode: TranslationMode,
        *,
        include_adjacent: bool = True,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
    ) -> TranslationContext:
        """Build complete translation context for a paragraph"""

        # 1. Build source material
        source = SourceMaterial(
            text=paragraph.original_text,
            language="en",  # Could be detected
            paragraph_index=paragraph.paragraph_number,
            chapter_index=paragraph.chapter.chapter_number if paragraph.chapter else None,
        )

        # 2. Build book analysis context
        book_analysis = None
        if project.analysis:
            book_analysis = BookAnalysisContext.from_raw_analysis(
                project.analysis.raw_analysis
            )

        # 3. Build adjacent context for coherence
        adjacent = None
        if include_adjacent:
            adjacent = await self._build_adjacent_context(paragraph)

        # 4. Get existing translation for optimization mode
        existing = None
        if mode == TranslationMode.OPTIMIZATION:
            existing = await self._get_existing_translation(paragraph)

        # 5. Assemble final context
        return TranslationContext(
            source=source,
            target_language="zh",
            mode=mode,
            book_analysis=book_analysis,
            adjacent=adjacent,
            existing=existing,
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
        )

    async def _build_adjacent_context(
        self, paragraph: Paragraph
    ) -> Optional[AdjacentContext]:
        """Get surrounding paragraphs for context"""
        # Query previous and next paragraphs
        # ... implementation details
        pass

    async def _get_existing_translation(
        self, paragraph: Paragraph
    ) -> Optional[ExistingTranslation]:
        """Get latest translation for optimization"""
        if paragraph.latest_translation:
            t = paragraph.latest_translation
            return ExistingTranslation(
                text=t.translated_text,
                provider=t.provider,
                model=t.model,
                version=t.version,
            )
        return None
```

### 2. Prompt Engine (Strategy Pattern)

```python
# backend/app/core/translation/pipeline/prompt_engine.py

from abc import ABC, abstractmethod
from typing import Dict, Type

from ..models.context import TranslationContext, TranslationMode
from ..models.prompt import PromptBundle, Message


class PromptStrategy(ABC):
    """Base class for mode-specific prompt building"""

    @abstractmethod
    def build(self, context: TranslationContext) -> PromptBundle:
        """Build prompt bundle from context"""
        pass

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation"""
        return len(text) // 4


class DirectTranslationStrategy(PromptStrategy):
    """Simple direct translation"""

    SYSTEM_TEMPLATE = """You are a professional translator specializing in {target_language} translation.

Translate the following text accurately while:
- Preserving the original meaning and tone
- Using natural, fluent {target_language}
- Maintaining any formatting in the source

Output ONLY the translated text, nothing else."""

    def build(self, context: TranslationContext) -> PromptBundle:
        system_prompt = self.SYSTEM_TEMPLATE.format(
            target_language=context.target_language
        )

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=context.source.text),
        ]

        return PromptBundle(
            messages=messages,
            temperature=0.3,
            mode="direct",
            estimated_input_tokens=self.estimate_tokens(
                system_prompt + context.source.text
            ),
        )


class AuthorAwareStrategy(PromptStrategy):
    """Style-preserving translation with author context"""

    SYSTEM_TEMPLATE = """You are a professional literary translator with expertise in preserving authorial voice.

## Author Context
{author_context}

## Translation Guidelines
{guidelines}

## Output Requirements
- Preserve the author's unique writing style
- Use terminology consistent with the author's works
- Output ONLY the translated text"""

    def build(self, context: TranslationContext) -> PromptBundle:
        # Build author context section
        author_context = self._build_author_section(context)

        # Build guidelines section
        guidelines = self._build_guidelines(context)

        system_prompt = self.SYSTEM_TEMPLATE.format(
            author_context=author_context,
            guidelines=guidelines,
        )

        # Build user prompt with adjacent context
        user_prompt = self._build_user_prompt(context)

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        return PromptBundle(
            messages=messages,
            temperature=0.3,
            mode="author_aware",
            estimated_input_tokens=self.estimate_tokens(
                system_prompt + user_prompt
            ),
        )

    def _build_author_section(self, context: TranslationContext) -> str:
        if not context.book_analysis:
            return "No author information available."

        ba = context.book_analysis
        sections = []

        if ba.author_name:
            sections.append(f"Author: {ba.author_name}")
        if ba.author_biography:
            sections.append(f"Background: {ba.author_biography}")
        if ba.writing_style:
            sections.append(f"Writing Style: {ba.writing_style}")
        if ba.tone:
            sections.append(f"Tone: {ba.tone}")

        return "\n".join(sections) if sections else "No author information available."

    def _build_guidelines(self, context: TranslationContext) -> str:
        guidelines = [
            "- Maintain accuracy while prioritizing natural flow",
            "- Use modern, standard Chinese expressions",
        ]

        if context.book_analysis and context.book_analysis.key_terminology:
            guidelines.append("- Follow terminology mappings:")
            for en, zh in context.book_analysis.key_terminology.items():
                guidelines.append(f"  - {en} → {zh}")

        if context.book_analysis and context.book_analysis.custom_guidelines:
            guidelines.extend([
                f"- {g}" for g in context.book_analysis.custom_guidelines
            ])

        return "\n".join(guidelines)

    def _build_user_prompt(self, context: TranslationContext) -> str:
        parts = []

        # Add adjacent context if available
        if context.adjacent:
            if context.adjacent.previous_original:
                parts.append(f"[Previous paragraph (for context)]\n{context.adjacent.previous_original}")
                if context.adjacent.previous_translation:
                    parts.append(f"[Previous translation]\n{context.adjacent.previous_translation}")
                parts.append("")

        parts.append(f"[Translate this paragraph]\n{context.source.text}")

        return "\n".join(parts)


class OptimizationStrategy(PromptStrategy):
    """Improve existing translation"""

    SYSTEM_TEMPLATE = """You are a Chinese language expert specializing in translation refinement.

Your task is to improve an existing translation by:
- Updating outdated or unnatural expressions
- Improving fluency and readability
- Correcting any inaccuracies
- Preserving the original meaning

Output ONLY the improved translation."""

    def build(self, context: TranslationContext) -> PromptBundle:
        if not context.existing:
            raise ValueError("Optimization mode requires existing translation")

        user_prompt = f"""[Original English]
{context.source.text}

[Current Translation]
{context.existing.text}

[Your improved translation]"""

        messages = [
            Message(role="system", content=self.SYSTEM_TEMPLATE),
            Message(role="user", content=user_prompt),
        ]

        return PromptBundle(
            messages=messages,
            temperature=0.3,
            mode="optimization",
            estimated_input_tokens=self.estimate_tokens(
                self.SYSTEM_TEMPLATE + user_prompt
            ),
        )


class IterativeStrategy(PromptStrategy):
    """Multi-pass refinement with chain-of-thought"""

    STEP1_SYSTEM = """You are a translator. First, create a literal translation.
Output format:
<literal>
Your literal translation here
</literal>"""

    STEP2_SYSTEM = """You are a translation editor. Given a literal translation,
make it natural and fluent while preserving meaning.
Output ONLY the refined translation."""

    def build(self, context: TranslationContext, step: int = 1) -> PromptBundle:
        if step == 1:
            return self._build_step1(context)
        else:
            return self._build_step2(context)

    def _build_step1(self, context: TranslationContext) -> PromptBundle:
        messages = [
            Message(role="system", content=self.STEP1_SYSTEM),
            Message(role="user", content=context.source.text),
        ]
        return PromptBundle(messages=messages, mode="iterative_step1")

    def _build_step2(self, context: TranslationContext) -> PromptBundle:
        # This would receive the literal translation from step 1
        # as part of the context (via existing.text or similar)
        pass


class PromptEngine:
    """
    Factory and router for prompt strategies.
    Single responsibility: Strategy selection and prompt building.
    """

    _strategies: Dict[TranslationMode, Type[PromptStrategy]] = {
        TranslationMode.DIRECT: DirectTranslationStrategy,
        TranslationMode.AUTHOR_AWARE: AuthorAwareStrategy,
        TranslationMode.OPTIMIZATION: OptimizationStrategy,
        TranslationMode.ITERATIVE: IterativeStrategy,
    }

    @classmethod
    def register_strategy(
        cls, mode: TranslationMode, strategy: Type[PromptStrategy]
    ):
        """Register custom strategy"""
        cls._strategies[mode] = strategy

    @classmethod
    def build(cls, context: TranslationContext) -> PromptBundle:
        """Build prompt bundle for given context"""
        # Validate context
        context.validate_for_mode()

        # Handle custom prompts override
        if context.custom_system_prompt or context.custom_user_prompt:
            return cls._build_custom(context)

        # Get strategy for mode
        strategy_class = cls._strategies.get(context.mode)
        if not strategy_class:
            raise ValueError(f"No strategy registered for mode: {context.mode}")

        strategy = strategy_class()
        return strategy.build(context)

    @classmethod
    def _build_custom(cls, context: TranslationContext) -> PromptBundle:
        """Build prompt with custom overrides"""
        messages = []

        if context.custom_system_prompt:
            messages.append(Message(role="system", content=context.custom_system_prompt))

        user_content = context.custom_user_prompt or context.source.text
        # Replace {{source_text}} placeholder if present
        user_content = user_content.replace("{{source_text}}", context.source.text)
        messages.append(Message(role="user", content=user_content))

        return PromptBundle(
            messages=messages,
            mode="custom",
        )
```

### 3. LLM Gateway (Unified Provider Access)

```python
# backend/app/core/translation/pipeline/llm_gateway.py

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any
import time

from ..models.prompt import PromptBundle
from ..models.response import LLMResponse, TokenUsage


class LLMGateway(ABC):
    """
    Abstract gateway for LLM providers.
    Single responsibility: LLM communication.
    """

    @abstractmethod
    async def call(self, bundle: PromptBundle) -> LLMResponse:
        """Synchronous call returning full response"""
        pass

    @abstractmethod
    async def stream(self, bundle: PromptBundle) -> AsyncIterator[LLMResponse]:
        """Streaming call yielding partial responses"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider availability"""
        pass


class OpenAIGateway(LLMGateway):
    """OpenAI-compatible gateway"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
    ):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.provider = "openai"

    async def call(self, bundle: PromptBundle) -> LLMResponse:
        start_time = time.time()

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=bundle.to_openai_format(),
            temperature=bundle.temperature,
            max_tokens=bundle.max_tokens,
            response_format=bundle.response_format,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content,
            provider=self.provider,
            model=self.model,
            usage=TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            latency_ms=latency_ms,
            raw_response=response.model_dump(),
        )

    async def stream(self, bundle: PromptBundle) -> AsyncIterator[LLMResponse]:
        start_time = time.time()
        accumulated_content = ""
        chunk_index = 0

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=bundle.to_openai_format(),
            temperature=bundle.temperature,
            max_tokens=bundle.max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                delta = chunk.choices[0].delta.content
                accumulated_content += delta

                yield LLMResponse(
                    content=delta,
                    provider=self.provider,
                    model=self.model,
                    latency_ms=int((time.time() - start_time) * 1000),
                    is_complete=False,
                    chunk_index=chunk_index,
                )
                chunk_index += 1

        # Final chunk with complete content
        yield LLMResponse(
            content=accumulated_content,
            provider=self.provider,
            model=self.model,
            latency_ms=int((time.time() - start_time) * 1000),
            is_complete=True,
            chunk_index=chunk_index,
        )

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False


class AnthropicGateway(LLMGateway):
    """Anthropic Claude gateway"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.provider = "anthropic"

    async def call(self, bundle: PromptBundle) -> LLMResponse:
        start_time = time.time()
        system, messages = bundle.to_anthropic_format()

        response = await self.client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=bundle.max_tokens,
            temperature=bundle.temperature,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return LLMResponse(
            content=response.content[0].text,
            provider=self.provider,
            model=self.model,
            usage=TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
            latency_ms=latency_ms,
        )

    async def stream(self, bundle: PromptBundle) -> AsyncIterator[LLMResponse]:
        # Similar streaming implementation
        pass

    async def health_check(self) -> bool:
        try:
            # Anthropic doesn't have a list endpoint, use minimal completion
            return True
        except Exception:
            return False


class GatewayFactory:
    """Factory for creating LLM gateways"""

    @staticmethod
    def create(
        provider: str,
        api_key: str,
        model: str,
        **kwargs
    ) -> LLMGateway:
        if provider == "openai":
            return OpenAIGateway(api_key=api_key, model=model, **kwargs)
        elif provider == "anthropic":
            return AnthropicGateway(api_key=api_key, model=model)
        elif provider == "deepseek":
            return OpenAIGateway(
                api_key=api_key,
                model=model,
                base_url="https://api.deepseek.com/v1",
            )
        elif provider == "qwen":
            return OpenAIGateway(
                api_key=api_key,
                model=model,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")
```

### 4. Output Processor

```python
# backend/app/core/translation/pipeline/output_processor.py

from typing import Optional, List
import re

from ..models.response import LLMResponse
from ..models.result import TranslationResult, QualityFlag
from ..models.context import TranslationContext


class OutputProcessor:
    """
    Processes raw LLM response into final translation result.
    Single responsibility: Output validation and transformation.
    """

    def process(
        self,
        response: LLMResponse,
        context: TranslationContext,
    ) -> TranslationResult:
        """Process raw LLM response into translation result"""

        # 1. Extract translation text
        translated_text = self._extract_translation(response.content)

        # 2. Validate output
        quality_flag, confidence = self._assess_quality(
            translated_text, context
        )

        # 3. Post-process text
        translated_text = self._post_process(translated_text, context)

        # 4. Build result
        return TranslationResult(
            translated_text=translated_text,
            quality_flag=quality_flag,
            confidence_score=confidence,
            mode_used=context.mode.value,
            provider=response.provider,
            model=response.model,
            tokens_used=response.usage.total_tokens,
            estimated_cost_usd=response.usage.estimated_cost_usd,
            raw_llm_response=response.content,
        )

    def _extract_translation(self, content: str) -> str:
        """Extract translation from response, handling various formats"""
        content = content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        # Handle XML-like tags (e.g., <translation>...</translation>)
        match = re.search(r"<translation>(.*?)</translation>", content, re.DOTALL)
        if match:
            content = match.group(1).strip()

        # Handle literal tags (e.g., <literal>...</literal>)
        match = re.search(r"<literal>(.*?)</literal>", content, re.DOTALL)
        if match:
            content = match.group(1).strip()

        return content

    def _assess_quality(
        self,
        translated: str,
        context: TranslationContext,
    ) -> tuple[QualityFlag, float]:
        """Assess translation quality"""
        confidence = 1.0
        flag = QualityFlag.CONFIDENT

        # Check length ratio (Chinese is typically 0.5-0.8x English length)
        ratio = len(translated) / len(context.source.text) if context.source.text else 0
        if ratio < 0.3 or ratio > 1.5:
            flag = QualityFlag.NEEDS_REVIEW
            confidence *= 0.7

        # Check for untranslated English chunks
        english_pattern = r"[a-zA-Z]{10,}"
        if re.search(english_pattern, translated):
            flag = QualityFlag.UNCERTAIN
            confidence *= 0.8

        # Check if formatting might be lost
        if ("\n" in context.source.text) != ("\n" in translated):
            if flag == QualityFlag.CONFIDENT:
                flag = QualityFlag.FORMATTING_LOST

        return flag, confidence

    def _post_process(
        self,
        text: str,
        context: TranslationContext,
    ) -> str:
        """Apply post-processing transformations"""

        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        # Preserve formatting if requested
        if context.preserve_formatting:
            # Restore paragraph breaks based on source
            source_breaks = context.source.text.count("\n\n")
            current_breaks = text.count("\n\n")

            if source_breaks > 0 and current_breaks == 0:
                # Attempt to restore paragraph structure
                # (simplified - real implementation would be smarter)
                pass

        return text
```

### 5. Translation Pipeline (Orchestrator)

```python
# backend/app/core/translation/pipeline/pipeline.py

from typing import Optional, AsyncIterator
from dataclasses import dataclass

from .context_builder import ContextBuilder
from .prompt_engine import PromptEngine
from .llm_gateway import LLMGateway, GatewayFactory
from .output_processor import OutputProcessor
from ..models.context import TranslationContext, TranslationMode
from ..models.result import TranslationResult
from ..models.response import LLMResponse


@dataclass
class PipelineConfig:
    """Pipeline configuration"""
    provider: str
    model: str
    api_key: str
    mode: TranslationMode = TranslationMode.DIRECT
    stream: bool = False
    max_retries: int = 3


class TranslationPipeline:
    """
    Main orchestrator for the translation pipeline.
    Composes all components into a unified flow.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.gateway = GatewayFactory.create(
            provider=config.provider,
            api_key=config.api_key,
            model=config.model,
        )
        self.output_processor = OutputProcessor()

    async def translate(
        self,
        context: TranslationContext,
    ) -> TranslationResult:
        """
        Execute the full translation pipeline.

        Flow:
        Context → PromptEngine → PromptBundle → Gateway → LLMResponse → OutputProcessor → Result
        """
        # 1. Build prompt from context
        prompt_bundle = PromptEngine.build(context)

        # 2. Call LLM
        response = await self.gateway.call(prompt_bundle)

        # 3. Process output
        result = self.output_processor.process(response, context)

        return result

    async def translate_stream(
        self,
        context: TranslationContext,
    ) -> AsyncIterator[str]:
        """
        Streaming translation for real-time UI updates.
        Yields partial translation chunks.
        """
        prompt_bundle = PromptEngine.build(context)

        async for chunk in self.gateway.stream(prompt_bundle):
            yield chunk.content

    async def translate_iterative(
        self,
        context: TranslationContext,
        steps: int = 2,
    ) -> TranslationResult:
        """
        Multi-step translation with chain-of-thought.

        Step 1: Literal translation
        Step 2: Refinement
        """
        from ..models.context import ExistingTranslation

        # Force iterative mode
        context.mode = TranslationMode.ITERATIVE

        # Step 1: Initial translation
        step1_context = context.model_copy()
        step1_prompt = PromptEngine.build(step1_context)
        step1_response = await self.gateway.call(step1_prompt)

        # Extract literal translation
        literal = self.output_processor._extract_translation(step1_response.content)

        # Step 2: Refinement
        step2_context = context.model_copy()
        step2_context.mode = TranslationMode.OPTIMIZATION
        step2_context.existing = ExistingTranslation(
            text=literal,
            provider=self.config.provider,
            model=self.config.model,
            version=1,
        )

        step2_prompt = PromptEngine.build(step2_context)
        step2_response = await self.gateway.call(step2_prompt)

        # Process final result
        result = self.output_processor.process(step2_response, step2_context)
        result.step_index = 2
        result.total_steps = 2

        return result
```

---

## Usage Example

```python
# Example: Translating a paragraph with full context

from app.core.translation.pipeline import (
    TranslationPipeline,
    PipelineConfig,
    ContextBuilder,
)
from app.core.translation.models.context import TranslationMode

async def translate_paragraph(
    session: AsyncSession,
    paragraph_id: int,
    project_id: int,
    provider: str,
    model: str,
    api_key: str,
):
    # 1. Load entities
    paragraph = await session.get(Paragraph, paragraph_id)
    project = await session.get(Project, project_id, options=[
        selectinload(Project.analysis)
    ])

    # 2. Build context
    context_builder = ContextBuilder(session)
    context = await context_builder.build(
        paragraph=paragraph,
        project=project,
        mode=TranslationMode.AUTHOR_AWARE,
        include_adjacent=True,
    )

    # 3. Create pipeline
    config = PipelineConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        mode=TranslationMode.AUTHOR_AWARE,
    )
    pipeline = TranslationPipeline(config)

    # 4. Execute translation
    result = await pipeline.translate(context)

    # 5. Save result
    translation = Translation(
        paragraph_id=paragraph_id,
        translated_text=result.translated_text,
        mode=result.mode_used,
        provider=result.provider,
        model=result.model,
        tokens_used=result.tokens_used,
    )
    session.add(translation)
    await session.commit()

    return result
```

---

## Migration Path

### Phase 1: Core Models (Week 1)
1. Create new data models in `backend/app/core/translation/models/`
2. Add unit tests for model validation
3. No breaking changes to existing code

### Phase 2: Pipeline Components (Week 2)
1. Implement ContextBuilder
2. Implement PromptEngine with strategies
3. Implement LLMGateway implementations
4. Implement OutputProcessor
5. Add integration tests

### Phase 3: Pipeline Orchestrator (Week 3)
1. Implement TranslationPipeline
2. Create new orchestrator using pipeline
3. Run parallel with old orchestrator
4. A/B testing for quality comparison

### Phase 4: Migration (Week 4)
1. Deprecate old adapter-based flow
2. Update API routes to use new pipeline
3. Remove legacy code
4. Documentation update

---

## Benefits

### 1. Clear Data Contracts
- Each layer has explicit input/output types
- Pydantic validation at every boundary
- Easy to test and mock

### 2. Extensibility
- New translation modes = new PromptStrategy
- New providers = new LLMGateway implementation
- No modification to existing code

### 3. Testability
- Each component can be unit tested independently
- Mock any layer for integration testing
- Clear dependency injection points

### 4. Observability
- Token usage tracked at every step
- Quality flags for monitoring
- Latency metrics built-in

### 5. Advanced Features Enabled
- Multi-step iterative translation
- Streaming with progress
- Quality-based auto-retry
- A/B testing different strategies

---

## File Structure

```
backend/app/core/translation/
├── models/
│   ├── __init__.py
│   ├── context.py          # TranslationContext, SourceMaterial, etc.
│   ├── prompt.py           # PromptBundle, Message
│   ├── response.py         # LLMResponse, TokenUsage
│   └── result.py           # TranslationResult, QualityFlag
├── pipeline/
│   ├── __init__.py
│   ├── context_builder.py  # ContextBuilder
│   ├── prompt_engine.py    # PromptEngine, strategies
│   ├── llm_gateway.py      # LLMGateway, implementations
│   ├── output_processor.py # OutputProcessor
│   └── pipeline.py         # TranslationPipeline
├── strategies/
│   ├── __init__.py
│   ├── direct.py
│   ├── author_aware.py
│   ├── optimization.py
│   └── iterative.py
└── orchestrator.py         # High-level task orchestrator (uses pipeline)
```
