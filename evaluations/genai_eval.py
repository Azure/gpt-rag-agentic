from promptflow.client import PFClient
from promptflow.core import AzureOpenAIModelConfiguration
import json
import os
import pandas as pd
import requests
import datetime
import time 

def main():
    print("Starting main function...")

    azure_config = {
        "aoai_endpoint": os.environ.get('AZURE_OPENAI_ENDPOINT', ''),
        "aoai_api_version": os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01'),
        "aoai_api_key": os.environ.get('AZURE_OPENAI_API_KEY', ''),
        "subscription_id": os.environ.get('AZURE_SUBSCRIPTION_ID', ''),
        "resource_group": os.environ.get('AZURE_RESOURCE_GROUP', ''),
        "project_name": os.environ.get('AZUREAI_PROJECT_NAME', '')
    }
    print("Azure configuration loaded.")

    orchestrator_endpoint = os.environ.get('ORCHESTRATOR_ENDPOINT', 'http://localhost:7071/api/orc')
    print(f"Orchestrator endpoint: {orchestrator_endpoint}")

    # Get the function key from environment variables
    function_key = os.environ.get('FUNCTION_KEY', '')
    print("Function key retrieved.")

    ##################################
    ## Base Run
    ##################################

    data_file = "evaluations/test-dataset.jsonl"
    custom_data_file = "evaluations/test-dataset.custom.jsonl"
    output_file = "evaluations/responses.jsonl"
    print("File paths set.")

    # Ensure 'evaluations' directory exists
    os.makedirs('evaluations', exist_ok=True)
    print("Ensured 'evaluations' directory exists.")

    # Determine which data file to use
    if os.path.exists(custom_data_file):
        data_file_to_use = custom_data_file
        print(f"Using custom data file: {custom_data_file}")
    elif os.path.exists(data_file):
        data_file_to_use = data_file
        print(f"Using default data file: {data_file}")
    else:
        raise FileNotFoundError("Neither custom_data_file nor data_file exists.")
    print(f"Data file to use: {data_file_to_use}")

    # Process each question in the test dataset
    with open(data_file_to_use, 'r', encoding='utf-8') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
        print("Opened data file and output file.")
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            try:
                # Attempt to parse the JSON line
                data = json.loads(line)
                question = data.get('question', '')
                ground_truth = data.get('ground_truth', '')
                print(f"Processing question: {question}")

                # Prepare the request payload
                request_body = {
                    "conversation_id": "",
                    "question": question
                }
                headers = {
                    'Content-Type': 'application/json',
                    'x-functions-key': function_key
                }
                
                # Start timing
                start_time = time.time()
                
                response = requests.post(orchestrator_endpoint, headers=headers, json=request_body)
                response.raise_for_status()
                response_data = response.json()
                answer = response_data.get('answer', '')
                data_points = response_data.get('data_points', '')
                thoughts = response_data.get('thoughts', '')
                
                # End timing
                end_time = time.time()
                duration = end_time - start_time
                print(f"Processing time for question '{question}': {duration:.2f} seconds")
                
            except Exception as e:
                # Handle errors from the orchestrator call
                error_message = f"Error calling orchestrator: {str(e)}"
                print(f"{error_message} for question: {question}")
                answer = error_message
                data_points = ""
                thoughts = ""
                duration = 0  # Set duration to zero if there's an error

            # Prepare and write the output JSON
            output_data = {
                "question": question,
                "ground_truth": ground_truth,
                "answer": answer,
                "context": data_points,
                "reasoning": thoughts,
                "processing_time_seconds": f"{duration:.2f}"  # Include processing time
            }
            f_out.write(json.dumps(output_data) + '\n')

    print("Finished processing all questions.")

    # Evaluation run
    pf = PFClient()
    eval_prompty = "evaluations/genai-score-eval.prompty"
    print("Starting evaluation run...")
    eval_run = pf.run(
        flow=eval_prompty,
        data=output_file,  
        column_mapping={
            "question": "${data.question}",
            "answer": "${data.answer}",
            "ground_truth": "${data.ground_truth}",
            "context": "${data.context}"            
        },
        stream=True,
    )
    print("Evaluation run completed.")

    details = pf.get_details(eval_run)
    print("Retrieved evaluation details.")
    print(details.head(10))

    # Compute the averages of outputs.similarity_score and outputs.groundedness_score
    average_score = details['outputs.similarity_score'].mean()
    average_groundedness_score = details['outputs.groundedness_score'].mean()

    # Create a new row with averages
    average_row = {}
    for col in details.columns:
        if col == 'inputs.question':
            average_row[col] = 'Average'
        elif col == 'outputs.similarity_score':
            average_row[col] = average_score
        elif col == 'outputs.groundedness_score':
            average_row[col] = average_groundedness_score
        else:
            average_row[col] = ''

    # Append the new row to the DataFrame
    average_df = pd.DataFrame([average_row])
    details = pd.concat([details, average_df], ignore_index=True)

    # Save output to an Excel file 
    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"evaluations/genai-score-eval_{current_time}.xlsx"
    details.to_excel(filename, index=False)
    print(f"Saved evaluation details to Excel file: {filename}")

if __name__ == '__main__':
    import promptflow as pf
    print("Imported promptflow.")
    main()
    print("Main function executed.")

    # To run the script, you need to run the following command:
    # python ./evaluations/prompty_eval.py
