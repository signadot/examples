# Signadot Java SDK Example

This example application uses Signadot's Java SDK to create a sandbox and test the preview URL in the context of Integration Testing with sandboxes.

# Setup

1. Ensure you have [Docker](https://www.docker.com/), [minikube](https://minikube.sigs.k8s.io/docs/), [helm](https://helm.sh/), and [kubectl](https://kubernetes.io/docs/tasks/tools/) installed.
2. Run [`minikube start`](https://minikube.sigs.k8s.io/docs/start/) to create a Kubernetes environment locally.
3. Create the `hotrod` namespace by running `kubectl create ns hotrod`.
4. Create our all in one demo application in your local Kubernetes cluster by running `kubectl -n hotrod apply -f https://raw.githubusercontent.com/signadot/hotrod/main/k8s/all-in-one/demo.yaml`.
5. Create a cluster in the [Signadot Dashboard](https://app.signadot.com/) and make sure to copy the token generated for it for the next step.
6. Run the following commands:
    1. `helm repo add signadot https://charts.signadot.com`
    2. `helm install signadot-sandboxes signadot/sandboxes`
    3. `kubectl -n signadot create secret generic cluster-agent --from-literal=token=...` where the `...` is replaced with the token you copied when creating the cluster in the Signadot Dashboard.

# Testing

The test creates a sandbox in the setup phase, runs tests against it and deletes the sandbox upon completion of the tests. Heres' the command to run it:

```
SIGNADOT_API_KEY=<SIGNADOT_API_KEY_HERE> gradle clean test
```
