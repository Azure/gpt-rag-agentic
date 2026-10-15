> [!WARNING]
> **This repository is retired and no longer actively supported.**
> As of **October 7, 2026**, `gpt-rag-agentic` is no longer maintained. It will not receive new features, bug fixes, security updates, or responses to issues and pull requests.
> The code remains available for reference only. If you are still using it, please plan to migrate or fork it at your own discretion.
> For the current, actively maintained solution, see [Azure/agent-landing-zone](https://github.com/Azure/agent-landing-zone).

# Agentic orchestrator

This repository contains an Azure Functions application that coordinates AutoGen
AgentChat agents using `SelectorGroupChat`. It includes retrieval-augmented
generation (RAG), multimodal retrieval, natural language to SQL (NL2SQL), and
Microsoft Fabric strategy implementations.

## Integration status

This is not the default Agent Landing Zone orchestrator. The
[Agent Landing Zone v4.3.0 manifest](https://github.com/Azure/agent-landing-zone/blob/v4.3.0/manifest.json)
pins `agent-app-ui` v3.3.0, `agent-app-orchestrator` v5.2.1, and
`agent-app-ingestion` v3.1.1. It does not include `agent-app-agentic`.
Do not treat this repository as a validated replacement for that combination.
The retirement notice above is the support declaration shipped in this repository.

For the maintained platform, see the
[Agent Landing Zone section of the AI Landing Zones documentation](https://azure.github.io/AI-Landing-Zones/agent-landing-zone/).
Those pages are not deployment instructions for this separate runtime.

## Repository guides

- [Local setup, configuration, API, and deployment limitations](docs/LOCAL_DEPLOYMENT.md)
- [Evaluation input generation and limitations](docs/EVALUATION.md)
- [Performance measurement scope](docs/LOADTEST.md)
- [NL2SQL and Fabric implementation details and limitations](docs/NL2SQL.md)

`AUTOGEN_ORCHESTRATION_STRATEGY` selects `classic_rag` (the code default),
`multimodal_rag`, `nl2sql`, `nl2sql_fewshot`, or `chat_with_fabric`.
The environment templates select different strategies, so check the value used
by your process. Fabric has known integration gaps described in its guide.

Strategy selection is implemented in
[`AgentStrategyFactory`](orchestration/agent_strategy_factory.py) and the
[`Strategy` enum](orchestration/constants.py). Custom strategies must implement
the asynchronous `create_agents` interface used by the
[orchestrators](orchestration/orchestrator.py), return the expected agent
configuration, and be registered in both places. An `execute` method alone does
not implement that interface.

Legacy names such as `gpt-rag-agentic` in the retirement notice and `azure-gpt-rag`
in deployment metadata are historical identifiers. They do not establish
compatibility with the current platform.

## Contributing

For contribution guidelines, refer to [CONTRIBUTING.md](https://github.com/Azure/GPT-RAG/blob/main/CONTRIBUTING.md).

## Trademarks

This project may contain trademarks. Follow
[Microsoft's Trademark Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general)
for proper use.
