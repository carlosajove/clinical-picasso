"""Natural language → OmniGraph .gq query generation.

The LLM reads the graph schema and a question, generates a .gq query,
we run it, and return results.  If the query fails, we retry once with
the error message so the LLM can self-correct.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai import Agent


_DEFAULT_MODEL = "anthropic:claude-sonnet-4-5"

_MAX_RETRIES = 2


class GeneratedQuery(BaseModel):
    """What the LLM produces."""
    gq_query: str
    explanation: str


_SYSTEM_PROMPT_TEMPLATE = """\
You are an OmniGraph query generator. Given a graph schema and a natural
language question, you produce a valid .gq query that answers the question.

# OmniGraph .gq syntax

```
query name() {{
    match {{
        $var: NodeType
        $var: NodeType {{ property: "value" }}
        $a edgeName $b              // single hop
        $a edgeName{{1,5}} $b        // multi-hop (bounded)
        $var.field > 42             // comparison
        not {{ $a edgeName $b }}     // negation
    }}
    return {{ $var.field1, $var.field2 }}
    order {{ $var.field desc }}
    limit 20
}}
```

## Rules
- Edge traversal uses camelCase: `derivedFrom`, `belongsToTrial`, `supersedes`, `references`, `governs`
- Node types use PascalCase: `Document`, `Trial`
- Unbounded traversal is disabled — always use {{min,max}} bounds
- The query must be named `nl_query` with no parameters (we run it as-is)
- Return only the fields needed to answer the question
- Keep queries simple — prefer fewer patterns
- Trial nodes have `protocol_id` as the primary identifier (e.g. "BIORCE-ONC-2023-001") — always include it when returning Trial data
- When querying trials, always include `$trial.protocol_id` and `$trial.title` in the return

# Graph schema

{schema}

# Important
- Return ONLY the GeneratedQuery JSON. No commentary.
- The `gq_query` field must contain a valid .gq query string.
- The `explanation` field should be a short, conversational answer to the user's question. Write it as if you're speaking directly to them (e.g. "Here are all the trials in the graph:" or "I found 3 ICFs linked to that protocol."). Do NOT describe the query itself — describe what the results show.
"""


@dataclass
class QueryResult:
    """Result of a natural language query."""
    question: str
    gq_query: str
    explanation: str
    rows: list[dict]
    error: str | None = None


def _load_schema(schema_path: str | Path) -> str:
    return Path(schema_path).read_text()


def ask(
    question: str,
    client,  # OmniGraphClient
    schema_path: str | Path = "schema/clinical.pg",
    model: str = _DEFAULT_MODEL,
) -> QueryResult:
    """Ask a natural language question about the graph.

    1. LLM generates a .gq query from the schema + question
    2. We run it against the graph
    3. Return structured results
    """
    schema_text = _load_schema(schema_path)
    system = _SYSTEM_PROMPT_TEMPLATE.replace("{schema}", schema_text)

    agent: Agent[None, GeneratedQuery] = Agent(
        model=model,
        output_type=GeneratedQuery,
        system_prompt=system,
    )

    result = agent.run_sync(question)
    gen = result.output

    # Try running the generated query
    for attempt in range(_MAX_RETRIES):
        try:
            rows = _run_gq(gen.gq_query, client)
            return QueryResult(
                question=question,
                gq_query=gen.gq_query,
                explanation=gen.explanation,
                rows=rows,
            )
        except RuntimeError as e:
            if attempt < _MAX_RETRIES - 1:
                # Retry: feed error back to LLM
                retry_prompt = (
                    f"The query you generated failed with this error:\n\n"
                    f"{e}\n\n"
                    f"Original question: {question}\n\n"
                    f"Please fix the query."
                )
                result = agent.run_sync(retry_prompt)
                gen = result.output
            else:
                return QueryResult(
                    question=question,
                    gq_query=gen.gq_query,
                    explanation=gen.explanation,
                    rows=[],
                    error=str(e),
                )


def _run_gq(gq_query: str, client) -> list[dict]:
    """Write query to temp file and execute via OmniGraphClient."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".gq", delete=False,
    ) as f:
        f.write(gq_query)
        tmp = f.name

    try:
        return client.read(tmp, "nl_query", branch=None)
    finally:
        Path(tmp).unlink(missing_ok=True)
