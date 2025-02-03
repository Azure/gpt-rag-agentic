# GPT-RAG Orchestrator Quality Evaluation

## Introduction

We provide an evaluation program to assess the performance of the GPT-RAG Orchestrator by:

1. Generating answers to a set of test questions.
2. Evaluating the generated answers based on similarity to ground truth and groundedness in provided context.

The program processes test data, invokes the orchestrator for each question, and then evaluates the responses using predefined scoring guidelines. The final results, including detailed scores and explanations, are saved in an Excel file for further analysis.

## Prerequisites

Before running the evaluation program, ensure you have the following:

- **Python 3.10+**
- **Required Python Libraries:**
  - `promptflow`
  - `requests`
  - `pandas`

## Environment Setup

### Creating the `.env` File

The program relies on several environment variables for configuration. You need to create a `.env` file to store these variables.

1. **Copy the Template:**

   - Make a copy of the `.env.template` file and rename it to `.env` in the root directory of your project.

2. **Fill in the Variables:**

   - Open the `.env` file and fill in the necessary variables with your specific configuration.
   
   - Replace the placeholders with your actual Azure and orchestrator configuration values.

### Environment Variables Explained

- `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID.
- `AZURE_RESOURCE_GROUP`: The name of your Azure resource group.
- `AZUREAI_PROJECT_NAME`: Name of your Azure AI project.
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL.
- `AZURE_OPENAI_API_VERSION`: API version (default is `'2024-02-01'`).
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key.
- `AZURE_OPENAI_CHAT_DEPLOYMENT`: Deployment name for chat models (default is `'chat'`).
- `AZURE_OPENAI_EMBEDDING_MODEL`: Embedding model name (default is `'text-embedding-3-large'`).
- `ORCHESTRATOR_ENDPOINT`: The endpoint URL of your GPT-RAG Orchestrator (default is `'http://localhost:7071/api/orc'`).
- `FUNCTION_KEY`: The function key for authenticating requests to the orchestrator (e.g., `'1234567890'`).

## Data Preparation

### Test Data Files

The program expects test data in JSON Lines (`.jsonl`) format. It looks for the following files in the `evaluations` directory:

1. `evaluations/test-dataset.custom.jsonl`: **Custom test dataset introduced by the user.**
2. `evaluations/test-dataset.jsonl`: **Default sample test dataset provided with the program.**

**Note:** If both files are present, the program uses `test-dataset.custom.jsonl` to allow users to run evaluations with their own test data.

### Creating Your Own Test Data

To use your own test dataset:

1. **Ensure the Evaluations Directory Exists:**

   Verify that the `evaluations` directory exists in the root of your project. If it doesn't, create it.

2. **Create a Custom Data File:**

   - In the `evaluations` directory, create a file named `test-dataset.custom.jsonl`.
   - Populate this file with your test data. Each line should be a valid JSON object containing:
     - `question`: The question you want the orchestrator to process.
     - `ground_truth`: The expected correct answer for the question.

3. **Sample Entry:**

   ```json
   {"question": "What is the highest mountain in the world?", "ground_truth": "Mount Everest"}
   ```

4. **File Format Guidelines:**

   - Each JSON object should be on a separate line in the file.
   - Do not include commas between lines.
   - Ensure that the JSON syntax is correct to prevent parsing errors.

By creating `test-dataset.custom.jsonl`, you can evaluate the orchestrator using your own set of questions and expected answers.

### Default Test Data

If you do not provide a custom test dataset, the program will use the default sample data provided in `test-dataset.jsonl`. This file contains sample questions and ground truth answers for demonstration purposes.

## Program Workflow

The evaluation program performs the following steps:

1. **Initialization:**

   - Loads configuration from the `.env` file.
   - Determines which test data file to use.
   - Ensures necessary directories exist.

2. **Processing Test Data:**

   - Reads each question from the test data file.
   - For each question:
     - Sends a request to the GenAI Orchestrator with the question.
     - Receives the answer, context (data points), and reasoning (reasoning).
     - Measures the processing time for generating the answer.
     - Logs any errors encountered during the process.

3. **Saving Responses:**

   - Writes the question, ground truth, generated answer, context, reasoning, and processing time to `evaluations/responses.jsonl`.

4. **Evaluation Run:**

   - Initializes the PromptFlow client.
   - Runs the evaluation using the `evaluations/genai-score-eval.prompty` prompt.
   - Maps the data columns appropriately.
   - Streams the evaluation results.

5. **Processing Evaluation Results:**

   - Retrieves evaluation details.
   - Computes average similarity and groundedness scores.
   - Appends an average row to the results.

6. **Saving Evaluation Results:**

   - Saves the detailed evaluation results to an Excel file named `evaluations/genai-score-eval_<timestamp>.xlsx`.

## Running the Program

Follow these steps to run the evaluation program:

1. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Environment Variables:**

   - Ensure that the `.env` file is correctly set up in the root directory with all the necessary variables filled.

3. **Prepare Test Data:**

   - If you want to use your own test data, create `test-dataset.custom.jsonl` in the `evaluations` directory as described above.
   - If not, ensure that the default `test-dataset.jsonl` file is present.

4. **Run the Script:**

   ```bash
   python ./evaluations/prompty_eval.py
   ```

   **Note:** Adjust the script path if necessary.

## Outputs

After running the program, you will have the following output files in the `evaluations` directory:

1. **responses.jsonl:**

   - Contains the raw responses from the orchestrator for each question.
   - Each line is a JSON object with the following keys:
     - `question`
     - `ground_truth`
     - `answer`
     - `context`
     - `reasoning`
     - `processing_time_seconds`

2. **genai-score-eval_<timestamp>.xlsx:**

   - An Excel file with detailed evaluation results.
   - Includes similarity and groundedness scores for each question.
   - Contains an average row summarizing overall performance.

## Evaluation Criteria

The evaluation program assesses the orchestrator's responses based on two main criteria:

### Similarity Scoring (GPT-Similarity)

- **Objective:** Measure how similar the generated answer is to the ground truth.
- **Scoring Guidelines:**
  - **1:** Not at all similar.
  - **2:** Mostly not similar.
  - **3:** Somewhat similar.
  - **4:** Mostly similar.
  - **5:** Completely similar.
- **Considerations:** Focus on the information and content equivalence between the answers.

### Groundedness Scoring

- **Objective:** Determine if the answer logically follows from the provided context.
- **Scoring Guidelines:**
  - **5:** Answer follows logically from the context.
  - **1:** Answer is logically false based on the context.
  - **2-4 (or 1 if uncertain):** Cannot determine truthfulness without more information.
- **Considerations:** Evaluate the answer solely based on the context provided, disregarding external knowledge.

### Example

**Question:**
```
What is the capital of France?
```

**Answer:**
```
Paris
```

**Ground Truth:**
```
Paris
```

**Context:**
```
Paris is the capital city of France. It is located along the Seine River in northern central France.
```

**Expected Output:**

```json
{
  "similarity_score": "5",
  "similarity_explanation": "The predicted answer 'Paris' is completely similar to the correct answer.",
  "groundedness_score": "5",
  "groundedness_explanation": "The answer follows logically from the information contained in the context."
}
```

## Notes

- **PromptFlow Configuration:**
  - The evaluation uses a prompt defined in `evaluations/genai-score-eval.prompty`.
  - Ensure this file exists and is correctly configured.

- **Error Handling:**
  - Any errors during orchestrator calls are logged, and the error message is saved as the answer.

- **Processing Time:**
  - The time taken to process each question is recorded and saved.

- **Extensibility:**
  - You can extend the evaluation criteria by modifying the prompt and scoring guidelines.

## Troubleshooting

- **Missing Environment Variables:**
  - Ensure all required environment variables are set in the `.env` file.
  - Check for typos or missing values.

- **Dependencies Not Installed:**
  - Verify that all Python libraries are installed.
  - Reinstall using `pip install -r requirements.txt` if you have a `requirements.txt` file.

- **File Not Found Errors:**
  - Confirm that the `evaluations` directory and necessary files exist.
  - Check file paths and filenames for typos.

- **Orchestrator Connection Issues:**
  - Ensure the orchestrator endpoint is correct and accessible.
  - Verify that the function key is valid.

## Conclusion

This evaluation program provides a systematic approach to assess the performance of the GPT-RAG Orchestrator. By following the guidelines and instructions provided, you can evaluate how well the orchestrator generates answers and how closely they align with the expected results and provided context.

Feel free to modify and extend the program to suit your specific evaluation needs.