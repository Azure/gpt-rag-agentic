# Enterprise RAG Agentic Orchestrator

This Orchestrator is part of the **Enterprise RAG (GPT-RAG)** Solution Accelerator. 

To learn more about the Enterprise RAG, please go to [https://aka.ms/gpt-rag](https://aka.ms/gpt-rag).

## How the Agentic Orchestrator Works

The **Enterprise RAG Agentic Orchestrator** utilizes AutoGen's group chat feature to enable multiple agents to collaborate on complex tasks. In this system, agents are created based on the chosen strategy and interact in a chat-like environment to achieve a common goal. Each agent has a distinct role—such as querying databases, retrieving knowledge, or synthesizing information—and they work together in a sequence to provide a comprehensive response.

The orchestrator coordinates these interactions, allowing for multiple rounds of conversation between agents, ensuring tasks are completed efficiently. The group chat feature is highly customizable, and users can define their own strategies and agent behaviors to suit specific business needs.

## Selecting an Agent Strategy

You can select an agent strategy through environment variables. By default, the orchestrator uses the `classic-rag` strategy, which is optimized for retrieving information from a knowledge base. Alternatively, the `nl2sql` strategy can be selected for scenarios where natural language queries are converted into SQL to query a relational database.

To configure the orchestrator to use a specific agent strategy:

1. **Set the environment variable**:  
   Set `AUTOGEN_ORCHESTRATION_STRATEGY` to the desired strategy name.
   
   Example:
   ```bash
   export AUTOGEN_ORCHESTRATION_STRATEGY=nl2sql
   ```

2. **Available Strategies**:
   - **classic-rag**: Retrieves answers from a knowledge base.
   - **nl2sql**: Converts user questions into SQL queries to retrieve data from a relational database.

## Customizing or Creating New Strategies

You can extend the orchestrator by creating your own agent creation strategies to meet specific needs. These strategies define how agents are created and interact with each other.

1. **Create a Custom Strategy**:  
   Subclass `BaseAgentCreationStrategy` and implement the `create_agents` method to define how your agents behave.
   
2. **Register the Custom Strategy**:  
   Register your strategy with the `AgentCreationStrategyFactory` so that it can be selected using the appropriate environment variable.

3. **Modify Prompts**:  
   Agent behavior is guided by prompts located in the `prompts` folder. These prompts define how agents communicate and perform tasks. You can customize these prompts to adjust the behavior of agents in any strategy. For example, if you're creating a new strategy or modifying an existing one, updating these prompt files allows you to control how agents respond and interact within the orchestrator.

## Configuring the `nl2sql` Strategy

The `nl2sql` strategy enables agents to convert natural language queries into SQL statements to retrieve data from a relational database. 

To configure and use the `nl2sql` strategy in the agent-based orchestrator, follow these two key steps:

1. **Configure the SQL Database Connection**  

   Set up the connection to your SQL Database by ensuring your identity has the `db_datareader` permission and configure the connection by setting the following environment variables:
   
```bash
   export SQL_DATABASE_SERVER=my-database-server
   export SQL_DATABASE_NAME=my-database-name
   ```   

> [!NOTE]
> Assumes SQL Database. Adjust settings for other databases as needed.

The connection to the SQL Database uses ODBC and Azure Entra ID for authentication, supporting managed identities. For more details on configuring these permissions, refer to [this guide](https://learn.microsoft.com/azure/azure-sql/database/azure-sql-python-quickstart).

2. **Updating the Data Dictionary**  
   
    The `nl2sql` strategy uses the data dictionary to understand the database structure. Functions `get_all_tables_info` and `get_schema_info` retrieve table and column details, enabling accurate SQL query generation. Ensure your database's data dictionary in `config/data_dictionary.json` is up-to-date for optimal performance.

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
