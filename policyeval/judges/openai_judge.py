"""OpenAI-compatible LLM judge implementation.

Works with the standard OpenAI API and any OpenAI-compatible proxy such as
LiteLLM, Azure OpenAI, or self-hosted endpoints.
"""

from __future__ import annotations

import json
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from policyeval.judges.base import LLMJudge
from policyeval.llm.openai import OpenAILLM

_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_JUDGE_TEMPERATURE = 0.0
_DEFAULT_SEED = 42


class OpenAIJudge(LLMJudge):
    """LLM judge backed by the OpenAI chat completions API.

    Because it uses the standard ``openai`` SDK, it works with any
    OpenAI-compatible endpoint – pass ``base_url`` to target LiteLLM,
    Azure OpenAI, or a local model proxy.

    ``complete`` / ``complete_sync`` return raw text (delegated to an
    internal :class:`~policyeval.llm.openai.OpenAILLM`).

    ``evaluate`` / ``evaluate_sync`` add JSON-mode and deterministic
    sampling on top (``temperature=0``, ``seed=42``,
    ``response_format=json_object``).

    Args:
        model: Model identifier (default: ``"gpt-4o"``).
        temperature: Sampling temperature for *evaluation* calls. Use
            ``0.0`` for deterministic results (default).
        seed: Seed for deterministic sampling (default: ``42``).
        api_key: Optional OpenAI API key.  Falls back to the
            ``OPENAI_API_KEY`` environment variable.
        base_url: Optional base URL to route requests through an
            OpenAI-compatible proxy (e.g. LiteLLM).
        max_retries: Number of retry attempts on transient failures.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        temperature: float = _DEFAULT_JUDGE_TEMPERATURE,
        seed: int = _DEFAULT_SEED,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 3,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.max_retries = max_retries
        self._api_key = api_key
        self._base_url = base_url

        # Delegate raw-text completions to OpenAILLM
        self._llm = OpenAILLM(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
        )

    # ------------------------------------------------------------------
    # LLM interface (raw text, delegates to OpenAILLM)
    # ------------------------------------------------------------------

    async def complete(self, system_prompt: str, prompt: str) -> str:
        """Complete a prompt asynchronously and return raw text."""
        return await self._llm.complete(system_prompt, prompt)

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        """Complete a prompt synchronously and return raw text."""
        return self._llm.complete_sync(system_prompt, prompt)

    # ------------------------------------------------------------------
    # Judge interface (JSON output, deterministic sampling)
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def evaluate(self, system_prompt: str, prompt: str) -> dict:
        """Evaluate asynchronously using the OpenAI chat completions API."""
        client = self._llm._get_async_client()
        response = await client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            seed=self.seed,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        """Evaluate synchronously using the OpenAI chat completions API."""
        client = self._llm._get_sync_client()
        response = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            seed=self.seed,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
