"""Abstract base class for LLM judge implementations."""

from __future__ import annotations

from abc import abstractmethod

from policyeval.llm.base import LLM


class LLMJudge(LLM):
    """LLM specialized for structured JSON evaluation.

    Extends :class:`~policyeval.llm.base.LLM` with evaluation-specific
    methods that return parsed JSON dictionaries instead of raw text.
    Concrete implementations (e.g.
    :class:`~policyeval.judges.openai_judge.OpenAIJudge`) must provide
    both a sync and an async variant.

    The ``evaluate`` methods accept a ``system_prompt`` (the judge persona
    established at call time) and a ``prompt`` (the user-turn content), and
    return a parsed JSON dictionary.
    """

    @abstractmethod
    async def evaluate(self, system_prompt: str, prompt: str) -> dict:
        """Evaluate a prompt asynchronously and return a parsed JSON dict.

        Args:
            system_prompt: System-turn content that sets the judge's context
                and persona.  Typically supplied by the evaluation engine.
            prompt: User-turn content containing the policy, input, and output.

        Returns:
            A Python dict parsed from the LLM's JSON response.
        """
        ...

    @abstractmethod
    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        """Synchronous variant of :meth:`evaluate`.

        Args:
            system_prompt: System-turn content.
            prompt: User-turn content.

        Returns:
            A Python dict parsed from the LLM's JSON response.
        """
        ...
