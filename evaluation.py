import argparse
import json
import os

from dotenv import load_dotenv

load_dotenv()

from langfuse import get_client
from langfuse.experiment import Evaluation
from openai import AsyncOpenAI

from Agent import run_research

langfuse = get_client()

DATASET_NAME = "research-agent-eval"

# Topics the research pipeline should be able to handle, with a short rubric of
# what a good answer ought to surface. expected_output is guidance for the judge,
# not a string to match exactly.
EVAL_ITEMS = [
    {
        "input": "which countries are hosting AI research labs?",
        "expected_output": "Names several specific countries (e.g. USA, UK, China, "
        "Canada, France) that host notable AI research labs, ideally tying labs to "
        "countries.",
    },
    {
        "input": "what are the main causes of coral reef bleaching?",
        "expected_output": "Identifies rising sea temperatures as the primary driver, "
        "plus ocean acidification, pollution, and overexposure to sunlight.",
    },
    {
        "input": "how does the EU AI Act classify AI systems by risk?",
        "expected_output": "Describes the tiered risk classification: unacceptable, "
        "high, limited, and minimal risk, with examples per tier.",
    },
    {
        "input": "what recent advances exist in solid-state battery technology?",
        "expected_output": "Covers solid electrolytes, higher energy density, improved "
        "safety vs lithium-ion, and key companies/research pushing the field.",
    },
    {
        "input": "who are the leading companies in commercial space launch?",
        "expected_output": "Names SpaceX, Rocket Lab, Blue Origin, ULA, Arianespace "
        "and similar, ideally with what differentiates them.",
    },
]


def seed_dataset() -> None:
    """Create the dataset and (idempotently) upsert evaluation items."""
    langfuse.create_dataset(
        name=DATASET_NAME,
        description="Topics for evaluating the research agent pipeline in Agent.py",
        metadata={"pipeline": "run_research", "source": "evaluation.py"},
    )
    for i, item in enumerate(EVAL_ITEMS):
        langfuse.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=f"{DATASET_NAME}-{i}",  # stable id -> upsert, safe to re-run
            input=item["input"],
            expected_output=item["expected_output"],
        )
    langfuse.flush()
    print(f"Seeded dataset '{DATASET_NAME}' with {len(EVAL_ITEMS)} items.")


async def research_task(*, item, **kwargs) -> dict:
    """Run the agent pipeline on a dataset item's topic."""
    topic = item.input
    result = await run_research(topic)
    return {
        "key_insights": list(result.key_insights),
        "cites": result.cites,
    }


# --- Scorers ------------------------------------------------------------------
# The in-code LLM-as-a-judge below scores the FINAL output of the whole pipeline
# (Researcher -> Display handoff). A UI evaluator on an experiment only sees a
# single generation in the trace, so it cannot judge the end-to-end result of a
# multi-agent handoff -- hence we judge in-process here, where `output` is exactly
# what research_task returns.

# Separate API key so the judge has its own quota, independent of the pipeline's.
_judge = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY1"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)


async def incode_llm_judge(*, input, output, expected_output, **kwargs):
    """Score the pipeline's final output 1-5 against the rubric."""
    prompt = (
        f"Topic: {input}\n\n"
        f"Agent output: {json.dumps(output)}\n\n"
        f"What a good answer should contain: {expected_output}\n\n"
        'Rate the output from 1 (irrelevant/wrong) to 5 (accurate and complete). '
        'Reply with JSON: {"score": <1-5>, "reasoning": "<one sentence>"}'
    )
    resp = await _judge.chat.completions.create(
        model="gemini-3.1-flash-lite",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    data = json.loads(resp.choices[0].message.content)
    return Evaluation(
        name="incode_llm_judge",
        value=int(data["score"]),
        comment=data.get("reasoning"),
    )


def has_citations(*, output, **kwargs):
    """Did the pipeline return any citation?"""
    cites = (output or {}).get("cites")
    return Evaluation(name="has_citations", value=1.0 if cites else 0.0)


def run_eval() -> None:
    dataset = langfuse.get_dataset(DATASET_NAME)
    result = dataset.run_experiment(
        name="research-agent-baseline",
        description="Baseline eval of run_research with LLM-as-a-judge scoring",
        task=research_task,
        evaluators=[incode_llm_judge, has_citations],
        max_concurrency=1,  # Gemini free tier: 15 req/min, each item makes several calls
    )
    print(result.format())
    langfuse.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the research agent pipeline.")
    parser.add_argument(
        "--seed", action="store_true", help="Create/upsert the eval dataset, then exit."
    )
    parser.add_argument(
        "--run", action="store_true", help="Run the experiment against the dataset."
    )
    args = parser.parse_args()

    if args.seed:
        seed_dataset()
    if args.run:
        run_eval()
    if not args.seed and not args.run:
        parser.print_help()


if __name__ == "__main__":
    main()
