# GPT-RAG Orchestrator Quality Evaluation

## Overview

This guide walks you through the simplified evaluation process for the GPT-RAG Orchestrator using the script `generate_evaluation_input.py`. Instead of running a full evaluation pipeline locally, you will:

1. Generate answers using your orchestrator and the script provided.
2. Upload the results to the AI Foundry portal.
3. Run evaluations such as **Groundedness** directly from the portal.

## Step 1 – Environment Setup

Before you begin, make sure the following are configured:

### Prerequisites

- **Python 3.10+**
- **Python Packages:**
  - `requests`

Install required packages with:

```bash
pip install -r requirements.txt
```

### Environment Variables

The script uses two environment variables:

- `ORCHESTRATOR_STREAM_ENDPOINT`: Your orchestrator's endpoint for streaming responses.
- `FUNCTION_KEY`: The API key for authentication.

Create a `.env` file or set the variables in your shell:

```env
ORCHESTRATOR_STREAM_ENDPOINT=https://your-orchestrator-endpoint/api/orc/stream
FUNCTION_KEY=your-function-key
```

## Step 2 – Prepare Test Data

Your test questions must be in JSON Lines format (`.jsonl`). Each line should contain a question and optionally a ground truth answer.

### Example `test-dataset.jsonl`

```json
{"question": "What is Zero Trust?", "ground_truth": "Zero Trust is a security model..."}
{"question": "Explain the benefits of Zero Trust architecture."}
```

You can place this file at `evaluations/input/test-dataset.jsonl` or specify a custom path using the `--input` flag.

## Step 3 – Generate Evaluation Input

Run the script to generate responses from your orchestrator:

```bash
python evaluations/generate_evaluation_input.py
```

This script will:

- Read each question.
- Call your orchestrator via REST API.
- Save the responses (with optional conversation IDs) into a new `.jsonl` file under the `evaluations/output/` folder.

### Output Example

```json
{
  "question": "What is Zero Trust?",
  "ground_truth": "Zero Trust is a security model...",
  "response": "Zero Trust is a framework that assumes...",
  "context": "",
  "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

## Step 4 – Upload to AI Foundry

1. Open your [Azure AI Studio / AI Foundry project](https://ai.azure.com/) in your browser.
2. Go to the **Evaluation** tab.
3. Select **"New Evaluation"** and choose **"Upload Evaluation File"**.
4. Upload the `.jsonl` output file you generated in Step 3.
5. Choose the evaluation metric you want to run, such as **Groundedness**.
6. Click **Run Evaluation**.

## Tips for Groundedness Evaluation

- Ensure your orchestrator includes relevant **context** in the response if required by the evaluation prompt.
- The AI Foundry evaluation will assess whether the answer logically follows from the context (even if context is currently empty).
- You can edit the prompt template used by the evaluation engine in AI Foundry if you want to improve score interpretation.

## Conclusion

This streamlined approach allows you to quickly evaluate the quality of your GPT-RAG Orchestrator using Azure AI Foundry’s built-in capabilities. You just need to:

1. Generate response data using `generate_evaluation_input.py`.
2. Upload the result to the AI Foundry portal.
3. Run targeted evaluations like **Groundedness**, **Similarity**, or others available.

You are free to modify the script or input format to better fit your use case or evaluation criteria.
