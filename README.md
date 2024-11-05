# Enterprise RAG Agentic Orchestrator

This Orchestrator is part of the **Enterprise RAG (GPT-RAG)** Solution Accelerator.

To learn more about the Enterprise RAG, please go to [https://aka.ms/gpt-rag](https://aka.ms/gpt-rag).

## How the Agentic Orchestrator Works

The **Enterprise RAG Agentic Orchestrator** utilizes AutoGen's group chat feature to enable multiple agents to collaborate on complex tasks. In this system, agents are created based on the chosen strategy and interact in a chat-like environment to achieve a common goal. Each agent has a distinct role—such as querying databases, retrieving knowledge, or synthesizing information—and they work together in a sequence to provide a comprehensive response.

The orchestrator coordinates these interactions, allowing for multiple rounds of conversation between agents, ensuring tasks are completed efficiently. The group chat feature is highly customizable, and users can define their own strategies and agent behaviors to suit specific business needs.

## Selecting an Agent Strategy

You can select an agent strategy through environment variables. By default, the orchestrator uses the `classic_rag` strategy, which is optimized for retrieving information from a knowledge base. Alternatively, the `nl2sql` and the experimental `nl2sql_dual` strategies can be selected for scenarios where natural language queries are converted into SQL to query a relational database.

### Available Strategies

- **classic_rag**: Retrieves answers from a knowledge base.
- **nl2sql**: Converts user questions into SQL queries to retrieve data from a relational database.

#### Experimental Strategies

- **nl2sql_dual**: Introduces a second agent to review and refine SQL queries and responses for improved accuracy and clarity.
- **nl2sql_fewshot**: A variation of the single-agent approach that uses AI search to find similar queries, improving SQL generation accuracy.

To configure the orchestrator to use a specific agent strategy:

1. **Set the environment variable**:  
   Set `AUTOGEN_ORCHESTRATION_STRATEGY` to the desired strategy name.

   Example:

   ```bash
   export AUTOGEN_ORCHESTRATION_STRATEGY=nl2sql
   ```

## Customizing or Creating New Strategies

You can extend the orchestrator by creating your own agent creation strategies to meet specific needs. These strategies define how agents are created and interact with each other.

1. **Create a Custom Strategy**:  
   Subclass `BaseAgentCreationStrategy` and implement the `create_agents` method to define how your agents behave.

2. **Register the Custom Strategy**:  
   Register your strategy with the `AgentCreationStrategyFactory` so that it can be selected using the appropriate environment variable.

## Modifying Prompts

Agent behavior is guided by prompt files located in the `prompts` directory. These prompts define how agents communicate and perform tasks. You can customize these prompts to adjust the behavior of agents in any strategy.

### Prompt File Structure

- **Base Directory**: `prompts/`
- **Strategy Subdirectory**: If your strategy has a `strategy_type`, prompts are located in `prompts/{strategy_type}/`.
- **Prompt Files**:
  - **Default Prompt File**: `{agent_name}.txt`
  - **Custom Prompt File**: `{agent_name}.custom.txt`

### Using Custom Prompt Files

To customize an agent's prompt without altering the default prompt file, you can create a custom prompt file:

1. **Create a Custom Prompt File**:
   - Name your custom prompt file as `{agent_name}.custom.txt`.
   - Place it in the appropriate prompts directory (e.g., `prompts/{strategy_type}/`).

2. **Prompt File Lookup Order**:
   - The orchestrator will first look for `{agent_name}.custom.txt`.
   - If not found, it will fall back to `{agent_name}.txt`.
   - If neither file is found, an error will be raised.

### Using Placeholders in Prompts

Prompts can contain placeholders that will be dynamically replaced at runtime. Placeholders follow the format `{{placeholder_name}}`.

#### Placeholder Replacement Process

1. **Provided Placeholders**:
   - When reading the prompt, you can supply a `placeholders` dictionary where keys are placeholder names and values are their replacements.
   - Any placeholders matching the keys in this dictionary will be replaced with their corresponding values.

2. **Common Placeholder Files**:
   - For any remaining placeholders not replaced by the provided `placeholders` dictionary, the orchestrator will search for files named `{placeholder_name}.txt` in the `prompts/common/` directory.
   - If such a file exists, the placeholder will be replaced with the content of that file.

3. **Unmatched Placeholders**:
   - If a placeholder cannot be replaced (i.e., no provided value and no matching file), a warning will be logged, and the placeholder will remain in the prompt.

#### Example

Suppose you have a prompt for an agent named `assistant` with the following content:

```
{{greeting}}

I am here to assist you with your tasks.

{{closing}}
```

- **Using Provided Placeholders**:
  - If you supply a `placeholders` dictionary like `{'greeting': 'Hello there!', 'closing': 'Best regards.'}`, the placeholders `{{greeting}}` and `{{closing}}` will be replaced accordingly.

- **Using Common Placeholder Files**:
  - If you do not provide values for `{{greeting}}` and `{{closing}}`, the orchestrator will look for `prompts/common/greeting.txt` and `prompts/common/closing.txt`.
  - If these files exist and contain text, the placeholders will be replaced with that content.

- **Unmatched Placeholders**:
  - If neither the `placeholders` dictionary provides values nor the common files exist, the placeholders will remain in the prompt, and a warning will be logged.

## Configuring the `nl2sql` Strategies

The `nl2sql`, `nl2sql_dual`, and `nl2sql_fewshot` strategies enable agents to convert natural language queries into SQL statements to retrieve data from a relational database. While their configurations are similar, the `nl2sql_dual` strategy introduces an additional agent to enhance query formation and response accuracy. The `nl2sql_fewshot` strategy, on the other hand, is based on a single agent but brings similar query examples into the conversation.

### Configuring the SQL Database Connection

To set up the connection to your SQL Database, ensure your identity has `db_datareader` permissions. Configure the connection using the following environment variables either in the Function App settings or as local environment variables for testing purposes:

```bash
SQL_DATABASE_SERVER=my-database-server
SQL_DATABASE_NAME=my-database-name
SQL_DATABASE_TYPE=[sqldatabase or fabric]
```

- **For SQL Database**: Use `SQL_DATABASE_SERVER` as your database server name and `SQL_DATABASE_NAME` as your database name.

- **For Fabric SQL Endpoint**: Use `SQL_DATABASE_SERVER` as the full SQL connection string and `SQL_DATABASE_NAME` as the name of the Lakehouse or Warehouse you want to connect to.

The connection to the SQL Database uses ODBC and Azure Entra ID for authentication, supporting managed identities. For more information on configuring SQL Database permissions, refer to [this guide](https://learn.microsoft.com/azure/azure-sql/database/azure-sql-python-quickstart).

> **Note:**  
> Both SQL Database and Fabric SQL Endpoints are supported. If you are working with other database types, you may need to adjust the [SQLDBClient](connectors/sqldbs.py) accordingly.

### Configuring the Teradata Connection

The `nl2sql` strategies can also be configured to connect to a Teradata database. To set up the connection to your Teradata database, ensure you have the necessary permissions and that your credentials are securely managed.

1. **Install the Teradata SQL Driver**

   Ensure that the `teradatasql` Python library is installed in your environment:

   ```bash
   pip install teradatasql
   ```

2. **Set the Environment Variables**

   Configure the connection using the following environment variables, similar to how it's done for SQL Database:

   ```bash
   TD_HOST=teradata-host
   TD_USER=teradata-username
   ```

   Add the Teradata password to the solution Key Vault as a secret named `teradataPassword`.

3. **Permissions**

   Make sure that your Teradata user account has the necessary permissions to execute queries and access the required tables.

By configuring these settings, the orchestrator's `nl2sql` strategies can connect to a Teradata database and execute SQL queries generated from natural language inputs.

> **Note:** The `SQLDBClient` in the orchestrator supports Teradata connections using the `teradatasql` library. It reads connection parameters from environment variables, and the password is securely retrieved from the Key Vault.

### Updating the Data Dictionary

The `nl2sql` strategy uses the data dictionary to understand the database structure. Functions `get_all_tables_info` and `get_schema_info` retrieve table and column details, enabling accurate SQL query generation. Ensure your database's data dictionary in `config/data_dictionary.json` is up-to-date for optimal performance.

### NL2SQL Few-Shot Strategy Configuration

The `nl2sql_fewshot` strategy utilizes pre-defined query examples to improve the accuracy of the generated SQL queries. These examples are stored in files with the `.json` extension, such as these [samples](https://github.com/Azure/gpt-rag-ingestion/tree/main/samples/nl2sql). The query examples are essential for enabling the model to generate contextually relevant SQL based on the database structure and queries.

To ensure optimal retrieval of these examples during query generation, ingest the query sample files into an AI Search Index using the [gpt-rag-ingestion](https://github.com/Azure/gpt-rag-ingestion/blob/main/docs/NL2SQL_INGESTION.md) component. This ensures that the query examples are efficiently indexed and retrieved in real time, enhancing the performance of the `nl2sql` strategy.

> **Note:** Ensure that the examples in `.nl2sql` files are clear and contextually relevant to your database queries to maximize the model's performance in the `nl2sql` strategy.

By following these steps, you can configure and customize the `nl2sql` strategy to handle SQL queries effectively. The flexibility of this strategy also allows for adaptation to other data sources beyond SQL databases.

## Cloud Deployment

To deploy the orchestrator in the cloud for the first time, please follow the deployment instructions provided in the [Enterprise RAG repo](https://github.com/Azure/GPT-RAG?tab=readme-ov-file#getting-started).

These instructions include the necessary infrastructure templates to provision the solution in the cloud.

Once the infrastructure is provisioned, you can redeploy just the orchestrator component using the instructions below:

First, please confirm that you have met the prerequisites:

- Azure Developer CLI: [Download azd for Windows](https://azdrelease.azureedge.net/azd/standalone/release/1.5.0/azd-windows-amd64.msi), [Other OS's](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd).
- Git: [Download Git](https://git-scm.com/downloads)
- Python 3.11: [Download Python](https://www.python.org/downloads/release/python-3118/)

Then just clone this repository and reproduce the following commands within the gpt-rag-orchestrator directory:

```bash
azd auth login
azd env refresh
azd deploy
```

> **Note:** When running the `azd env refresh`, use the same environment name, subscription, and region used in the initial provisioning of the infrastructure.

## Running Locally with VS Code

[How can I test the solution locally in VS Code?](docs/LOCAL_DEPLOYMENT.md)

## Evaluating

To assess the performance of the Orchestrator, we have provided an evaluation program that allows you to test and measure its capabilities.

For detailed instructions on how to run the evaluation program, set up the environment, and prepare test data, please refer to the [Evaluation Documentation](docs/EVALUATION.md).

## Contributing

We appreciate your interest in contributing to this project! Please refer to the [CONTRIBUTING.md](https://github.com/Azure/GPT-RAG/blob/main/CONTRIBUTING.md) page for detailed guidelines on how to contribute, including information about the Contributor License Agreement (CLA), code of conduct, and the process for submitting pull requests.

Thank you for your support and contributions!

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.