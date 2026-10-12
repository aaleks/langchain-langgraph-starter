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

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from starter.config.settings import Settings
from starter.domain.agents.budgets import MODEL_CALL_DEADLINE_SECONDS
from starter.domain.agents.retries import is_transient
from starter.domain.models import choose_model

OFFLINE_ANSWER = (
    "This is the starter's offline model: no provider is configured, so every "
    "message gets this same answer (docs/decisions/0005)."
)


def build_model(settings: Settings) -> BaseChatModel:
    """The model the settings choose. Refuses a partial configuration."""
    choice = choose_model(
        settings.openwebui_url, settings.openwebui_api_key, settings.openwebui_model
    )
    if choice == "openwebui":
        return build_openwebui_model(settings)
    return build_offline_model()


def build_openwebui_model(settings: Settings) -> BaseChatModel:
    """An OpenAI-compatible client addressed to Open WebUI's `/api`.

    - `max_retries=0`: the openai client would otherwise retry twice on its own,
      under the assistant's policy (ModelRetryMiddleware in the factory).
    - `use_responses_api=False`: some model ids switch ChatOpenAI to
      `/responses`, which Open WebUI does not serve.
    - `base_url` and `api_key` explicit: left out, langchain-core may route a
      ChatOpenAI through LangSmith's gateway (`LANGSMITH_GATEWAY`) -- never here.
    """
    from langchain_openai import ChatOpenAI  # the provider, only when chosen

    return ChatOpenAI(
        base_url=settings.openwebui_url.rstrip("/") + "/api",
        api_key=settings.openwebui_api_key,
        model=settings.openwebui_model,
        timeout=MODEL_CALL_DEADLINE_SECONDS,
        max_retries=0,
        use_responses_api=False,
    )


def build_offline_model() -> BaseChatModel:
    """A model that reaches no network and answers every message the same way.

    A string, repeated, rather than one AIMessage: the fake turns each string into
    a fresh message, so no two answers share an id -- a reused message would
    replace the earlier answer in a thread's history instead of following it.
    """
    return GenericFakeChatModel(messages=itertools.repeat(OFFLINE_ANSWER))


def is_transient_failure(failure: Exception) -> bool:
    """Whether the domain's retry policy would try this failed model call again.

    Reads the openai client's exceptions -- the ones Open WebUI's errors arrive
    as -- into facts. Imported lazily: with the offline model, openai is never
    needed, and nothing it raises is transient.
    """
    try:
        import openai
    except ImportError:
        return False
    status = failure.status_code if isinstance(failure, openai.APIStatusError) else None
    return is_transient(
        status=status,
        timed_out=isinstance(failure, openai.APITimeoutError),
        connection_failed=isinstance(failure, openai.APIConnectionError)
        and not isinstance(failure, openai.APITimeoutError),
    )
