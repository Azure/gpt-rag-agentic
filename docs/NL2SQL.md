# NL2SQL and Fabric runtime reference

This page describes the implementations in this repository. It is not a
validated deployment guide for the current Agent Landing Zone platform.
See [integration status](../README.md#integration-status) and
[local setup](LOCAL_DEPLOYMENT.md).

## Strategy implementations

Set `AUTOGEN_ORCHESTRATION_STRATEGY` in the runtime environment, not just in a
remote API client's shell.

| Strategy | Agents and tools defined in source |
| --- | --- |
| `nl2sql` | `sql_agent` and `chat_closure`. Tools list data sources and tables, read schema metadata, parse SQL, execute SQL, and obtain dates and times. |
| `nl2sql_fewshot` | `assistant` and `chat_closure`. Adds similar-query retrieval to the SQL tools. It does not add a triage or DAX agent. |
| `chat_with_fabric` | `triage_agent`, `sql_query_agent`, `dax_query_agent`, and `chat_closure`. Defines table, measure, and similar-query retrieval plus SQL and DAX execution tools. |

The orchestrators use AutoGen `SelectorGroupChat`. Few-shot retrieval supplies
examples to the agent. It does not train a model or guarantee query accuracy.

### Fabric integration gaps

`chat_with_fabric` is registered in the factory, but it is not a working
end-to-end path as shipped:

- The orchestrators pass `output_mode` and `output_format` positionally to
  `create_agents`. The Fabric strategy still accepts `text_only` and
  `optimize_for_audio` in those positions.
- Its closure agent requests `chat_closure.txt` or `chat_closure_audio.txt`.
  Neither file exists in `prompts/chat_with_fabric/`. The shipped variants are
  `chat_closure_json.txt`, `chat_closure_text.txt`, and `chat_closure_tts.txt`.

The connector details below describe source paths, not a claim that those
strategy integration gaps have been fixed.

## Authentication

### SQL databases

For `type: "sql_database"`, omitting `uid` selects an Entra token credential
chain that tries managed identity and then Azure CLI credentials.
Prefer this path where it fits your environment. The connector does not
configure a user-assigned identity by client ID or create a database user.
An administrator must grant the chosen identity appropriate database read
permissions and network access.

If `uid` is present, the connector uses SQL authentication and looks up the
password in Key Vault. It does not read a password field from the data source
document.

### Fabric SQL endpoints

For `type: "sql_endpoint"`, the connector uses ODBC service-principal
authentication with `client_id`, `tenant_id`, and a Key Vault secret.
It does not implement managed identity for this path.
Both SQL connectors require ODBC Driver 18 for SQL Server.

### Fabric semantic models

The DAX execution path passes the API request's `access_token` to the Power BI
Execute Queries API. It does not perform an on-behalf-of exchange.
The connector contains a service-principal token helper, but the DAX execution
method does not call it or fall back to it when a user token is missing.
Do not assume that adding a client secret enables app-only DAX execution.

The caller needs a token accepted by the Power BI API and permissions for the
target semantic model. Tenant settings and data-source permissions are
external prerequisites, not provisioned or validated by this code. Consult
the current [Execute Queries API documentation](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/execute-queries)
and [Fabric SQL authentication documentation](https://learn.microsoft.com/en-us/fabric/data-warehouse/entra-id-authentication).
This guide does not prescribe a tenant-wide permission change.

### Secret references

Where a connector uses a secret, it derives the Key Vault name from
`<datasource-id>-secret`. `generate_valid_secret_name` replaces characters
other than letters, digits, and hyphens with hyphens, trims edge hyphens, and
limits the result to 63 characters.
`AZURE_KEY_VAULT_NAME` selects the vault, and secret retrieval uses managed
identity followed by Azure CLI credentials.

Keep secret values out of data source JSON, documentation, and shell history.
Use your approved secret-management process for any required credentials.

### Query safety limitations

`validate_sql_query` uses `sqlparse.parse` and treats a nonempty parse result
as valid. It is not full SQL syntax or permission validation.
`execute_sql_query` checks whether the trimmed query starts with `select`
before sending it to the database. This prefix check is not a read-only
security boundary. Use a least-privilege database identity, and review generated
queries before using this code with sensitive data.

## Data source documents

Data sources are JSON documents in the existing Cosmos DB container selected
by `DATASOURCES_CONTAINER` (default `datasources`).
The execution tools retrieve a document using its ID as both the item key and
partition key. The dictionary's `datasource` value must match that ID.

The models in [`connectors/types.py`](../connectors/types.py) require:

| Type | Fields |
| --- | --- |
| All types | `id`, `description`, `type` |
| `sql_database` | `server`, `database`, and optional `uid` |
| `sql_endpoint` | `server`, `database`, `tenant_id`, `client_id` |
| `semantic_model` | `organization`, `workspace`, `dataset`, `tenant_id`, `client_id` |

For example, a SQL database using token authentication has no `uid` or password:

```json
{
  "id": "adventureworks",
  "description": "AdventureWorksLT sample database.",
  "type": "sql_database",
  "database": "adventureworkslt",
  "server": "sqlservername.database.windows.net"
}
```

The semantic model's `dataset` is the dataset ID used in the request URL,
not a display name. Although `workspace` and `organization` are required by the
model, the current execution URL uses `/v1.0/myorg/datasets/<dataset>/executeQueries`.

The [SQL sample](../samples/sql_database/datasources.json) and
[Fabric samples](../samples/fabric/datasources.json) are starting points, not
ready-to-run resource configurations. The Fabric semantic model sample omits
the required `workspace` field and describes `dataset` as a name.
Supply the required fields and actual IDs in your own configuration.
The runtime does not import these sample files into Cosmos DB.

## Data dictionary and Search indexes

The tools consume metadata already stored in Azure AI Search. This repository
does not ship index definitions, indexers, embedding skillsets, upload scripts,
or an indexing schedule for that metadata. The former ingestion diagram is
not a provisioning contract.

| Consumer | Index and fields used |
| --- | --- |
| `get_all_tables_info` and `get_schema_info` | Fixed `nl2sql-tables` index. Reads `table`, `description`, `datasource`, and `columns` with column `name` and `description`. |
| `tables_retrieval` | `NL2SQL_TABLES_INDEX`, default `nl2sql-tables`. Searches text and/or `contentVector`, depending on the approach, and selects `table` and `description`. |
| `queries_retrieval` | `NL2SQL_QUERIES_INDEX`, default `nl2sql-queries`. Selects `question`, `query`, and `reasoning`, and can filter by `datasource`. Vector search uses `contentVector`. |
| `measures_retrieval` | Fixed `nl2sql-measures` index. Filters by `datasource` and reads `name`, `description`, `type`, `source_table`, `data_type`, and `source_model`. It does not perform vector search. |

Changing `NL2SQL_TABLES_INDEX` does not redirect the fixed-index schema tools.
Do not assume one override changes all table lookups.
Queries use a fixed top count of 3, table relevance retrieval uses 10, and
table and measure listing use up to 1000 results. These tools do not use
`AZURE_SEARCH_TOP_K`.

Search uses `AZURE_SEARCH_SERVICE` and `AZURE_SEARCH_API_VERSION`.
Query and table relevance retrieval support `term`, `vector`, and `hybrid`
through `AZURE_SEARCH_APPROACH`. They generate a query embedding even in
`term` mode. Semantic mode uses `AZURE_SEARCH_USE_SEMANTIC` and
`AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG` when the approach is not vector-only.
Your indexes must support the fields, filters, and vector dimensions used by
these requests.

Existing table and query metadata examples are in
[`samples/sql_database/`](../samples/sql_database/) and
[`samples/fabric/`](../samples/fabric/). Column types and example values in
metadata are not returned by `get_schema_info`, which maps column names to
descriptions. Measure metadata accepts `type` values `local` and `external`.
Those labels describe metadata, not an automated measure deployment.

Arrange and index metadata using a separately verified process. Folder names
such as `tables/` and `queries/` in the samples do not trigger ingestion in
this runtime, and no optional ingestion or current platform integration is
implied.
