# Evaluation input generation

This guide describes
[`generate_evaluation_input.py`](../evaluations/generate_evaluation_input.py).
It sends questions to the streaming API and saves responses as JSON Lines.
It does not calculate quality scores or run a load test.
See the [repository status](../README.md#integration-status) before using this
runtime.

## Prerequisites and environment

Run commands from the repository root. The generator imports `requests` and
standard Python modules. `requests` is included in the root
[`requirements.txt`](../requirements.txt).
If you only need the generator, install its dependency in a virtual environment:

```bash
python -m pip install requests
```

The script reads these variables from the process environment:

| Variable | Use |
| --- | --- |
| `ORCHESTRATOR_STREAM_ENDPOINT` | Full streaming URL, normally `https://<function-app>.azurewebsites.net/api/orcstream`. |
| `FUNCTION_KEY` | Function key sent in the `x-functions-key` header. |

Both variables must be nonempty. The generator does not load `.env` files.
Provide the key through your approved secret-handling process, not a command
saved in shell history or a tracked file. Managed identity is used by runtime
service connectors, but this generator does not implement token-based API
authentication.

The endpoint must already be running and reachable. Generating answers calls
Azure services through the orchestrator and can incur costs. Use approved,
non-sensitive test data.

## Input

Each nonempty line must be a JSON object with a `question` or `query` string.
If both are present, the script uses `query`.
`ground_truth` is optional and is preserved, not scored.

```jsonl
{"question": "What is Zero Trust?", "ground_truth": "An expected answer for comparison."}
{"question": "How does that affect access decisions?", "followup": "yes"}
```

Only `followup: "yes"` reuses the last conversation ID extracted from a response.
Other records start with an empty conversation ID. Input fields named
`conversation` or `conversation_id` do not select the request's conversation.
Blank lines are ignored, and invalid JSON lines are skipped with a message.
The script does not validate all field types, so check your dataset first.

## Generate responses

Two sample datasets are provided in [`evaluations/`](../evaluations/).
The default input path, `evaluations/input/test-dataset.jsonl`, is not shipped.
Specify an existing file:

```bash
python evaluations/generate_evaluation_input.py --input evaluations/sample-test-dataset-classic.jsonl --output-folder evaluations/output
```

Choose a strategy and data sources that match the dataset. The NL2SQL sample is
`evaluations/sample-test-dataset-nl2sql.jsonl`.

The generator creates the output folder and writes a file named
`<input-name>_<YYYYMMDD_HHMMSS><input-extension>`. It preserves input fields and
adds or overwrites `response`, `context`, and `conversation_id`.

```jsonl
{"question": "What is Zero Trust?", "response": "An answer from the orchestrator.", "context": "", "conversation_id": "123e4567-e89b-12d3-a456-426614174000"}
```

The [streaming implementation](../orchestration/orchestrator.py) sends a
conversation ID before model text. The generator tries to extract a leading
UUID from the received lines and joins the remaining text. It does not parse a
structured response containing retrieved sources.

Review the output before scoring it. Request failures are written as
`Error: ...` response text rather than causing the whole run to fail.
A completed file is not proof that every request succeeded.

## Scoring limitations

`context` is always an empty string in the generated file. This output alone is
not sufficient for a groundedness evaluation that requires retrieval context.
Supply actual retrieved evidence and map fields according to the evaluator you
choose. Do not treat an empty context as evidence that an answer is grounded.

You can use the file as input to a separate evaluation workflow, subject to that
workflow's schema, permissions, and data-handling requirements. This repository
does not automate a Foundry portal upload or define the portal's current UI.
Portal steps and metric availability must be checked against current service
documentation.

## Older evaluation scripts

`genai_evaluation.py`, `evaluate.sh`, and `evaluate.ps1` are separate legacy
scripts, not wrappers for the generator above. They are not a working
end-to-end evaluation path as shipped:

- `genai_evaluation.py` imports `Orchestrator`, which is not exported by
  `orchestration/__init__.py`. This also blocks its REST mode.
- The wrappers search for `test-*.jsonl`, not the shipped `sample-test-*.jsonl`
  names.
- The PowerShell wrapper constructs a nested
  `evaluations/evaluations/genai_evaluation.py` path that does not exist.

The separate `evaluations/requirements.txt` belongs to that older workflow.
Do not install it as a requirement for the response generator.
