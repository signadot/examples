# Signadot Python SDK Example

## Introduction
This sample application uses Signadot's Node SDK to create a sandbox and test the preview URL in the context of Integration Testing with sandboxes.

## Setup

1. Ensure you have [Docker](https://www.docker.com/), [minikube](https://minikube.sigs.k8s.io/docs/), [helm](https://helm.sh/), and [kubectl](https://kubernetes.io/docs/tasks/tools/) installed.
2. Run [`minikube start`](https://minikube.sigs.k8s.io/docs/start/) to create a Kubernetes environment locally.
3. Create the `hotrod` namespace by running `kubectl create ns hotrod`.
4. Create our all in one demo application in your local Kubernetes cluster by running `kubectl -n hotrod apply -f https://raw.githubusercontent.com/signadot/hotrod/main/k8s/all-in-one/demo.yaml`.
5. Create a cluster in the [Signadot Dashboard](https://app.signadot.com/) and make sure to copy the token generated for it for the next step.
6. Install signadot operator on cluster following [these instructions](https://docs.signadot.com/docs/installation#signadot-operator)

## Installation
```shell
pip3 install -r test-requirements.txt
```

## Run test(s)
Plug in Signadot API Key from Signadot dashboard and run the command below:
```shell
SIGNADOT_API_KEY=<signadot-api-key> python3 tests/integration/route_test.py
```
