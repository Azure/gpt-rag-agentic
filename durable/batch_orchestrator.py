import azure.durable_functions as df
import logging

def orchestrator_function(context: df.DurableOrchestrationContext):
    logging.info("[batch_orchestrator] Orchestrator started")
    
    # Call the activity function that lists the input blobs.
    input_blobs = yield context.call_activity("list_input_blobs", None)
    results = []
    
    # Process each blob (sequentially or in parallel based on your needs).
    for blob in input_blobs:
        result = yield context.call_activity("process_blob", blob)
        results.append(result)
    
    return results

main = df.Orchestrator.create(orchestrator_function)
