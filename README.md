# Signadot Examples

This repository contains examples for Signadot users.

# Setup Instructions for Running Examples

1. Ensure you have [Docker](https://www.docker.com/), [minikube](https://minikube.sigs.k8s.io/docs/), [helm](https://helm.sh/), and [kubectl](kubectl apply -f https://raw.githubusercontent.com/signadot/hotrod/main/k8s/all-in-one/demo.yaml) installed.
2. Run [`minikube start`](https://minikube.sigs.k8s.io/docs/start/) to create a Kubernetes environment locally.
3. Create our all in one demo application in your local Kubernetes cluster by running `kubectl -n hotrod apply -f https://raw.githubusercontent.com/signadot/hotrod/main/k8s/all-in-one/demo.yaml`.
4. Create a cluster in the [Signadot Dashboard](https://app.signadot.com/) and make sure to copy the token generated for it for the next step.
5. Run the following commands:
    1. `helm repo add signadot https://charts.signadot.com`
    2. `helm install signadot-workspaces signadot/workspaces`
    3. `kubectl -n signadot create secret generic cluster-agent --from-literal=token=...` where the `...` is replaced with the token you copied when creating the cluster in the Signadot Dashboard.
6. Check the README's in the java/node SDK examples for instructions on running integration tests against your new cluster.