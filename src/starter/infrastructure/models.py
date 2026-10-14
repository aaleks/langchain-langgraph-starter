"""Model builders: the only place a chat model is made.

The settings choose the model (domain/models.py): the owner's local Open WebUI,
through its OpenAI-compatible API, when `.env` configures it; otherwise the
offline model -- a walking skeleton's fixed answer, reaching no network
(docs/decisions/0005). This module also reads a provider's failures into the
facts the domain's retry policy decides on, so nothing beyond it knows the
provider's exception types.
"""

from __future__ import annotations

import itertools
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from starter.config.settings import Settings
from starter.domain.agents.budgets import MODEL_CALL_TIMEOUT_SECONDS, MODEL_OUTPUT_TOKENS
from starter.domain.agents.retries import is_transient
from starter.domain.models import api_base, choose_model

OFFLINE_ANSWER = (
    "This is the starter's offline model: no provider is configured, so every "
    "message gets this same answer (docs/decisions/0005)."
)


def build_model(settings: Settings) -> BaseChatModel:
    """The model the settings choose. Refuses a partial or malformed configuration."""
    choice = choose_model(
        settings.openwebui_url, settings.openwebui_api_key, settings.openwebui_model
    )
    if choice == "openwebui":
        return build_openwebui_model(settings)
    return build_offline_model()


def build_openwebui_model(settings: Settings) -> BaseChatModel:
    """An OpenAI-compatible client addressed to Open WebUI's `/api`.

    - `timeout` and `stream_chunk_timeout`: the domain's wait. A call carrying
      tools is not streamed (`disable_streaming`, below), so for it the wait is
      the whole reply; a call without tools streams, and the chunk timer -- else
      langchain-openai's own -- applies to each chunk.
    - `max_retries=0`: the openai client would otherwise retry twice on its own,
      under the assistant's policy (ModelRetryMiddleware in the factory).
    - `use_responses_api=False`: some model ids switch ChatOpenAI to
      `/responses`, which Open WebUI does not serve.
    - `base_url` and `api_key` explicit: left out, langchain-core may route a
      ChatOpenAI through LangSmith's gateway (`LANGSMITH_GATEWAY`) -- never here.

    The client still reads the owner's `OPENAI_*` variables it is not given
    here (a proxy, an organisation): the owner's shell, the owner's choice.
    """
    from langchain_openai import ChatOpenAI  # the provider, only when chosen

    return ChatOpenAI(
        base_url=api_base(settings.openwebui_url),
        api_key=settings.openwebui_api_key,
        model=settings.openwebui_model,
        timeout=MODEL_CALL_TIMEOUT_SECONDS,
        stream_chunk_timeout=MODEL_CALL_TIMEOUT_SECONDS,
        # Open WebUI honours it: a capped reply comes back with finish_reason
        # `length` (checked on the owner's server); ASSISTANT-OUTPUT-BUDGET.
        max_tokens=MODEL_OUTPUT_TOKENS,
        # A streamed call's arguments are re-parsed at every chunk, worse than
        # linearly: 2,000 characters that never repair took 3.2 s, blocking the
        # server (measured). The assistant's calls always carry tools.
        disable_streaming="tool_calling",
        max_retries=0,
        use_responses_api=False,
    )


def build_offline_model() -> BaseChatModel:
    """A model that reaches no network and answers every message the same way.

    A string, repeated, rather than one AIMessage: the fake turns each string into
    a fresh message, so no two answers share an id -- a reused message would
    replace the earlier answer in a thread's history instead of following it.
    """
    return OfflineChatModel(messages=itertools.repeat(OFFLINE_ANSWER))


class OfflineChatModel(GenericFakeChatModel):
    """The fake, able to be offered tools: the assistant now has some, and the
    stock fake's `bind_tools` raises NotImplementedError. Offered or not, it
    proposes no call -- it only answers."""

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> Any:
        return self


def is_transient_failure(failure: Exception) -> bool:
    """Whether the domain's retry policy would try this failed model call again.

    Reads the failure into facts: the openai client's exceptions -- the ones
    Open WebUI's errors arrive as -- and a builtin `TimeoutError`, which is how
    langchain-openai reports a streamed chunk that never came.
    """
    import openai  # with the client it reads; never needed by the offline model

    status = failure.status_code if isinstance(failure, openai.APIStatusError) else None
    timed_out = isinstance(failure, (openai.APITimeoutError, TimeoutError))
    return is_transient(
        status=status,
        timed_out=timed_out,
        # APITimeoutError is an APIConnectionError: counted once, as a timeout.
        connection_failed=isinstance(failure, openai.APIConnectionError) and not timed_out,
    )
