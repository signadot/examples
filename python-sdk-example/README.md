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
export SIGNADOT_API_KEY=...
python3 tests/integration/create_sandbox_test.py
ROUTE_IMAGE=signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd python3 tests/integration/usecase1_test.py
ROUTE_IMAGE=signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3 FRONTEND_IMAGE=signadot/hotrod-frontend:5069b62ddc2625244c8504c3bca6602650494879 python3 tests/integration/usecase2_test.py
python3 tests/integration/resources_test.py
```
