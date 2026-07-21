from dataclasses import dataclass


@dataclass
class RetrievalCaseResult:
    query: str
    expected_arxiv_id: str
    precision: float
    recall: float


@dataclass
class RetrievalReport:
    results: list[RetrievalCaseResult]
    mean_precision: float
    mean_recall: float


@dataclass
class GuardrailCaseResult:
    query: str
    expected: bool
    predicted: bool


@dataclass
class GuardrailReport:
    results: list[GuardrailCaseResult]
    accuracy: float


@dataclass
class FaithfulnessCaseResult:
    query: str
    category: str
    naive_answered: bool
    naive_score: int | None
    naive_note: str | None
    agentic_answered: bool
    agentic_score: int | None
    agentic_note: str | None


@dataclass
class CategorySummary:
    category: str
    naive_answer_rate: float
    naive_mean_faithfulness: float | None
    agentic_answer_rate: float
    agentic_mean_faithfulness: float | None


@dataclass
class FaithfulnessReport:
    results: list[FaithfulnessCaseResult]
    category_summaries: list[CategorySummary]
