"""OpenAI LLM Adapter - Uses LiteLLM for unified model access."""

from typing import AsyncIterator

from litellm import acompletion

from app.core.llm.adapter import LLMAdapter, TranslationRequest, TranslationResponse


class OpenAIAdapter(LLMAdapter):
    """OpenAI GPT implementation using LiteLLM for consistency."""

    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__(model, api_key, **kwargs)
        self.api_key = api_key
        # Ensure openai/ prefix for proper LiteLLM routing
        if not model.startswith("openai/"):
            self._litellm_model = f"openai/{model}"
        else:
            self._litellm_model = model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        """Perform translation using LiteLLM."""
        system_prompt = self.build_system_prompt(request)
        user_prompt = self.build_user_prompt(request)

        response = await acompletion(
            model=self._litellm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
            api_key=self.api_key,
        )

        return TranslationResponse(
            translated_text=response.choices[0].message.content.strip(),
            tokens_used=response.usage.total_tokens if response.usage else 0,
            model=self.model,
            provider=self.provider_name,
        )

    async def translate_stream(
        self,
        request: TranslationRequest,
    ) -> AsyncIterator[str]:
        """Stream translation for real-time display."""
        system_prompt = self.build_system_prompt(request)
        user_prompt = self.build_user_prompt(request)

        response = await acompletion(
            model=self._litellm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            stream=True,
            api_key=self.api_key,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        """Check if OpenAI is available."""
        try:
            response = await acompletion(
                model=self._litellm_model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                api_key=self.api_key,
            )
            return True
        except Exception:
            return False
