"""Model builders: the only place a chat model is made.

No provider is installed yet. Until a requirement names one, the registered
graph runs on an offline model -- a walking skeleton, not an assistant anyone
uses (docs/decisions/0005).
"""

from __future__ import annotations

import itertools

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

OFFLINE_ANSWER = (
    "This is the starter's offline model: no provider is configured, so every "
    "message gets this same answer (docs/decisions/0005)."
)


def build_offline_model() -> BaseChatModel:
    """A model that reaches no network and answers every message the same way.

    A string, repeated, rather than one AIMessage: the fake turns each string into
    a fresh message, so no two answers share an id -- a reused message would
    replace the earlier answer in a thread's history instead of following it.
    """
    return GenericFakeChatModel(messages=itertools.repeat(OFFLINE_ANSWER))
