# Testing Amazon SQS Microservices with Signadot Sandboxes

A producer and a consumer share one Amazon SQS queue, and Signadot sandboxes run changed versions of
them next to the stable ones. Each message carries a routing key in its `baggage` attribute. A
consumer that receives a message meant for another version releases it with
`ChangeMessageVisibility` (timeout 0), so the right consumer picks it up. The demo also publishes
through SNS fan-out, from a forked producer.

> **Step-by-step tutorial:** [Testing Amazon SQS Microservices in Kubernetes](https://www.signadot.com/docs/tutorials/testing-sqs-microservices?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=sqs)
> explains the receive loop, how a consumer learns which routing keys are its own, and when to choose
> a shared queue, SNS fan-out or a queue per sandbox.

![Project architecture](./apps/frontend/public/img/project-architecture.jpg)

## What's in this directory

| Path | What it does |
| --- | --- |
| `apps/frontend`, `apps/producer`, `apps/consumer` | The three services. All run from one image. |
| `modules/pull_router/router_api.py` | Asks the Signadot Routes API which routing keys belong to this consumer, and decides whether to process or release each message. |
| `k8s/` | The Secret, ConfigMap, Redis and the three Deployments, in the `aws-sqs-app` namespace. |
| `sandbox/sqs_sandbox.yaml` | Forks the consumer. |
| `sandbox/sns_sandbox.yaml` | Forks the producer and sets `SNS_FANOUT_PUBLISH`, so the fork publishes to SNS. |
| `sandbox/sns-sqs-router-grp.yaml` | Route group that joins both sandboxes under one routing key. |

## Prerequisites

- A [Signadot account](https://www.signadot.com/signup/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=sqs)
  and a Kubernetes cluster with the
  [Signadot Operator](https://www.signadot.com/docs/installation/signadot-operator) v0.15.0 or later.
  The demo targets Minikube (`minikube start --driver=docker`).
- The [Signadot CLI](https://www.signadot.com/docs/getting-started/installation/signadot-cli),
  logged in with `signadot auth login`.
- `kubectl`, Docker, `git`, `jq` and the AWS CLI.
- An AWS IAM user with an access key. The quickest setup attaches `AmazonSQSFullAccess` and
  `AmazonSNSFullAccess`; the tutorial lists the narrower set of actions the demo calls.

## 1. Clone and add AWS credentials

```bash
git clone https://github.com/signadot/examples.git
cd examples/SQS-Based-Microservices-with-Signadot-main
echo -n 'YOUR_AWS_ACCESS_KEY_ID' | base64
echo -n 'YOUR_AWS_SECRET_ACCESS_KEY' | base64
```

Put the two base64 values in `k8s/secrets.yaml`, and don't commit the edited file. The region,
queue and topic names are in `k8s/configmap.yaml`: `us-east-1`, `sqs-signadot` and `sns-signadot`.

## 2. Build the image

The frontend, producer and consumer all run from `sqs-signadot:latest`. On Minikube, build it inside
Minikube's Docker daemon so the cluster can use it without a registry:

```bash
eval $(minikube docker-env)
docker build -t sqs-signadot:latest .
```

On another cluster, push the image to a registry it can pull from, and set `image:` in
`k8s/frontend.yaml`, `k8s/producer.yaml` and `k8s/consumer.yaml` to match.

## 3. Deploy and send a baseline message

```bash
kubectl create namespace aws-sqs-app
kubectl apply -f k8s/
kubectl -n aws-sqs-app wait --for=condition=available deployment --all --timeout=5m
kubectl -n aws-sqs-app port-forward service/frontend-service 8080:8080
```

The producer and consumer create the queue and topic on startup if they don't exist. Open
http://localhost:8080 and publish a message: with no sandboxes, the baseline consumer processes it.

## 4. Fork the consumer and send a message with its routing key

```bash
export CLUSTER=<your-cluster>
signadot sandbox apply -f sandbox/sqs_sandbox.yaml --set cluster=$CLUSTER

SBX_KEY=$(signadot sandbox get sqs-counsumer-sandbox -o json | jq -r .routingKey)
curl -s -X POST http://localhost:8080/api/produce \
  -H 'Content-Type: application/json' \
  -H "baggage: sd-routing-key=$SBX_KEY" \
  -d '{"id": "cli-1", "body": "for the sandbox"}'
```

The sandboxed consumer processes the message. If the baseline consumer receives it first, it logs
`Skipping message with routing_key: '<key>'. Releasing back to queue.` Instead of `curl`, you can pick
the sandbox in the
[Signadot Chrome extension](https://chromewebstore.google.com/detail/signadot/aigejiccjejdeiikegdjlofgcjhhnkim)
and publish from the frontend.

## 5. Publish through SNS, then test both changes together

```bash
signadot sandbox apply -f sandbox/sns_sandbox.yaml --set cluster=$CLUSTER
signadot routegroup apply -f sandbox/sns-sqs-router-grp.yaml --set cluster=$CLUSTER
```

With `sns-sqs-fanout-sandbox` selected, the forked producer publishes to the topic and the baseline
consumer processes the message, because no consumer sandbox claims that key. With the
`sns-sqs-router-grp` route group selected, the forked producer publishes and the forked consumer
processes it.

![SNS fan-out and SQS architecture](./apps/frontend/public/img/architecture.jpg)

## Clean up

```bash
signadot routegroup delete sns-sqs-router-grp
signadot sandbox delete sns-sqs-fanout-sandbox
signadot sandbox delete sqs-counsumer-sandbox
kubectl delete namespace aws-sqs-app
```

The queue and topic outlive the namespace; the tutorial has the AWS CLI commands to delete them.

## Next steps

- [Testing Amazon SQS Microservices in Kubernetes](https://www.signadot.com/docs/tutorials/testing-sqs-microservices?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=sqs): the full tutorial for this example.
- [Messaging and workflow tutorials](https://www.signadot.com/docs/tutorials/messaging-and-workflows?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=sqs): the same pattern for Kafka, RabbitMQ, Google Pub/Sub, Redis Streams, Temporal and Dapr.
- New to Signadot? [Create a free account](https://www.signadot.com/signup/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=sqs) (no credit card), then try it on your own services.
- Questions? Ask in the [Signadot community Slack](https://join.slack.com/t/signadotcommunity/shared_invite/zt-1estxm8pv-qfiaNfiFFCaW~eUlXsVoEQ).
