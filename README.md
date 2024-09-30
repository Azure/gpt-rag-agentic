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

3. **Modify Prompts**:  
   Agent behavior is guided by prompts located in the `prompts` folder. These prompts define how agents communicate and perform tasks. You can customize these prompts to adjust the behavior of agents in any strategy. For example, if you're creating a new strategy or modifying an existing one, updating these prompt files allows you to control how agents respond and interact within the orchestrator.

## Configuring the `nl2sql` Strategies

The `nl2sql`, `nl2sql_dual`, and `nl2sql_fewshot` strategies enable agents to convert natural language queries into SQL statements to retrieve data from a relational database. While their configurations are similar, the `nl2sql_dual` strategy introduces an additional agent to enhance query formation and response accuracy. The `nl2sql_fewshot` strategy, on the other hand, is based on a single agent but brings similar query examples into the conversation.

To configure and use the `nl2sql` strategy in the agent-based orchestrator, follow these two key steps:

1. **Configure the SQL Database Connection**

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

2. **Updating the Data Dictionary**  
   
    The `nl2sql` strategy uses the data dictionary to understand the database structure. Functions `get_all_tables_info` and `get_schema_info` retrieve table and column details, enabling accurate SQL query generation. Ensure your database's data dictionary in `config/data_dictionary.json` is up-to-date for optimal performance.

3. **NL2SQL Few-Shot Strategy configuration**

    The `nl2sql` few-shot strategy utilizes pre-defined query examples to improve the accuracy of the generated SQL queries. These examples are stored in files with the `.nl2sql` extension, such as [queries.nl2sql](config/queries.nl2sql). The query examples are essential for enabling the model to generate contextually relevant SQL based on the database structure and queries.

    To ensure optimal retrieval of these examples during query generation, you need to ingest the `.nl2sql` files into an AI Search Index using the [gpt-rag-ingestion](https://github.com/azure/gpt-rag-ingestion) component. This ensures that the query examples are efficiently indexed and retrieved in real time, enhancing the performance of the `nl2sql` strategy.

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

```
azd auth login  
azd env refresh  
azd deploy  
```

> [!NOTE] 
> Note: when running the ```azd env refresh```, use the same environment name, subscription, and region used in the initial provisioning of the infrastructure.

## Running Locally with VS Code  
   
[How can I test the solution locally in VS Code?](docs/LOCAL_DEPLOYMENT.md)

## Evaluating

[How to test the orchestrator performance?](docs/LOADTEST.md)

## Contributing

We appreciate your interest in contributing to this project! Please refer to the [CONTRIBUTING.md](https://github.com/Azure/GPT-RAG/blob/main/CONTRIBUTING.md) page for detailed guidelines on how to contribute, including information about the Contributor License Agreement (CLA), code of conduct, and the process for submitting pull requests.

Thank you for your support and contributions!

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
