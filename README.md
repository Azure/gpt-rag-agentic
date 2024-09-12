# Enterprise RAG Agentic Orchestrator

This Orchestrator is part of the **Enterprise RAG (GPT-RAG)** Solution Accelerator.

To learn more about the Enterprise RAG, please go to [https://aka.ms/gpt-rag](https://aka.ms/gpt-rag).

### Cloud Deployment

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

> Note: when running the ```azd env refresh```, use the same environment name, subscription, and region used in the initial provisioning of the infrastructure.

### Running Locally with VS Code  
   
[How can I test the solution locally in VS Code?](docs/LOCAL_DEPLOYMENT.md)

Got it! I’ve noted that the prompt files are in the `prompt` folder. Here's an updated version of the README section, taking this into account:

### Customizing the Orchestrator

The **Enterprise RAG Agentic Orchestrator** is designed to be flexible and extensible, enabling you to customize its behavior by modifying or extending the agent creation strategy. The orchestrator uses a strategy pattern, which allows you to define how agents are created, interact, and function. By default, it uses the `DefaultAgentCreationStrategy`, which is a simple RAG implementation, but you can implement your own strategy to fit your needs.

#### How to Customize the Orchestrator

1. **Change the Agent Creation Strategy**:
   The `AgentCreationStrategyFactory` is responsible for selecting the strategy used to create agents. You can customize the orchestrator by creating your own agent creation strategy and registering it with the factory. To do this, subclass the `BaseAgentCreationStrategy` and implement the `create_agents` method. This method defines how agents are set up. Once your custom strategy is defined, pass its name as the `strategy_type` parameter when initializing the orchestrator.

   Example:
   ```python
   orchestrator = Orchestrator(conversation_id, client_principal, strategy_type='custom')
   ```

2. **Add or Modify Agents**:
   The default strategy creates two agents (a `UserProxyAgent` and an `AssistantAgent`). To add new agents or modify existing ones, you can customize the `create_agents` method in your strategy. Each agent uses a prompt file stored in the `prompts` folder, which you can modify to change the agent’s behavior. For example, you can add agents with different roles or knowledge domains.

3. **Customize Prompts**:
   The behavior of each agent is driven by prompts that are stored in the `prompts` folder. You can modify these prompt files to adjust how agents respond to user queries. To add new agents with their own unique behavior, create corresponding prompt files and ensure they are loaded within your custom strategy.

4. **Register Custom Functions**:
   If you need agents to perform additional tasks, such as integrating with external systems or performing complex data retrieval, you can register custom functions. In the default strategy, a function like `vector_index_retrieve` is registered to allow the assistant to search a knowledge base. You can add more functions in a similar way by modifying the strategy or registering new tools directly with your agents.

By customizing these components, you can tailor the orchestrator to suit specific workflows or business logic, adding more agents or modifying existing ones to handle different scenarios.

### Evaluating

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
