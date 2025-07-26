# Tutorial: Collaborative Pre-Merge Testing for Multi-PR Features

When new features span multiple microservices, testing becomes a major challenge. Coordinated changes across separate pull requests (PRs) must be validated together before merging. This tutorial provides a hands-on guide to building an automated system using Signadot that creates unified, ephemeral preview environments for all PRs related to a single feature epic.
This technical guide is a comprehensive, step-by-step resource for:

- Setting up a collaborative pre-merge testing environment with Signadot and HotROD
- Troubleshooting real-world issues
- Automating ephemeral preview environments with GitHub Actions
- Implementing and testing multi-service features such as "Dynamic Surcharges"

> **Note:** The configuration files and code referenced in this guide can be found in the following repository:  
> https://github.com/signadot/examples/tree/main/collaborative-pre-merge-testing-for-multi-PR-features

---

## 1. Prerequisites and Baseline Environment Setup

Before you begin, you need a functioning Kubernetes cluster with the HotROD demo application deployed and connected to Signadot.

### 1.1. Install Signadot and Set Up Your Cluster

- **Create a Signadot account:** [Signadot Official Docs](https://www.signadot.com/docs/overview)
- **Connect your Kubernetes cluster:** Follow the onboarding instructions in the Signadot dashboard to connect your cluster. This typically involves downloading a YAML file and applying it:

  ```bash
  kubectl apply -f <signadot-operator-yaml>
  ```

- **Install the Signadot CLI:**
  
  ```bash
  curl -sSLf https://raw.githubusercontent.com/signadot/cli/main/scripts/install.sh | sh
  signadot auth login
  signadot cluster list
  ```

  Ensure your cluster appears as "ready" in the Signadot dashboard.

### 1.2. Deploy the HotROD Demo Application

HotROD is a demo ride-sharing app with four main services: frontend, route, driver, and location.

```bash
cd hotrod
# Or clone directly from the official repo
git clone https://github.com/signadot/hotrod.git
# Create a namespace
kubectl create namespace hotrod
# Deploy using the Istio overlay for routing capabilities
kubectl -n hotrod apply -k k8s/overlays/prod/istio
```

#### Troubleshooting: Istio and Resource Issues

- If you see errors about `VirtualService` not found, **Istio is not installed**. Install Istio:

  ```bash
  curl -L https://istio.io/downloadIstio | sh -
  cd istio-*
  export PATH=$PWD/bin:$PATH
  istioctl install --set profile=demo -y
  ```

  Then re-apply the HotROD deployment.
- If pods are stuck in `ContainerCreating` or `Pending`, check for resource issues. Increase Minikube resources if needed:

  ```bash
  minikube delete
  minikube start --cpus=3 --memory=4096
  ```

- If you see `ImagePullBackOff`, ensure the image exists or use the baseline image.

### 1.3. Verify the Baseline

Confirm the application is running correctly by forwarding a local port to the frontend service:

```bash
kubectl -n hotrod port-forward svc/frontend 8080:8080
```

Open [http://localhost:8080](http://localhost:8080) in your browser. Request a ride by selecting a pickup and dropoff location. A successful request will display a car on a map, confirming the baseline is working.

#### Additional Troubleshooting and Fixes

- If the Signadot dashboard shows your cluster as "not connected" after authentication, ensure you have applied the correct cluster token secret. If you deleted and recreated the cluster in the dashboard, update the secret:

  ```bash
  kubectl -n signadot delete secret cluster-agent
  kubectl -n signadot create secret generic cluster-agent --from-literal=token='<NEW_TOKEN_HERE>'
  # Restart the operator if needed
  kubectl rollout restart deployment signadot-operator -n <namespace>
  ```

- If sandboxes are stuck as "Not Ready: DevMesh Sidecar absent on baseline ...", inject the DevMesh sidecar:

  ```bash
  kubectl -n hotrod patch deployment route -p '{"spec":{"template":{"metadata":{"annotations":{"sidecar.signadot.com/inject":"true"}}}}}'
  kubectl -n hotrod patch deployment frontend -p '{"spec":{"template":{"metadata":{"annotations":{"sidecar.signadot.com/inject":"true"}}}}}'
  ```

  Wait for the new pods to be running before proceeding.

---

## 2. The Scenario: Implementing "Dynamic Surcharges"

When new features span multiple microservices, testing becomes a major challenge. Coordinated changes across separate pull requests (PRs) must be validated together before merging. This scenario demonstrates a real-world example: implementing a "Dynamic Surcharges" feature in the HotROD demo app, which requires changes to both the backend (`route` service) and frontend services. All work for this feature is tracked under the identifier `EPIC-42`.

### 2.1 Backend Change: route Service

Add a new gRPC endpoint to the route service to calculate the surcharge.

**Edit `pkg/route/route.proto`:**

```proto
// Add these message definitions
message SurchargeRequest {
    string pickup = 1;
    string dropoff = 2;
}

message SurchargeResponse {
    double amount = 1;
}

service Route {
  rpc GetRoute(RouteRequest) returns (RouteResponse);
  // Add this new RPC
  rpc GetSurcharge(SurchargeRequest) returns (SurchargeResponse);
}
```

**Implement the server logic in `services/route/server.go`:**

```go
// Add this method to the server struct
func (s *server) GetSurcharge(ctx context.Context, req *route.SurchargeRequest) (*route.SurchargeResponse, error) {
    s.logger.For(ctx).Info("Calculating surcharge", zap.String("pickup", req.Pickup), zap.String("dropoff", req.Dropoff))
    // In a real application, you would have logic to determine the surcharge.
    // For this tutorial, we'll return a fixed amount.
    return &route.SurchargeResponse{
        Amount: 1.25,
    }, nil
}
```

### 2.2 Frontend Change: frontend Service

Modify the frontend service to call the new `GetSurcharge` endpoint and display the result to the user.

**Update the frontend server in `services/frontend/server.go`:**

```go
// In services/frontend/server.go, inside dispatchHandler

// Create a SurchargeRequest
surchargeReq := &route.SurchargeRequest{
    Pickup:  r.FormValue("pickup"),
    Dropoff: r.FormValue("dropoff"),
}

// Call the new GetSurcharge endpoint
surchargeRes, err := s.routeClient.GetSurcharge(ctx, surchargeReq)
if err!= nil {
    s.logger.For(ctx).Error("Failed to get surcharge", zap.Error(err))
    // Decide how to handle the error; for now, we'll ignore it and proceed
}

// Existing logic to dispatch the ride...
//...

// Pass the surcharge amount to the template
templateData := map[string]interface{}{
    "locations": locations,
    "surcharge": surchargeRes.GetAmount(), // Add this line
}
s.render(r, w, "index", templateData)
```

**Update the UI template in `services/frontend/templates/index.html`:**

```html
{{if.surcharge}}
<div class="surcharge-info" style="padding: 10px; background-color: #fffbe6; border: 1px solid #ffe58f; margin-top: 15px; border-radius: 5px;">
    <strong>Dynamic Surcharge Applied:</strong> ${{printf "%.2f".surcharge}}
</div>
{{end}}

<div id="ride-info" class="p-2"></div>
```

After making these changes, you would typically build new container images for both services (e.g., `your-repo/hotrod-route:epic-42` and `your-repo/hotrod-frontend:epic-42`) and push them to a registry. For the main workflow in this guide, pre-built images or the baseline image are used, but this section is provided for teams who wish to implement and test the feature end-to-end.

---

## 3. Manual Workflow: Unified Preview with Signadot

### 3.1. Inject the DevMesh Sidecar (Required for Sandboxes)

To enable Signadot sandboxes, you must inject the DevMesh sidecar into the baseline deployments you wish to fork. This is done by adding an annotation to the deployment's pod template.

**Patch the `route` deployment:**

```bash
kubectl -n hotrod patch deployment route -p '{
  "spec": {
    "template": {
      "metadata": {
        "annotations": {
          "sidecar.signadot.com/inject": "true"
        }
      }
    }
  }
}'
```

**Patch the `frontend` deployment:**

```bash
kubectl -n hotrod patch deployment frontend -p '{
  "spec": {
    "template": {
      "metadata": {
        "annotations": {
          "sidecar.signadot.com/inject": "true"
        }
      }
    }
  }
}'
```

Wait for the new pods to be created and reach the `Running` state:

```bash
kubectl -n hotrod get pods
```

**Verify the sidecar is present:**

```bash
kubectl -n hotrod describe pod <route-pod-name>
```

Look for an extra container in the pod spec, typically named `devmesh` or similar.

---

#### 3.2. Create Sandboxes for Each Service

Create `route-surcharge-sandbox.yaml`:

```yaml
name: route-surcharge-feature
spec:
  cluster: <your-cluster-name>
  labels:
    epic: EPIC-42
  forks:
    - forkOf:
        kind: Deployment
        namespace: hotrod
        name: route
```

Create `frontend-surcharge-sandbox.yaml`:

```yaml
name: frontend-surcharge-feature
spec:
  cluster: <your-cluster-name>
  labels:
    epic: EPIC-42
  forks:
    - forkOf:
        kind: Deployment
        namespace: hotrod
        name: frontend
```

Apply the sandboxes:

```bash
signadot sandbox apply -f route-surcharge-sandbox.yaml --set cluster=<your-cluster-name>
signadot sandbox apply -f frontend-surcharge-sandbox.yaml --set cluster=<your-cluster-name>
```

**Troubleshooting:**

- If you see `Insufficient cpu` errors, increase Minikube resources (see above). The Signadot traffic manager sidecars require significant CPU.
- If you see `ImagePullBackOff` for custom images, ensure the image exists in your registry or use the baseline image.
- If you see `DevMesh Sidecar absent on baseline ...`, ensure you have injected the sidecar as described above.
- If pods are stuck in `Pending`, describe them:

  ```bash
  kubectl -n hotrod describe pod <pod-name>
  ```

  Look for resource or image pull errors.

#### 3.3. Create a RouteGroup

Create `epic-routegroup.yaml`:

```yaml
name: epic-42-preview
spec:
  cluster: <your-cluster-name>
  match:
    any:
      - label:
          key: epic
          value: EPIC-42
  endpoints:
    - name: hotrod-frontend
      target: http://frontend.hotrod.svc:8080
```

Apply it:

```bash
signadot routegroup apply -f epic-routegroup.yaml --set cluster=<your-cluster-name>
```

#### 3.4. Test the Unified Preview

- Install the [Signadot Chrome Extension](https://chrome.google.com/webstore/detail/signadot/)
- Log in and select the `epic-42-preview` RouteGroup
- Visit [http://localhost:8080](http://localhost:8080)
- Request a ride; you should see **Dynamic Surcharge Applied: $1.25** (if using custom images)

---

### 4. Troubleshooting & Real-World Notes

- Always ensure Istio is installed before applying HotROD overlays.
- If you have limited resources, you may need to use a cloud Kubernetes cluster.
- The Signadot traffic manager sidecars have high default CPU requests; these cannot be changed in the sandbox YAML.
- If you want to implement the code changes yourself (Step 2 in the original guide), you’ll need to:
  - Edit the Go and proto files
  - Build and push your own Docker images
  - Update the sandbox YAMLs to use your images
- If you delete and recreate your cluster in the Signadot dashboard, ensure you update the cluster token secret in your Kubernetes cluster and restart the operator if needed.

---

## 5. Automation: GitHub Actions Integration

### 5.1. Overview

Automate the creation and management of Signadot sandboxes and RouteGroups for every pull request and epic using GitHub Actions. This enables fully automated ephemeral preview environments for collaborative testing.

> **Professional Note:**
> The automation workflows and templates provided here are based on Signadot's official patterns and best practices. They are designed to work when correct parameters, secrets, and valid container images are supplied. However, as with any CI/CD automation, you should validate these workflows in your environment and adapt as needed for your specific use case and infrastructure.

#### 5.2. Required Templates

- **Sandbox template:** `.signadot/sandbox-template.yaml`
- **RouteGroup template:** `.signadot/routegroup-template.yaml`

**.signadot/sandbox-template.yaml**

```yaml
name: "${name}"
spec:
  cluster: "${cluster}"
  labels:
    signadot/github-pull-request: "${signadot/github-pull-request}"
    signadot/github-repo: "${signadot/github-repo}"
    epic: "${epic}"
  forks:
    - forkOf:
        kind: Deployment
        namespace: hotrod
        name: ${service}
      customizations:
        images:
          - image: ${image}
```

**.signadot/routegroup-template.yaml**

```yaml
name: "${name}"
spec:
  cluster: "${cluster}"
  match:
    any:
      - label:
          key: epic
          value: "${match_value}"
  endpoints:
    - name: hotrod-frontend
      target: http://frontend.hotrod.svc:8080
```

#### 5.3. Add Required GitHub Secrets

In your repository settings, add the following secrets:

- `SIGNADOT_API_KEY` (your Signadot API key)
- `SIGNADOT_ORG` (your Signadot organization name)
- `SIGNADOT_CLUSTER` (your Signadot cluster name)

#### 5.4. Workflow 1: Create Sandbox on PR

Create `.github/workflows/create-pr-sandbox.yml`:

```yaml
name: Create PR Sandbox
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  create-sandbox:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      # (Optional) Build and push your image
      # - name: Build and push image
      #   run: |
      #     docker build -t your-registry/hotrod:${{ github.sha }} .
      #     docker push your-registry/hotrod:${{ github.sha }}

      - name: Install Signadot CLI
        run: curl -sSLf https://raw.githubusercontent.com/signadot/cli/main/scripts/install.sh | sh

      - name: Apply Sandbox
        env:
          SIGNADOT_API_KEY: ${{ secrets.SIGNADOT_API_KEY }}
          SIGNADOT_ORG: ${{ secrets.SIGNADOT_ORG }}
        run: |
          signadot sandbox apply -f .signadot/sandbox-template.yaml \
            --set cluster=${{ secrets.SIGNADOT_CLUSTER }} \
            --set name="pr-${{ github.event.pull_request.number }}" \
            --set image="your-registry/hotrod:${{ github.sha }}" \
            --set labels."signadot/github-pull-request"="${{ github.event.pull_request.number }}" \
            --set labels."signadot/github-repo"="${{ github.repository }}"
```

#### 5.5. Workflow 2: Link Epic via PR Comment

Create `.github/workflows/link-epic-preview.yml`:

```yaml
name: Link Epic Preview
on:
  issue_comment:
    types: [created]

jobs:
  link-epic:
    if: github.event.issue.pull_request && contains(github.event.comment.body, '/epic')
    runs-on: ubuntu-latest
    steps:
      - name: Parse Epic ID from comment
        id: parse_epic
        run: |
          EPIC_ID=$(echo "${{ github.event.comment.body }}" | awk '{print $2}')
          echo "EPIC_ID=${EPIC_ID}" >> $GITHUB_ENV

      - name: Install Signadot CLI
        run: curl -sSLf https://raw.githubusercontent.com/signadot/cli/main/scripts/install.sh | sh

      - name: Update Sandbox with Epic Label
        env:
          SIGNADOT_API_KEY: ${{ secrets.SIGNADOT_API_KEY }}
          SIGNADOT_ORG: ${{ secrets.SIGNADOT_ORG }}
        run: |
          signadot sandbox apply -f .signadot/sandbox-template.yaml \
            --set cluster=${{ secrets.SIGNADOT_CLUSTER }} \
            --set name="pr-${{ github.event.issue.number }}" \
            --set image="your-registry/hotrod:${{ github.event.pull_request.head.sha }}" \
            --set labels."epic"="${{ env.EPIC_ID }}" \
            --set labels."signadot/github-pull-request"="${{ github.event.issue.number }}" \
            --set labels."signadot/github-repo"="${{ github.repository }}"

      - name: Create or Update Epic RouteGroup
        id: routegroup
        env:
          SIGNADOT_API_KEY: ${{ secrets.SIGNADOT_API_KEY }}
          SIGNADOT_ORG: ${{ secrets.SIGNADOT_ORG }}
        run: |
          signadot routegroup apply -f .signadot/routegroup-template.yaml \
            --set cluster=${{ secrets.SIGNADOT_CLUSTER }} \
            --set name="epic-${{ env.EPIC_ID }}-preview" \
            --set match_value="${{ env.EPIC_ID }}"

          RG_URL=$(signadot routegroup get epic-${{ env.EPIC_ID }}-preview -o jsonpath='{.endpoints.url}')
          echo "preview_url=${RG_URL}" >> $GITHUB_OUTPUT

      - name: Post Preview URL back to PR
        uses: peter-evans/create-or-update-comment@v4
        with:
          issue-number: ${{ github.event.issue.number }}
          body: |
            ✅ Unified preview for **${{ env.EPIC_ID }}** is ready!
            Preview URL: **${{ steps.routegroup.outputs.preview_url }}**
```

## 6. Lifecycle Management: Automated Cleanup

Ephemeral environments should be cleaned up automatically to save resources. Signadot provides two simple mechanisms for this:

**Time-To-Live (TTL):** You can define a ttl field in the specification for both Sandboxes and RouteGroups. This ensures the resource is automatically deleted after a specified duration (e.g., 2d for two days), preventing orphaned environments.

**PR-Based Deletion:** By installing the [https://www.signadot.com/docs/guides/integrate-ci/github](https://www.signadot.com/docs/guides/integrate-ci/github) and adding `signadot/github-repo` and `signadot/github-pull-request` labels to your sandboxes (as shown in the automation examples), Signadot will automatically delete the associated sandbox when the corresponding PR is closed or merged.

---
