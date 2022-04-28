# Signadot Node SDK Example

This sample application uses Signadot's Node SDK to create a sandbox and test the preview URL in the context of Integration Testing with sandboxes.

# Setup

1. Ensure you have [Docker](https://www.docker.com/), [minikube](https://minikube.sigs.k8s.io/docs/), [helm](https://helm.sh/), and [kubectl](https://kubernetes.io/docs/tasks/tools/) installed.
2. Run [`minikube start`](https://minikube.sigs.k8s.io/docs/start/) to create a Kubernetes environment locally.
3. Create the `hotrod` namespace by running `kubectl create ns hotrod`.
4. Create our all in one demo application in your local Kubernetes cluster by running `kubectl -n hotrod apply -f https://raw.githubusercontent.com/signadot/hotrod/main/k8s/all-in-one/demo.yaml`.
5. Create a cluster in the [Signadot Dashboard](https://app.signadot.com/) and make sure to copy the token generated for it for the next step.
6. Install signadot operator on cluster following [these instructions](https://docs.signadot.com/docs/installation#signadot-operator)

# Installation

## npm

```shell
npm install @signadot/signadot-sdk --save
```

## yarn

```shell
yarn add @signadot/signadot-sdk
```

# Running the example

Install the npm dependencies.
```shell
npm install
```

Run the tests with the below command. Supply SIGNADOT_API_KEY from Signadot dashboard.
```shell
SIGNADOT_ORG=<your-signadot-org> SIGNADOT_API_KEY=<supply-signadot-api-key-here> npm run test
```
