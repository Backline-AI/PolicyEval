"""Abstract base class for all LLM interactions."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLM(ABC):
    """Base interface for any LLM call.

    Returns raw text from :meth:`complete` / :meth:`complete_sync`.
    This is the root contract for all LLM interactions in PolicyEval --
    evaluation, generation, and extraction all build on top of this.

    Concrete implementations supply the transport layer (OpenAI SDK,
    LiteLLM proxy, etc.).  Higher-level abstractions like
    :class:`~policyeval.judges.base.LLMJudge` add structured output
    semantics on top.
    """

    @abstractmethod
    async def complete(self, system_prompt: str, prompt: str) -> str:
        """Send a chat completion request asynchronously and return raw text.

        Args:
            system_prompt: System-turn content that sets context and persona.
            prompt: User-turn content.

        Returns:
            The model's response as a plain string.
        """
        ...

    @abstractmethod
    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        """Synchronous variant of :meth:`complete`.

        Args:
            system_prompt: System-turn content.
            prompt: User-turn content.

        Returns:
            The model's response as a plain string.
        """
        ...
