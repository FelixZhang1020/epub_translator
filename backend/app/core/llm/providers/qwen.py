"""Qwen LLM Adapter via DashScope - Uses LiteLLM for unified model access."""

from typing import AsyncIterator

from litellm import acompletion

from app.core.llm.adapter import LLMAdapter, TranslationRequest, TranslationResponse


class QwenAdapter(LLMAdapter):
    """Qwen implementation using LiteLLM for consistency."""

    DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__(model, api_key, **kwargs)
        self.api_key = api_key
        # For Qwen/DashScope, we strip any dashscope/ prefix and use the base URL
        if model.startswith("dashscope/"):
            self._litellm_model = model.replace("dashscope/", "", 1)
        else:
            self._litellm_model = model

    @property
    def provider_name(self) -> str:
        return "qwen"

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
            api_base=self.DASHSCOPE_BASE_URL,
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
            api_base=self.DASHSCOPE_BASE_URL,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        """Check if Qwen is available."""
        try:
            response = await acompletion(
                model=self._litellm_model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                api_key=self.api_key,
                api_base=self.DASHSCOPE_BASE_URL,
            )
            return True
        except Exception:
            return False
