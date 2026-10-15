# Local setup and runtime reference

This is a source-level guide to the Azure Functions application in this
repository, not a deployment path for the current Agent Landing Zone release.
Read the [support and integration status](../README.md#integration-status) first.
Running the function locally still uses remote Azure services. It is not an
offline emulator for the whole application.

## Prerequisites

- Python compatible with your Azure Functions host and the packages in
  [`requirements.txt`](../requirements.txt). The repository does not pin an
  interpreter version.
- Azure Functions Core Tools for local execution.
- Azurite for the Functions host storage configured by the local template.
- Existing Azure OpenAI deployments, a Cosmos DB database and conversation
  container, and any Search indexes, blobs, databases, or Key Vault secrets
  needed by your chosen strategy.
- An identity with access to those resources and network connectivity to them.
  The service connectors generally try `ManagedIdentityCredential` and then
  `AzureCliCredential`. A local process needs an already available developer
  credential. A deployed app needs an appropriately authorized identity.

Use managed identity for service access where implemented. Do not add an
OpenAI API key merely because the templates contain an `AZURE_OPENAI_API_KEY`
placeholder. The runtime model clients use Entra tokens.
This does not change the function-key authentication used by the HTTP API.

## Prepare a local environment

From the repository root:

```bash
python -m venv .venv
```

Activate the virtual environment for your shell, then install the runtime
dependencies:

```bash
python -m pip install -r requirements.txt
```

For SQL strategies, the connectors also require **ODBC Driver 18 for SQL
Server** on the machine. Installing `pyodbc` alone does not install that driver.
Check dependency and interpreter compatibility for your environment.

Copy `local.settings.json.template` to the ignored file `local.settings.json`
and edit the local copy. The shipped template contains an invalid JSON line
starting with `"AZURE_STORAGE_CONTAINER:`. Remove that line from your local
copy. The runtime does not read that setting. Check that the result is valid
JSON before starting Functions.

Replace the settings used by your selected strategy with the names of your
existing resources. Remove unused secret placeholders rather than adding
credentials to the file. Keep local settings, tokens, and generated
conversation data out of version control.

Start Azurite and then run:

```bash
func start
```

Use the URLs reported by the local host. With the usual port and route prefix,
the routes are `http://localhost:7071/api/orc` and
`http://localhost:7071/api/orcstream`.

VS Code's Azure Functions and Azurite extensions can help with local execution.
This repository does not ship a `.vscode` debug configuration, so F5 alone is
not a complete setup procedure.

## Configuration read by the code

The runtime reads process environment variables. It does not load Azure App
Configuration. The Functions host supplies `Values` from `local.settings.json`
locally and application settings in Azure. Neither `function_app.py` nor the
evaluation input generator loads `.env` automatically.

The [environment template](../.env.template) and
[`app_settings.json`](../app_settings.json) are examples, not an automatically
applied configuration or a list of universally required settings.

| Area | Settings and behavior |
| --- | --- |
| Strategy | `AUTOGEN_ORCHESTRATION_STRATEGY` defaults to `classic_rag` when absent. The code replaces hyphens with underscores before enum lookup. `.env.template` and `app_settings.json` select `multimodal_rag`, while the local settings template selects `classic_rag`. |
| Conversation storage | `AZURE_DB_ID` is the Cosmos DB account name used to build the endpoint. `AZURE_DB_NAME` selects the database. `CONVERSATION_CONTAINER` defaults to `conversations`. The code uses existing containers, not a provisioning step. |
| Model access | `AZURE_OPENAI_RESOURCE` builds the `https://<resource>.openai.azure.com` endpoint. Set `AZURE_OPENAI_API_VERSION` and `AZURE_OPENAI_CHATGPT_DEPLOYMENT` for the helper client as well as the strategy client. `AZURE_OPENAI_CHATGPT_MODEL`, `AZURE_OPENAI_MAX_TOKENS`, and `AZURE_OPENAI_TEMPERATURE` configure the strategy model client. |
| Embeddings | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` selects the embedding deployment used by retrieval tools. The runtime does not read `AZURE_OPENAI_EMBEDDING_MODEL`. |
| RAG search | `AZURE_SEARCH_SERVICE`, `AZURE_SEARCH_INDEX` (default `ragindex`), `AZURE_SEARCH_API_VERSION` (default `2024-07-01`), and `AZURE_SEARCH_TOP_K` (default `3`) configure document retrieval. Classic RAG supports `term`, `vector`, and `hybrid` via `AZURE_SEARCH_APPROACH` (default `hybrid`). Multimodal retrieval builds vector queries over both `contentVector` and `captionVector`. |
| Semantic search | Multimodal and NL2SQL search paths use `AZURE_SEARCH_USE_SEMANTIC` and `AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG`. The classic RAG function reads these settings but does not add semantic query parameters to its request. |
| Secret lookup | `AZURE_KEY_VAULT_NAME` is used by the database connectors when their authentication path requires an existing secret. See [NL2SQL](NL2SQL.md). |
| Logging | `LOGLEVEL` defaults to `INFO` in `function_app.py`. `host.json` contains Functions logging and sampling settings. |

These defaults describe source behavior, not recommended model versions or a
validated deployment configuration. Use an index schema compatible with the
selected retrieval tool. This repository does not provision or populate those
indexes.

### Resource permissions

Have your resource administrator grant the runtime identity only the access
needed by the selected strategy. Typical service roles include:

- Cosmos DB Built-in Data Contributor for conversation reads and writes.
- Cognitive Services OpenAI User for model calls.
- Search Index Data Reader for search queries.
- Storage Blob Data Reader for image blobs used by multimodal retrieval.
- Key Vault Secrets User when a database connector needs secret retrieval.

These roles do not configure network access or create resources. SQL database
permissions are separate. See the [database authentication details](NL2SQL.md#authentication).
The code does not select a user-assigned managed identity by client ID, so do
not assume that assigning one alone configures these credential chains.

## API contract

[`function_app.py`](../function_app.py) declares function-level authentication
and two POST routes:

| Route | Response |
| --- | --- |
| `/api/orc` | JSON with `conversation_id`, `answer`, `reasoning`, `thoughts`, and `data_points` after group-chat execution. |
| `/api/orcstream` | A `text/event-stream` response containing raw text chunks. The streaming orchestrator emits the conversation ID before model text. It does not emit JSON objects or standard `data:` event envelopes. |

The paths above use the default Functions `/api` prefix. A request body needs a
nonempty `question`. An empty or omitted `conversation_id` starts a new
conversation. For example:

```json
{
  "question": "What information is available?",
  "conversation_id": ""
}
```

Missing or empty `question` returns HTTP 400. The routes also accept
`client_principal_id`, `client_principal_name`, `client_group_names`, and
`access_token`. The streaming route accepts `optimize_for_audio`, not
`text_only`.

Principal fields come from the request body. The route code does not validate
them as authenticated identity claims. It also does not check conversation
ownership before loading an existing ID. Do not expose this API on the
assumption that function keys or caller-supplied principal fields provide
per-user authorization. Review access controls at the hosting boundary.

### Client limitations

`chat.sh` and `chat.ps1` launch `chat.py`. That script imports `Orchestrator`,
which is not exported by the current `orchestration` package. The import occurs
before REST mode is selected, so `USE_REST_API=true` does not resolve the issue.
The wrappers also check the old `autogen` package name rather than the
`autogen-agentchat` dependency in `requirements.txt`.

`chat_stream.py` uses `STREAMING_ENDPOINT` (default
`http://localhost:7071/api/orcstream`) and requires `FUNCTION_KEY`. It sends a
fixed sample question and a `text_only` field that the route does not read.
It is not an interactive replacement for `chat.py`.

## Cloud deployment limitations

[`azure.yaml`](../azure.yaml) defines a Python Functions service named
`orchestrator`. Both preprovision hooks deliberately exit with an error for
`azd provision` and `azd up`. They refer to historical GPT-RAG infrastructure
and suggest `azd env refresh` followed by `azd deploy` for an existing matching
environment.

Those hooks do not prove compatibility with the current Agent Landing Zone
infrastructure or its Container Apps runtime. Do not run them against a
current platform environment as a replacement procedure.
Publishing with Functions Core Tools also requires an existing, compatible
Function App, settings, permissions, and native dependencies. This repository
does not provide a validated standalone infrastructure path.
