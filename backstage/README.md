# Sample Backstage App

To start the app, run:

```sh
yarn install
yarn start
```

## Kubernetes Deployment

### Minikube

Build the sample-app image:

```sh
eval $(minikube docker-env)
yarn build-image --tag signadot/backstage-sample-app:latest
```

Create the `backstage` namespace, and a secret for the postgres credentials:

```sh
kubectl create namespace backstage


kubectl create secret generic postgres-credentials -n backstage \
  --from-literal=POSTGRES_USER='backstage' \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -base64 12)"
```

Apply the `minikube` overlay:

```sh
kubectl apply -k ./k8s/overlays/minikube/
```

Make sure all pods are running:

```sh
kubectl get deploy,po,svc -n backstage
```

Connect to the cluster:

```sh
signadot local connect
```

Access the backstage sample app at: http://sample-app.backstage/