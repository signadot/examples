# Signadot Examples

Runnable examples for [Signadot](https://www.signadot.com/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root),
which gives every pull request, developer and coding agent an isolated sandbox inside a shared
Kubernetes cluster. A sandbox runs only the services you changed. Requests that carry its routing
key reach those services, and everything else comes from the shared baseline, so you test against
real dependencies without copying the whole environment.

Most examples have a step-by-step tutorial in the Signadot docs that explains how it works and walks
through every command.

## Before you start

1. [Create a free Signadot account](https://www.signadot.com/signup/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root). No credit card needed.
2. [Install the Signadot Operator](https://www.signadot.com/docs/installation/signadot-operator?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root)
   in a Kubernetes cluster. Minikube or kind works for most examples.
3. [Install the Signadot CLI](https://www.signadot.com/docs/getting-started/installation/signadot-cli?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root)
   and run `signadot auth login`.

New to sandboxes? [Create Preview Environments](https://www.signadot.com/docs/tutorials/quickstart/first-sandbox?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root)
is the shortest path to a first sandbox.

## AI coding agents

| Example | What it shows | Tutorial |
| --- | --- | --- |
| [argocd-tutorial](argocd-tutorial) | An Argo CD ApplicationSet giving every agent pull request a sandbox and an e2e check, which the agent reads through the Argo CD MCP server | [Test Coding Agent Pull Requests with Argo CD](https://www.signadot.com/docs/tutorials/argocd-coding-agent-pull-requests?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [coderabbit-tutorial](coderabbit-tutorial) | Playwright tests in a sandbox on every pull request, with CodeRabbit explaining failures | [Diagnose Failing Tests with CodeRabbit](https://www.signadot.com/docs/tutorials/coderabbit-signadot-failing-tests?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [devin-tutorial](devin-tutorial) | Devin validating its change to one microservice against the rest of the system | [Test Devin's Changes End to End](https://www.signadot.com/docs/tutorials/devin-signadot-sandboxes?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [jira-coding-agent-tutorial](jira-coding-agent-tutorial) | From a Jira ticket to a pull request tested in a sandbox, with Bitbucket Pipelines | [From Jira Ticket to Tested Pull Request](https://www.signadot.com/docs/tutorials/jira-coding-agent-signadot-sandboxes?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [modal-sandboxes-tutorial](modal-sandboxes-tutorial) | A background coding agent in a Modal sandbox testing against Kubernetes services | [Modal Sandboxes: E2E Testing for Coding Agents](https://www.signadot.com/docs/tutorials/modal-sandboxes-signadot?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [dolt-tutorial](dolt-tutorial) | A closed-loop agent workflow with the Signadot MCP server and a Dolt database | In the README |
| [closed-loop-comparison](closed-loop-comparison) | A harness that compares Claude Code with and without Signadot agent skills | In the README |

## Pull request testing

| Example | What it shows | Tutorial |
| --- | --- | --- |
| [apollographql-tutorial](apollographql-tutorial) | A GraphQL schema change per pull request with Apollo graph variants | [Testing Apollo Federation Schema Changes](https://www.signadot.com/docs/tutorials/apollo-graphql-schema-testing?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [wundergraph-tutorial](wundergraph-tutorial) | A GraphQL schema change per sandbox with WunderGraph Cosmo feature flags | [Testing WunderGraph Federated GraphQL Schemas](https://www.signadot.com/docs/tutorials/wundergraph-schema-testing?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |

Playwright, Cypress and k6 tutorials run against [HotROD](https://github.com/signadot/hotrod)
directly; see [Pull Request Testing](https://www.signadot.com/docs/tutorials/pull-request-testing?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root).

## Preview environments

| Example | What it shows | Tutorial |
| --- | --- | --- |
| [vercel-preview-signadot-sandoxes-cicd-connection](vercel-preview-signadot-sandoxes-cicd-connection) | A Vercel frontend preview wired to a backend sandbox from the same pull request | [Full-Stack Vercel Preview Environments](https://www.signadot.com/docs/tutorials/vercel-preview-environments?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [collaborative-pre-merge-testing-for-multi-PR-features](collaborative-pre-merge-testing-for-multi-PR-features) | One preview for a feature that spans several pull requests and services | [Testing Multi-PR Features Before Merge](https://www.signadot.com/docs/tutorials/multi-pr-feature-testing?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [hotrod-ios-app](hotrod-ios-app) | An iOS app sending a sandbox's routing key to preview backend changes | [Preview Backend Changes in a Mobile App](https://www.signadot.com/docs/tutorials/mobile-app-previews?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [argocd-tutorial](argocd-tutorial) | An Argo CD ApplicationSet whose hooks create a sandbox for every pull request, run its Playwright suite and report a commit status | [Test Coding Agent Pull Requests with Argo CD](https://www.signadot.com/docs/tutorials/argocd-coding-agent-pull-requests?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |

## Messaging and workflows

Each consumer version reads every message and processes only the ones whose routing key is meant
for it, so sandboxes share one broker.

| Example | What it shows | Tutorial |
| --- | --- | --- |
| [selective-consumption-with-kafka](selective-consumption-with-kafka) | Kafka, with a consumer group per sandbox | [Testing Kafka Microservices](https://www.signadot.com/docs/tutorials/testing-kafka-microservices?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [rabbitmq-signadot-demo](rabbitmq-signadot-demo) | RabbitMQ, with a queue per consumer version on one exchange | [Testing RabbitMQ Microservices](https://www.signadot.com/docs/tutorials/testing-rabbitmq-microservices?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [SQS-Based-Microservices-with-Signadot-main](SQS-Based-Microservices-with-Signadot-main) | Amazon SQS, with a shared queue and SNS fan-out | [Testing Amazon SQS Microservices](https://www.signadot.com/docs/tutorials/testing-sqs-microservices?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [selective-consumption-with-google-pub-sub](selective-consumption-with-google-pub-sub) | Google Pub/Sub, with a subscription per sandbox | [Test Google Pub/Sub Flows End to End](https://www.signadot.com/docs/tutorials/testing-google-pub-sub-flows?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [selective-consumption-with-redis-streams](selective-consumption-with-redis-streams) | Redis Streams, with a consumer group per sandbox | [Test Redis Streams Consumers](https://www.signadot.com/docs/tutorials/testing-redis-streams?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [temporal-tutorial](temporal-tutorial) | Temporal workers in Go, Java and TypeScript sharing one task queue | [Test Temporal Workers](https://www.signadot.com/docs/tutorials/testing-temporal-workers?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [dapr-tutorial](dapr-tutorial) | Dapr service invocation and pub/sub, keeping Dapr's mTLS | [Testing Dapr Services](https://www.signadot.com/docs/tutorials/testing-dapr-services?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |

## Databases

| Example | What it shows | Tutorial |
| --- | --- | --- |
| [neon-branching-tutorial](neon-branching-tutorial) | A Neon database branch for every sandbox, created by a resource plugin | [Neon Database Branching](https://www.signadot.com/docs/tutorials/neon-database-branching?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [xata-branching-tutorial](xata-branching-tutorial) | A Xata database branch for every sandbox, created by a resource plugin | [Xata Database Branching](https://www.signadot.com/docs/tutorials/xata-database-branching?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |

Testing a schema change with a temporary MariaDB per sandbox uses
[signadot/plugins](https://github.com/signadot/plugins); see
[Testing Database Schema Changes](https://www.signadot.com/docs/tutorials/testing-database-schema-changes?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root).

## Security testing

| Example | What it shows | Tutorial |
| --- | --- | --- |
| [zap-security-tutorial](zap-security-tutorial) | A ZAP DAST scan against one change before merge | [Run ZAP DAST Scans on Every Change](https://www.signadot.com/docs/tutorials/zap-security-testing?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [falco-security-tutorial](falco-security-tutorial) | Falco runtime alerts scoped to a sandbox | [Catch Risky Runtime Behavior with Falco](https://www.signadot.com/docs/tutorials/falco-runtime-security?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |

## Reference

| Example | What it shows | Docs |
| --- | --- | --- |
| [cli](cli) | Sandbox, route group, job runner group and job specs to copy | [CLI reference](https://www.signadot.com/docs/reference/cli/overview?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [instrumentation](instrumentation) | OpenTelemetry context propagation inside an app | [Context propagation](https://www.signadot.com/docs/guides/set-up-context-propagation?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [prometheus](prometheus) | Prometheus Operator config to monitor the Signadot Operator | [Monitoring](https://www.signadot.com/docs/guides/admin/monitoring?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root) |
| [sdk](sdk) | Tests for the Signadot SDKs in Java, Node.js and Python | In the README |
| [experimental/custom-routing-with-envoy](experimental/custom-routing-with-envoy) | Custom routing with an Envoy proxy | In the README |

All tutorials, including ones that need no code from this repository, are at
[signadot.com/docs/tutorials](https://www.signadot.com/docs/tutorials?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=root).

## Get help

- Questions: ask in the [Signadot community Slack](https://join.slack.com/t/signadotcommunity/shared_invite/zt-1estxm8pv-qfiaNfiFFCaW~eUlXsVoEQ).
- Problems with an example: file an issue in the [community issue tracker](https://github.com/signadot/community/issues).
