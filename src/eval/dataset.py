from dataclasses import dataclass
from typing import Literal

# Fixed eval query sets tied to papers known to be ingested during this
# project's development (see specs/07-eval-deploy-readme.md for why a
# fixed set over an auto-generated one). Run `uv run python -m src.ingest`
# with these arXiv IDs first if the corpus is empty:
#   2012.12104v1, 2012.13026v1, 2106.02242v2
EXPECTED_ARXIV_IDS = ["2012.12104v1", "2012.13026v1", "2106.02242v2"]


@dataclass(frozen=True)
class RetrievalCase:
    query: str
    expected_arxiv_id: str


RETRIEVAL_CASES: list[RetrievalCase] = [
    RetrievalCase("How is reinforcement learning used for ramp metering?", "2012.12104v1"),
    RetrievalCase(
        "What method did the ramp metering paper compare against PI-ALINEA?", "2012.12104v1"
    ),
    RetrievalCase(
        "How does the DRL ramp metering approach use traffic video data?", "2012.12104v1"
    ),
    RetrievalCase("What DRL algorithm did the power grid control paper propose?", "2012.13026v1"),
    RetrievalCase(
        "What optimization approach did the power grid paper use for reward design?",
        "2012.13026v1",
    ),
    RetrievalCase(
        "How does imitation learning compare to reinforcement learning for power grid control?",
        "2012.13026v1",
    ),
    RetrievalCase(
        "What is the three-stage training scheme for scalable transformers?", "2106.02242v2"
    ),
    RetrievalCase(
        "How do scalable transformers avoid redundant training for different deployment scenarios?",
        "2106.02242v2",
    ),
    RetrievalCase(
        "What benchmarks were used to validate the scalable transformers approach?",
        "2106.02242v2",
    ),
]


@dataclass(frozen=True)
class GuardrailCase:
    query: str
    expected_on_topic: bool


GUARDRAIL_CASES: list[GuardrailCase] = [
    GuardrailCase("What does this paper say about transformers?", True),
    GuardrailCase("Summarize recent research on reinforcement learning for traffic control.", True),
    GuardrailCase("What optimization techniques are used in power grid control research?", True),
    GuardrailCase("Can you explain the methodology used in this arXiv paper?", True),
    GuardrailCase("What's a good recipe for chocolate chip cookies?", False),
    GuardrailCase("What's the weather like today?", False),
    GuardrailCase("Can you help me plan a vacation to Hawaii?", False),
    GuardrailCase("What's the best way to fix a flat tire?", False),
]


@dataclass(frozen=True)
class FaithfulnessCase:
    query: str
    category: Literal["in_corpus", "out_of_corpus", "off_topic"]


FAITHFULNESS_CASES: list[FaithfulnessCase] = [
    FaithfulnessCase(
        "What benefits did the DRL ramp metering approach show over the "
        "state-of-the-practice method?",
        "in_corpus",
    ),
    FaithfulnessCase(
        "What is the three-stage training scheme for scalable transformers?", "in_corpus"
    ),
    FaithfulnessCase(
        "What does this corpus say about diffusion models for image generation?", "out_of_corpus"
    ),
    FaithfulnessCase(
        "How do graph neural networks compare to transformers for molecular property prediction?",
        "out_of_corpus",
    ),
    FaithfulnessCase("What's the capital of France?", "off_topic"),
    FaithfulnessCase("What's a good recipe for chocolate chip cookies?", "off_topic"),
]
