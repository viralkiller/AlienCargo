Here is the extracted information from the provided document regarding how to track the progress, status, and duration of requests from Anthropic models:

**Message Batches API Progress Tracking**
For asynchronous batch processing, you can track the progress of your requests by polling the API to see how many individual requests have completed.

*
**Processing Status**: The batch response includes a `processing_status` field that indicates the current stage of the batch, starting as `"in_progress"` and updating to `"ended"` once all requests finish.


*
**Request Counts**: You can calculate completion progress using the `request_counts` object. It breaks down the batch into the number of requests that are `"processing"`, `"succeeded"`, `"errored"`, `"canceled"`, or `"expired"`.


*
**Timestamps**: The API returns `created_at`, `ended_at`, and `expires_at` timestamps (note that batches expire after 24 hours) which can help track how long the batch has been running.



**Real-Time Streaming**
For synchronous requests, while the API does not provide an upfront time estimate, you can provide real-time progress to the user by enabling streaming (`"stream": true`).

* Instead of waiting for the full response to finish, the API pushes server-sent events (SSE) to the client to keep the connection alive.


* You receive `content_block_delta` events (which stream text or tool JSON sequentially) to show live generation progress as the model works.



**Token Usage Budgets**
For long-running tasks, Claude 4.5 models feature context awareness where the API updates the remaining token capacity after each tool call.

* The API returns a system warning showing exact usage metrics (e.g., `<system_warning>Token usage: 35000/200000; 165000 remaining</system_warning>`).


* This acts as a "clock" indicating how much working capacity is left before the workflow must be summarized or concluded.



**Execution Duration Metrics**
The SDK result messages and task outputs return exact execution times via `duration_ms` and `duration_api_ms` fields.
While these are returned post-execution, you can log them to calculate historical average completion times for specific tasks to provide better estimates to users in the future.

----

Plan:

1. Implement a polling mechanism for the Anthropic Message Batches API to track asynchronous completion counts.
2. Implement a real-time event listener using the Anthropic Messages streaming API to track synchronous generation progress.
3. Integrate detailed console logging across all network and processing events.
4. Keep comments brief.

[-]

```python
import anthropic
import logging
import time

# Configure verbose console logging
logging.basicConfig(level=logging.DEBUG)

def track_batch_progress(batch_id: str):
    # Initialize the client
    client = anthropic.Anthropic()
    logging.debug(f"Starting poll for batch: {batch_id}")

    while True:
        # Fetch current batch state
        batch = client.messages.batches.retrieve(batch_id)
        status = batch.processing_status
        logging.info(f"Current batch status: {status}")

        if status == "ended":
            # Exit loop on completion
            logging.debug("Batch processing has finished.")
            break

        # Log exact completion metrics
        counts = batch.request_counts
        logging.debug(f"Progress counts: {counts}")

        # Pause before polling again
        logging.info("Sleeping 10s before next poll.")
        time.sleep(10)

def stream_request_progress():
    # Initialize the client
    client = anthropic.Anthropic()
    logging.debug("Initiating streaming request.")

    # Open continuous stream connection
    with client.messages.stream(
        max_tokens=1024,
        messages=[{"role": "user", "content": "Explain quantum computing."}],
        model="claude-opus-4-6",
    ) as stream:
        logging.info("Stream connection opened.")

        # Process events as they arrive
        for event in stream:
            if event.type == "content_block_delta":
                # Log incremental text generation
                logging.debug("Text delta chunk received.")
                print(event.delta.text, end="", flush=True)
            elif event.type == "message_stop":
                # Log stream termination
                logging.info("Message generation stopped.")

        # Extract final execution metrics
        message = stream.get_final_message()
        logging.info(f"Final token usage: {message.usage}")

if __name__ == "__main__":
    # Example execution triggers
    logging.debug("Script execution started.")

    # Execute stream tracking
    stream_request_progress()

    # Execute batch tracking
    # track_batch_progress("msgbatch_123")

```

