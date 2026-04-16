"""Knowledge base — backward-compatible re-exports."""

from orqestra.capabilities.kb_capabilities import (
    create_kb_capabilities,
    get_personal_knowledge_base,
    init_knowledge_base,
    init_personal_knowledge_base,
    kb_delete,
    kb_list,
    kb_read,
    kb_related,
    kb_search,
    kb_write,
    my_kb_delete,
    my_kb_list,
    my_kb_related,
    my_kb_write,
)
from orqestra.capabilities.kb_core import KnowledgeBase

__all__ = [
    "KnowledgeBase",
    "create_kb_capabilities",
    "get_personal_knowledge_base",
    "init_knowledge_base",
    "init_personal_knowledge_base",
    "kb_delete",
    "kb_list",
    "kb_read",
    "kb_related",
    "kb_search",
    "kb_write",
    "my_kb_delete",
    "my_kb_list",
    "my_kb_related",
    "my_kb_write",
]
