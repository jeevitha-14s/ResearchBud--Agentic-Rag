from src.agents.graph import initial_state
from src.agents.guardrail import make_guardrail_node
from src.eval.dataset import GUARDRAIL_CASES
from src.eval.metrics import accuracy
from src.eval.reports import GuardrailCaseResult, GuardrailReport
from src.services.llm import LLMClient


def run_guardrail_eval(llm_client: LLMClient) -> GuardrailReport:
    node = make_guardrail_node(llm_client)

    results = []
    for case in GUARDRAIL_CASES:
        update = node(initial_state(case.query))
        results.append(
            GuardrailCaseResult(
                query=case.query,
                expected=case.expected_on_topic,
                predicted=bool(update["is_on_topic"]),
            )
        )

    acc = accuracy([r.predicted for r in results], [r.expected for r in results])
    return GuardrailReport(results=results, accuracy=acc)
