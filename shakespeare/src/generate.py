from typing import List, Dict


PROMPT_TEMPLATE = (
    "System: You are a Shakespearean culture assistant.\n"
    "User: {query}\n"
    "Context:\n{context}\n"
    "Task: Answer the user using the context. Include dates and locations. Avoid speculation.\n"
)


def assemble_context(snippets: List[Dict]) -> str:
    return "\n---\n".join(s.get("text", "") for s in snippets)


def generate_answer(query: str, snippets: List[Dict]) -> str:
    # Offline-friendly dummy response using prompt template
    context = assemble_context(snippets)
    prompt = PROMPT_TEMPLATE.format(query=query, context=context)
    # Minimal heuristic answer; replace with real LLM call if desired
    if not snippets:
        return "I don't have enough indexed data yet. Please run ingestion/embedding."
    return f"Based on the context, here are relevant details for your query: {query}\n\n{context}"

from typing import List, Tuple


def assemble_prompt(user_query: str, contexts: List[str]) -> str:
    context_block = "\n\n".join(contexts)
    return (
        "System: You are a Shakespearean culture assistant.\n"
        f"User: {user_query}\n"
        "Context:\n"
        f"{context_block}\n"
        "Task: Answer the user using the context. Include dates and locations. Avoid speculation.\n"
    )


def simple_generate(user_query: str, top_contexts: List[Tuple[int, float, str]]) -> str:
    if not top_contexts:
        return (
            "I could not find relevant context yet. Please add Shakespeare texts to data/raw/ "
            "or provide more details in your question."
        )
    bullet_points = [f"- {text}" for (_i, _s, text) in top_contexts]
    joined = "\n".join(bullet_points[:5])
    return (
        "Here are the most relevant context snippets I found.\n" +
        joined +
        "\n\nBased on these, please refine your question if needed."
    )

