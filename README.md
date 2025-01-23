# Enterprise RAG Agentic Orchestrator

Part of [GPT-RAG](https://aka.ms/gpt-rag)

## Table of Contents

1. [**Concepts**](#concepts)
   - [1.1 How the Orchestrator Works](#how-the-orchestrator-works)
   - [1.2 Agent Strategies](#selecting-an-agent-strategy)
   - [1.3 Create your Own Agent Strategy](#how-to-add-and-configure-you-own-agent-strategies)
2. [**Running the Orchestrator**](#running-the-orchestrator)
   - [2.1 Cloud Deployment](#cloud-deployment)
   - [2.2 Running the Chat Client Locally](#running-the-chat-client-locally)
   - [2.3 Running the Function Locally](docs/LOCAL_DEPLOYMENT.md)
3. [**NL2SQL Strategies Configuration**](#nl2sql-strategies-configuration)
   - [3.1 Configuring NL2SQL Strategies](#configuring-nl2sql-strategies)
   - [3.2 Data Dictionary and Query samples](#nl2sql-data)
   - [3.3 Database Connection Setup](#database-connection-setup)
   - [3.3.1 SQL Database Connection](#sql-database-connection)
4. [**Evaluation**](#evaluation)
5. [**Contributing**](#contributing)
6. [**Trademarks**](#trademarks)

---

## Concepts

### How the Orchestrator Works

The **GPT-RAG Agentic Orchestrator** is a powerful system that leverages AutoGen's AgetChat programming framework to facilitate collaboration among multiple specialized agents. This orchestrator is designed to handle complex tasks by coordinating the interactions of agents, each with a specific role, to produce coherent and accurate responses. For more details about AutoGen, refer to its [documentation](https://microsoft.github.io/autogen/stable/).

#### Multi-Agent Group Chat    
     
Our orchestrator employs AutoGen's `Selector Group Chat` pattern to facilitate dynamic conversations involving multiple agents. The group chat coordinates agent interactions based on the selected strategy.

![Selector Group Chat](media/selector-group-chat.svg)
<BR>*Example of a Group Chat obtained from the AutoGen documentation.*

> [!Note]
> The agents shown here are examples. You can define your own agents tailored to your use cases.

#### Agent Strategies

The orchestrator uses a factory pattern to create agents based on predefined strategies. The `AgentStrategyFactory` handles the creation of agents for each selected strategy, such as `classic_rag` or `nl2sql`. Each strategy defines a unique set of agents, their roles, and their interactions within the group chat.

Different strategies support various queries and data interactions:

- **Classic RAG Strategy (`classic_rag`)**: This strategy centers on retrieval-augmented generation, where agents collaborate to retrieve relevant information from a knowledge base and generate responses based on that information.
- **NL2SQL Strategy (`nl2sql`)**: This strategy translates natural language queries into SQL statements, enabling users to interact with databases using everyday language.

#### Elements of a Strategy:
     
- **The Agents Team**: Agents are instantiated with distinct roles and system messages. For example, in the `multimodal_rag` strategy, the agents include:    
       
   - **Assistant Agent**: Processes the user ask and invokes the necessary tools, such as `multimodal_vector_index_retrieve`, to gather relevant data. 
   - **Multimodal Message Creator**: Constructs a `MultiModalMessage` containing text and image data, ensuring the response is based on multimodal content. 
     
- **Functions used by agents**: Functions (or tools) empowers agents it with specific capabilities such as data retrieval or executing complex queries. There's no need to register tools separately, simply inform the `AssistantAgent` which tool to execute.    
     
- **Agent Selection**: Transition rules are established to control the flow of conversations between agents. The **Selector Function** defines rules for selecting the next agent to engage in the conversation based on the current context and message flow.    

#### Customization and Extensibility

The orchestrator is highly customizable, allowing developers to define custom strategies and agent behaviors. By subclassing `BaseAgentStrategy` and implementing the `create_agents` method, new strategies can be created to meet specific requirements. This extensibility ensures that the orchestrator can adapt to a wide range of operational scenarios.

### Selecting an Agent Strategy

The **GPT-RAG Agentic Orchestrator** provides a range of agent strategies to handle different types of queries and data interactions. Selecting the appropriate strategy ensures that the orchestrator operates efficiently and meets the specific needs of your application. This section outlines how to select a strategy and provides detailed descriptions of the available strategies.

### How to Select a Strategy

The orchestrator selects the agent strategy based on the `AUTOGEN_ORCHESTRATION_STRATEGY` environment variable. Be sure to set this variable to the name of the desired strategy. If you're running the chat client locally, set this variable in your shell environment. For deployments as a Function App, define it in the application settings.

#### Available Strategies

The orchestrator supports the following strategies, each tailored to specific needs:

- **Classical RAG**: The `classic_rag` strategy is the default mode of operation for the orchestrator. It is optimized for retrieving information from a predefined knowledge base indexed as an AI Search Index. This strategy leverages retrieval-augmented generation (RAG) techniques to fetch and synthesize information from existing documents or databases, ensuring accurate and relevant responses based on the available data.

- **Multimodal RAG**: In the `multimodal_rag` strategy, user queries are searched in an index containing text content and image descriptions. The system combines text and images to generate a comprehensive response.

- **NL2SQL**: The `nl2sql` strategy enables the orchestrator to convert natural language queries into SQL statements. This allows users to interact with relational databases using everyday language, simplifying data retrieval processes without the need to write complex SQL queries. Currently, this strategy is designed to execute queries on SQL databases in Azure.

- **NL2SQL Fewshot**: The `nl2sql_fewshot` strategy enhances the standard `nl2sql` approach by utilizing AI-driven search to identify similar past queries. This few-shot learning technique improves the accuracy and relevance of the generated SQL statements by learning from a limited set of examples, thereby refining the query translation process.

- **NL2SQL Fewshot Scales**: This strategy enhances `nl2sql_fewshot` by using AI Search Indexes to handle cases with numerous tables or columns. It identifies the most relevant schema elements based on the user's question, enabling precise SQL generation even in complex database environments.

### How to Add and Configure you Own Agent Strategies

If the available strategies don’t fully meet your requirements, you can extend the orchestrator by implementing custom strategies. This flexibility lets you adapt the orchestrator’s behavior to unique use cases and operational demands.

Define custom agent strategies by specifying distinctive agent behaviors. To create a custom strategy:

1. **Subclass** `BaseAgentStrategy` and implement the `create_agents` method.
2. **Register** the strategy in `AgentStrategyFactory` for environment variable selection.

**Steps to Add a Custom Strategy:**

1. **Create the Strategy Class:**  
   Define a new strategy by inheriting from the base strategy class and specifying the required logic.
   
   ```python
   from .strategies.base_strategy import BaseAgentStrategy

   class CustomAgentStrategy(BaseAgentStrategy):
       def execute(self, query):
           # Implement custom strategy logic here
           pass
   ```

2. **Update the AgentStrategyFactory:**  
   Modify `AgentStrategyFactory` to recognize and instantiate your custom strategy.

   ```python
   from .strategies.custom_agent_strategy import CustomAgentStrategy

   class AgentStrategyFactory:
       @staticmethod
       def get_strategy(strategy_type: str):
           # Existing strategy selections
           if strategy_type == 'custom':
               return CustomAgentStrategy()
           # Other strategies...
           else:
               raise ValueError(f"Unknown strategy type: {strategy_type}")
   ```

Ensure the `AUTOGEN_ORCHESTRATION_STRATEGY` environment variable is correctly set to the desired strategy name, whether a predefined strategy or a custom one you’ve implemented.

> [!NOTE]
> The name `custom` is used here as an example. You should choose a name that best represents your specific case.

---

## Running the Orchestrator

### Cloud Deployment

**Option 1: Deploy the orchestrator to the cloud using the Azure Developer CLI**

```bash
azd auth login
azd env refresh
azd deploy
```

Ensure [Python 3.11](https://www.python.org/downloads/release/python-3118/) and [Azure Developer CLI](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd) are installed.

**Option 2: Using Azure Functions Core Tools**

```bash
az login
func azure functionapp publish FUNCTION_APP_NAME --python
```

*Replace FUNCTION_APP_NAME with your Orchestrator Function App name before running the command* 

After finishing the deployment run the following command to confirm the function was deployed:  
```bash
func azure functionapp list-functions FUNCTION_APP_NAME
```

Ensure [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=windows%2Cisolated-process%2Cnode-v4%2Cpython-v2%2Chttp-trigger%2Ccontainer-apps&pivots=programming-language-python#install-the-azure-functions-core-tools) and  [AZ CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) ar installed.


### Running the Chat Client Locally

1. Make sure your user has the roles needed to access CosmosDB and AI Search.

### Bash
```bash
# Set variables for Cosmos DB role assignment
resourceGroupName='your resource group name'  # Name of your resource group
cosmosDbaccountName='CosmosDB Service name'   # Name of your CosmosDB account
roleDefinitionId='00000000-0000-0000-0000-000000000002'  # Built-in CosmosDB role ID for Data Contributor
principalId='Object id of your user in Microsoft Entra ID'  # Object ID of the user in Microsoft Entra ID

# Assign CosmosDB Data Contributor role to the user
az cosmosdb sql role assignment create --account-name $cosmosDbaccountName --resource-group $resourceGroupName --scope "/" --principal-id $principalId --role-definition-id $roleDefinitionId

# Set variables for Azure OpenAI role assignment
subscriptionId='your subscription id'  # Subscription ID
openAIAccountName='Azure OpenAI service name'  # Name of the Azure OpenAI service

# Assign Cognitive Services OpenAI User role
az role assignment create --role "Cognitive Services OpenAI User" --assignee $principalId --scope /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName

# Set variables for Cognitive Search role assignment
searchServiceName='Azure Cognitive Search service name'  # Name of your Azure AI Search service

# Assign Search Index Data Reader role
az role assignment create --role "Search Index Data Reader" --assignee $principalId --scope /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.Search/searchServices/$searchServiceName
```

### PowerShell
```powershell
# Set variables for Cosmos DB role assignment
$resourceGroupName='your resource group name'  # Name of your resource group
$cosmosDbaccountName='CosmosDB Service name'   # Name of your CosmosDB account
$roleDefinitionId='00000000-0000-0000-0000-000000000002'  # Built-in CosmosDB role ID for Data Contributor
$principalId='Object id of your user in Microsoft Entra ID'  # Object ID of the user in Microsoft Entra ID

# Assign CosmosDB Data Contributor role to the user
az cosmosdb sql role assignment create --account-name $cosmosDbaccountName --resource-group $resourceGroupName --scope "/" --principal-id $principalId --role-definition-id $roleDefinitionId

# Set variables for Azure OpenAI role assignment
$subscriptionId='your subscription id'  # Subscription ID
$openAIAccountName='Azure OpenAI service name'  # Name of the Azure OpenAI service

# Assign Cognitive Services OpenAI User role
az role assignment create --role "Cognitive Services OpenAI User" --assignee $principalId --scope /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName

# Set variables for Cognitive Search role assignment
$searchServiceName='Azure Cognitive Search service name'  # Name of your Azure AI Search service

# Assign Search Index Data Reader role
az role assignment create --role "Search Index Data Reader" --assignee $principalId --scope /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.Search/searchServices/$searchServiceName
``` 
2. Rename the `.env.template` file to `.env` and update the variables as needed.

3. Run `./chat.sh` (for Bash) or `./chat.ps1` (for PowerShell) to start the client locally.

![chat client](media/running_chat_client.png)

### Running the Function Locally

To run the Azure Function locally, see [Testing the Solution Locally in VS Code](docs/LOCAL_DEPLOYMENT.md).

---

## NL2SQL Strategies Configuration

### Configuring NL2SQL Strategies

This section provides configuration steps for the various NL2SQL strategies. These strategies convert natural language queries into SQL statements compatible with your databases.

### NL2SQL Data

**Data Dictionary**

The Data Dictionary is essential for SQL generation, providing a structured reference for database tables and columns. If you're using the standard `nl2sql` strategy, simply review and update the `config/data_dictionary.json` file as needed.

> [!NOTE]
> If you prefer, you can create a `config/data_dictionary.custom.json` file, which will override the example file in `config/data_dictionary.json`.

If you're using the `nl2sql_fewshot_scaled` strategy, the `data_dictionary.json` file will not be used. In this case, you'll need to create the JSON files differently to be indexed. You can refer to the examples in [gpt-rag-ingestion](https://github.com/azure/gpt-rag-ingestion) to see how to set up the table and column files for AI Search indexing.

**Queries**

If you've chosen the `nl2sql_fewshot` or `nl2sql_fewshot_scaled` strategy, you'll need to create example queries and index them in AI Search. For guidance on creating and indexing queries, as well as for example queries, refer to [gpt-rag-ingestion](https://github.com/azure/gpt-rag-ingestion).

### Database Connection Setup

Set up database connections by configuring the required environment variables for each target database.

### SQL Database Connection

To set up a connection to your SQL Database, follow these steps based on your authentication method.

1. **Configure environment variables:**

    ```bash
    SQL_DATABASE_SERVER=my-database-server
    SQL_DATABASE_NAME=my-database-name
    ```

    - If using **SQL Authentication**, also set the following environment variable and store the user's password securely in Key Vault as a secret named `sqlDatabasePassword`:
      
      ```bash
      SQL_DATABASE_UID=my-username
      ```

    - If using **Azure Active Directory (AAD) Authentication**, **do not set** the `SQL_DATABASE_UID` variable. The application will use the identity associated with your environment.

2. **Permissions:**
    Ensure your identity has the `db_datareader` role on the database. For more details on setting up your permissions, refer to the [SQL Database Setup Guide](https://learn.microsoft.com/azure/azure-sql/database/azure-sql-python-quickstart).

3. **Connection details in code:**

   - If `SQL_DATABASE_UID` is set, the code will use SQL Authentication, retrieving the password from the Key Vault.
   - If `SQL_DATABASE_UID` is not set, the code will default to Azure AD token-based authentication. 

## Evaluation

An evaluation program is provided for testing the orchestrator's performance. 
<BR>Refer to the [Evaluation Documentation](docs/EVALUATION.md) for details.

## Contributing

For contribution guidelines, refer to [CONTRIBUTING.md](https://github.com/Azure/GPT-RAG/blob/main/CONTRIBUTING.md).

## Trademarks

This project may contain trademarks. Follow [Microsoft's Trademark Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general) for proper use.
