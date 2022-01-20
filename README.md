# Signadot Examples

This repository contains examples for Signadot users.

# Setup Instructions for Running Examples

1. Ensure you have [Docker](https://www.docker.com/), [minikube](https://minikube.sigs.k8s.io/docs/), [helm](https://helm.sh/), and [kubectl](kubectl apply -f https://raw.githubusercontent.com/signadot/hotrod/main/k8s/all-in-one/demo.yaml) installed.
2. Run [`minikube start`](https://minikube.sigs.k8s.io/docs/start/) to create a Kubernetes environment locally.
3. Create our all in one demo application in your local Kubernetes cluster by running `kubectl apply -f https://raw.githubusercontent.com/signadot/hotrod/main/k8s/all-in-one/demo.yaml`.
4. Create a cluster in the [Signadot Dashboard](https://app.signadot.com/) and make sure to copy the token generated for it for the next step.
5. Run the following commands:
    1. `helm repo add signadot https://charts.signadot.com`
    2. `helm install signadot-workspaces signadot/workspaces`
    3. `kubectl -n signadot create secret generic cluster-agent --from-literal=token=...` where the `...` is replaced with the token you copied when creating the cluster in the Signadot Dashboard.
6. Create a new workspace in the Signadot Dashboard in the newly-created cluster. Select "hotrod" as the namespace, and choose "route" in the "Select Deployments to Fork" section.
7. Click on the new workspace in the table to show the details page for it.
8. Click on the URL in the "Forked Deployment" column in the "Forked Deployments" table. If you click on any of the destination buttons, you'll notice it takes a long time to calculate a route. Let's fix that.
9. Go back to the workspace details page (clicking on the URL should have opened a new tab, so you can close that to go back to the dashboard). Click on the first row in the "Forked Deployments" table.
10. Put `signadot/hotrod-route:bugfix-slow-cards` into the "Replacement Image" text input and click Apply.
11. Click the back button in your browser, and wait for the status of the workspace to show "Ready". Once it does, click the URL in the "Forked Deployment" column in the "Forked Deployments" table again. Then click a destination button, and notice that it calculates a route much faster.
12. Congratulations, you've successfully used a Signadot workspace to quickly try a bug fix and see it in action!