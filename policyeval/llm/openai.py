"""OpenAI-compatible LLM implementation.

Works with the standard OpenAI API and any OpenAI-compatible proxy such as
LiteLLM, Azure OpenAI, or self-hosted endpoints.  Pass ``base_url`` to route
requests through any such proxy.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from policyeval.llm.base import LLM

_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_TEMPERATURE = 0.7


class OpenAILLM(LLM):
    """LLM backed by the OpenAI chat completions API.

    Because it uses the standard ``openai`` SDK it works with any
    OpenAI-compatible endpoint.  Pass ``base_url`` to target a LiteLLM
    proxy, Azure OpenAI, or a local model server.

    Args:
        model: Model identifier (default: ``"gpt-4o"``).
        temperature: Sampling temperature (default: ``0.7``).
        api_key: Optional API key.  Falls back to the ``OPENAI_API_KEY``
            environment variable.
        base_url: Optional base URL for an OpenAI-compatible proxy
            (e.g. a LiteLLM server at ``http://localhost:4000``).
        max_retries: Number of retry attempts on transient failures
            (default: ``3``).
        **default_kwargs: Extra keyword arguments forwarded to every
            ``chat.completions.create`` call (e.g. ``seed``, ``top_p``).

    Examples::

        # Standard OpenAI
        llm = OpenAILLM(model="gpt-4o")

        # LiteLLM proxy (Anthropic, Gemini, local models, …)
        llm = OpenAILLM(
            model="anthropic/claude-3-opus",
            base_url="http://localhost:4000",
        )

        # Azure OpenAI
        llm = OpenAILLM(
            model="gpt-4o",
            base_url="https://<resource>.openai.azure.com/",
            api_key="<azure-key>",
        )
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        temperature: float = _DEFAULT_TEMPERATURE,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        **default_kwargs: Any,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._api_key = api_key
        self._base_url = base_url
        self._default_kwargs = default_kwargs
        self._async_client: Optional[object] = None
        self._sync_client: Optional[object] = None

    # ------------------------------------------------------------------
    # Client factories (lazy, cached)
    # ------------------------------------------------------------------

    def _get_async_client(self):
        if self._async_client is None:
            from openai import AsyncOpenAI

            kwargs: dict = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._async_client = AsyncOpenAI(**kwargs)
        return self._async_client

    def _get_sync_client(self):
        if self._sync_client is None:
            from openai import OpenAI

            kwargs: dict = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._sync_client = OpenAI(**kwargs)
        return self._sync_client

    # ------------------------------------------------------------------
    # LLM interface
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def complete(self, system_prompt: str, prompt: str) -> str:
        """Complete a prompt asynchronously and return raw text."""
        client = self._get_async_client()
        response = await client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            **self._default_kwargs,
        )
        return response.choices[0].message.content or ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        """Complete a prompt synchronously and return raw text."""
        client = self._get_sync_client()
        response = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            **self._default_kwargs,
        )
        return response.choices[0].message.content or ""

    def _complete_sync_from_async(self, system_prompt: str, prompt: str) -> str:
        """Run the async complete in a new event loop (for sync callers in async contexts)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run, self.complete(system_prompt, prompt)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.complete(system_prompt, prompt))
        except RuntimeError:
            return asyncio.run(self.complete(system_prompt, prompt))
