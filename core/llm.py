import os
from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI

_aiml_client: AsyncOpenAI | None = None


def get_aiml_llm(temperature: float = 0) -> ChatOpenAI:
    """LangChain LLM backed by AI/ML API — used as the agent brain for all 3 agents."""
    return ChatOpenAI(
        base_url="https://api.aimlapi.com/v1",
        api_key=os.environ["AIML_API_KEY"],
        model=os.environ.get("AIML_MODEL", "openai/gpt-4o-mini"),
        temperature=temperature,
    )


def _get_aiml_client() -> AsyncOpenAI:
    global _aiml_client
    if _aiml_client is None:
        _aiml_client = AsyncOpenAI(
            base_url="https://api.aimlapi.com/v1",
            api_key=os.environ.get("AIML_API_KEY", "placeholder"),
        )
    return _aiml_client


async def aiml_reason(prompt: str) -> str:
    """Direct (non-agentic) AI/ML API call for the Analyst's strategic narrative.

    No tool-calling — a bounded, single-shot reasoning call. Uses the same AI/ML
    API that powers the agent brains, keeping the whole stack on one provider.
    """
    model = os.environ.get("AIML_MODEL", "openai/gpt-4o-mini")
    resp = await _get_aiml_client().chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a senior pricing strategist. Be concise and decisive.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=400,
    )
    return resp.choices[0].message.content
