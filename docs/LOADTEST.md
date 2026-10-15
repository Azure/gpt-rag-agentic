# Performance measurement scope

This repository does not include a load-test harness, a workload definition, or
published performance targets. The
[evaluation input generator](EVALUATION.md) sends questions sequentially. It is
not a concurrent load test.

For a performance study of this runtime, define an external test plan for the
actual [API routes](LOCAL_DEPLOYMENT.md#api-contract):

- Measure end-to-end latency separately from time to first streamed text.
- Record the strategy, model deployment, dataset, concurrency, and service
  limits used in the test.
- Track failed requests and error text as well as latency. A completed response
  or evaluation output file is not proof of a successful answer.
- Use approved test data and an isolated test environment with cost and load
  limits.

The request-response orchestrator logs its elapsed answer time. That timer is
not a measurement of frontend or network latency. `host.json` contains
Application Insights sampling settings, but this repository does not provide a
load-test dashboard or a benchmark acceptance threshold.

The old link to a GPT-RAG load-test page did not establish compatibility with
this API. For maintained platform guidance, use the
[Agent Landing Zone documentation](https://azure.github.io/AI-Landing-Zones/agent-landing-zone/).
That platform does not pin this runtime in its v4.3.0 manifest. See
[integration status](../README.md#integration-status).
