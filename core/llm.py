import os
from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI

_featherless_client: AsyncOpenAI | None = None


def get_aiml_llm(temperature: float = 0) -> ChatOpenAI:
    """LangChain LLM backed by AI/ML API — used as the agent brain for all 3 agents."""
    return ChatOpenAI(
        base_url="https://api.aimlapi.com/v1",
        api_key=os.environ["AIML_API_KEY"],
        model=os.environ.get("AIML_MODEL", "openai/gpt-4o-mini"),
        temperature=temperature,
    )


def _get_featherless_client() -> AsyncOpenAI:
    global _featherless_client
    if _featherless_client is None:
        _featherless_client = AsyncOpenAI(
            base_url="https://api.featherless.ai/v1",
            api_key=os.environ.get("FEATHERLESS_API_KEY", "placeholder"),
        )
    return _featherless_client


async def featherless_reason(prompt: str) -> str:
    """Direct (non-agentic) open-model call via Featherless for strategic narrative.

    No tool-calling — model choice is low-risk. Keeps orchestration on AI/ML API.
    """
    model = os.environ.get("FEATHERLESS_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    resp = await _get_featherless_client().chat.completions.create(
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
