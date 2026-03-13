Here is what we need:
Alien Cargo is a game generator. The index page consists of a textarea "describe your game" and also a "Create Game" button.
We then send an LLM gen request to external microservice 'AIManager' to get a single HTML/JS page containing the game, and allow the user to instantly
access this page and play the game. Obviously some kind of clever generative code trick.

Games should have:
1280x720 centered canvas.
Arrow keys to move if applicable, WASD for second player if applicable.
Enter to start game.
Space to shoot.
Games should always have a Restart/Go again button if a player gets killed.

----

[AIManager Quick Start Guide]

Here is a quickstart guide for integrating your client website with the AIManager system to request generations from Anthropic's Claude Sonnet or Opus models.

### 1. The API Endpoint

To communicate with AIManager, your client website needs to send a `POST` request to the unified processing endpoint:

*
**URL:** `https://<your-aimanager-domain>/process_request` (or `http://localhost:5000/process_request` for local development).


*
**Method:** `POST`


*
**Headers:** `Content-Type: application/json`



### 2. Choosing Your Model

AIManager uses a standardized naming convention to route your request to the correct Anthropic model. You must specify the provider and the exact model key:

*
**Provider:** `"anthropic"`


* **Available Model Keys:**
*
`"claude-sonnet-4-5-20250929"`: Supports standard text-to-text generation.


*
`"claude-opus-4-6"`: Supports both text-to-text generation and image-to-text analysis.





### 3. Constructing the JSON Payload

The AIManager endpoint expects a specific JSON structure to process your request. Here is the breakdown of the payload:

*
**`provider`** (string): Must be set to `"anthropic"`.


*
**`model_key`** (string): Either `"claude-sonnet-4-5-20250929"` or `"claude-opus-4-6"`.


*
**`query`** (string): Your main text prompt.


*
**`images`** (array of strings, *optional*): A list of image URLs or Base64 encoded data URIs (Supported by Opus 4.6 for `image_to_text` tasks).


*
**`parameters`** (object, *optional*): Model-specific settings:


*
`task`: Usually `"text_to_text"` or `"image_to_text"`.


*
`instructions`: System instructions (e.g., "Be concise").


*
`max_tokens`: The maximum output length.


*
`budget_tokens`: Enables Anthropic's "thinking" feature (requires a budget of at least 1,024 tokens).


*
`effort`: Sets the thinking effort (`"low"`, `"medium"`, or `"high"`) if `budget_tokens` is not explicitly set.





### 4. Code Example (JavaScript / Fetch API)

Here is a drop-in example of how a client-side website can trigger an Anthropic request to your backend:

```javascript
async function fetchClaudeResponse(userPrompt) {
  const payload = {
    provider: "anthropic",
    model_key: "claude-sonnet-4-5-20250929",
    query: userPrompt,
    parameters: {
      task: "text_to_text",
      instructions: "You are a helpful assistant.",
      max_tokens: 4096,
      budget_tokens: 2048 // Enables thinking feature
    }
  };

  try {
    const response = await fetch('https://<your-aimanager-domain>/process_request', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;

  } catch (error) {
    console.error("Error communicating with AIManager:", error);
  }
}

// Example usage:
fetchClaudeResponse("Write a haiku about artificial intelligence.").then(data => {
    console.log("Model Output:", data.outputs[0]);
});

```

### 5. Handling the Response

If successful, AIManager will return a JSON object containing the model's output alongside metadata and cost breakdowns.

**Expected Response Format:**

```json
{
  "outputs": [
    "Artificial minds\nProcessing the human world\nLearning how to dream"
  ],
  "costs": {
    "input_tokens": 25,
    "output_tokens": 15,
    "total_cost": 0.0003
  },
  "metadata": {
    "provider": "anthropic",
    "model_key": "claude-sonnet-4-5-20250929"
  },
  "debug_info": {}
}

```

----
