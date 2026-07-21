import re

from src.services.llm import LLMClient

JUDGE_SYSTEM_PROMPT = (
    "You are an evaluator scoring whether an AI-generated answer is faithful to "
    "the context it was given. Faithful means every factual claim in the answer "
    "is actually supported by the context, with no fabricated or unsupported "
    "claims. Respond with ONLY a single integer from 1 to 5, where 1 means the "
    "answer contains claims with no support in the context, and 5 means every "
    "claim in the answer is directly supported by the context. Do not explain."
)


def _build_judge_prompt(query: str, context: str, answer: str) -> str:
    return f"Question: {query}\n\nContext:\n{context}\n\nAnswer to evaluate:\n{answer}"


def score_faithfulness(llm_client: LLMClient, query: str, context: str, answer: str) -> int:
    prompt = _build_judge_prompt(query, context, answer)
    response = llm_client.complete(JUDGE_SYSTEM_PROMPT, prompt, max_tokens=10)
    match = re.search(r"[1-5]", response)
    if not match:
        raise ValueError(f"Judge response unparseable as a 1-5 score: {response!r}")
    return int(match.group())
