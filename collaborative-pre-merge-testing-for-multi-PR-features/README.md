# Collaborative Pre-Merge Testing for Multi-PR Features

A feature that changes several microservices usually arrives as several pull requests, and testing
each one on its own never runs the feature end to end. This example gives each pull request a
Signadot sandbox that runs only its changed service, and joins the sandboxes with a route group, so
one preview URL runs the whole feature while every other service comes from the shared baseline.

> **Step-by-step tutorial:** [How to Test a Feature That Spans Multiple Pull Requests](https://www.signadot.com/docs/tutorials/multi-pr-feature-testing?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=multi-pr-features)
> explains how this works and walks through every step.

The feature is a "dynamic surcharge" in [HotROD](https://github.com/signadot/hotrod): the `route`
service gains a `GetSurcharge` gRPC method, and the `frontend` calls it and shows the amount.

## What's in this directory

| File | What it does |
| --- | --- |
| `route-surcharge-sandbox.yaml` | Sandbox for the route pull request. Forks `route` and labels it `epic: EPIC-42`. |
| `frontend-surcharge-sandbox.yaml` | Sandbox for the frontend pull request. Forks `frontend` with the same label. |
| `epic-routegroup.yaml` | Route group that matches every sandbox labeled `epic: EPIC-42` and exposes the frontend. |
| `.github/workflows/create-pr-sandbox.yml` | Builds an image and creates a sandbox for every pull request. Copy it into each service repository. |
| `.github/workflows/link-epic-preview.yml` | Adds a pull request to a feature preview when someone comments `/epic EPIC-42`, then replies with the preview URL. |
| `.signadot/*-template.yaml` | The same sandbox and route group as templates, for `signadot ... apply --set`. |

## Prerequisites

- A [Signadot account](https://www.signadot.com/signup/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=multi-pr-features)
  and a Kubernetes cluster with the
  [Signadot Operator](https://www.signadot.com/docs/installation/signadot-operator) installed.
- The [Signadot CLI](https://www.signadot.com/docs/getting-started/installation/signadot-cli),
  logged in with `signadot auth login`.
- `kubectl`, `git`, Docker, and a container registry the cluster can pull from.
- To build HotROD: Go, Node.js with npm, and `protoc` with the `protoc-gen-go` and
  `protoc-gen-go-grpc` plugins.

## 1. Deploy HotROD

```bash
kubectl create namespace hotrod
kubectl -n hotrod apply -k 'https://github.com/signadot/hotrod/k8s/overlays/prod/devmesh'
kubectl -n hotrod wait --for=condition=available deployment --all --timeout=5m
signadot local connect --cluster=<your-cluster>
```

Open http://frontend.hotrod.svc:8080 and request a ride. This is the baseline: no surcharge yet.

## 2. Make the two changes

```bash
git clone https://github.com/signadot/hotrod.git
cd hotrod
git checkout -b epic-42-surcharge
```

In a real team these would be two pull requests. HotROD builds every service into one image, so one
branch carries both changes here, and each sandbox runs only its own service from that image.

### The route pull request

`services/route/route.proto`:

```protobuf
service RoutesService {
  rpc FindRoute(FindRouteRequest) returns (FindRouteResponse);
  rpc GetSurcharge(SurchargeRequest) returns (SurchargeResponse);
}

message SurchargeRequest {
  string pickup = 1;
  string dropoff = 2;
}

message SurchargeResponse {
  double amount = 1;
}
```

`services/route/server.go`, a new method:

```go
func (s *Server) GetSurcharge(ctx context.Context, req *SurchargeRequest) (*SurchargeResponse, error) {
	s.logger.For(ctx).Info("Calculating surcharge", zap.String("pickup", req.Pickup), zap.String("dropoff", req.Dropoff))
	// A real service would compute this. The example returns a fixed amount.
	return &SurchargeResponse{Amount: 1.25}, nil
}
```

`services/route/client.go`, a matching client method:

```go
func (c *Client) GetSurcharge(ctx context.Context, pickup, dropoff string) (*SurchargeResponse, error) {
	c.logger.For(ctx).Info("Getting surcharge", zap.String("pickup", pickup), zap.String("dropoff", dropoff))
	ctx, cancel := context.WithTimeout(ctx, 1*time.Second)
	defer cancel()
	return c.client.GetSurcharge(ctx, &SurchargeRequest{Pickup: pickup, Dropoff: dropoff})
}
```

### The frontend pull request

`services/frontend/server.go`: give the server a route client, register a `/surcharge` handler, and
pass the request's context to the gRPC call. That context carries the routing key from the frontend
to the route service.

```go
import "github.com/signadot/hotrod/services/route"

type Server struct {
	// ... existing fields
	routeClient *route.Client
}

// In NewServer, next to the other clients:
	routeClient := route.NewClient(tracerProvider, logger, config.GetRouteAddr())
	// ... and add routeClient: routeClient to the returned &Server{...}

// In createServeMux, next to the other handlers:
	mux.Handle(path.Join(p, "/surcharge"), http.HandlerFunc(s.surcharge))

func (s *Server) surcharge(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	pickup := r.URL.Query().Get("pickup")
	dropoff := r.URL.Query().Get("dropoff")
	if pickup == "" || dropoff == "" {
		http.Error(w, "Missing pickup or dropoff parameters", http.StatusBadRequest)
		return
	}

	surchargeRes, err := s.routeClient.GetSurcharge(ctx, pickup, dropoff)
	if err != nil {
		s.logger.For(ctx).Error("Failed to get surcharge", zap.Error(err))
		http.Error(w, "Failed to get surcharge", http.StatusInternalServerError)
		return
	}
	s.writeResponse(map[string]interface{}{"surcharge": surchargeRes.Amount}, w, r)
}
```

`services/frontend/react_app/src/pages/home.tsx`: fetch the surcharge when the rider requests a ride,
and show it only when the call succeeds. Paired with the baseline route service, the call fails and
the banner stays hidden.

```tsx
const [surcharge, setSurcharge] = useState<number | null>(null);

const getSurcharge = async (pickupId: number, dropoffId: number) => {
    try {
        const response = await fetch(`/surcharge?pickup=${pickupId}&dropoff=${dropoffId}`);
        if (response.ok) {
            const data = await response.json();
            setSurcharge(data.surcharge);
        }
    } catch (error) {
        console.error('Failed to get surcharge:', error);
    }
};

// In handleRequestDrive, after reading pickupId and dropoffId from selectedLocations:
await getSurcharge(pickupId, dropoffId);

// In the JSX, above the ride details:
{surcharge !== null && (
    <Box p={3} bg="yellow.100" borderRadius="md" border="1px solid" borderColor="yellow.300">
        <Text fontWeight="bold" color="yellow.800">
            Dynamic Surcharge Applied: ${surcharge.toFixed(2)}
        </Text>
    </Box>
)}
```

## 3. Build and push the image

`make build-docker` builds the React app and tags the image `signadot/hotrod:<RELEASE_TAG>-<GOOS>-<GOARCH>`:

```bash
make generate-proto
make build-docker RELEASE_TAG=epic-42 GOOS=linux GOARCH=amd64
docker tag signadot/hotrod:epic-42-linux-amd64 <your-registry>/hotrod:epic-42
docker push <your-registry>/hotrod:epic-42
```

Use `GOARCH=arm64` if your nodes are ARM. `<your-registry>` is a placeholder: for images of your own
services, push to a private repository and give the cluster pull access, for example with an
[image pull secret](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/).

## 4. Create the sandboxes and the route group

From this directory:

```bash
export CLUSTER=<your-cluster>
export IMAGE=<your-registry>/hotrod:epic-42
signadot sandbox apply -f route-surcharge-sandbox.yaml --set cluster=$CLUSTER --set image=$IMAGE
signadot sandbox apply -f frontend-surcharge-sandbox.yaml --set cluster=$CLUSTER --set image=$IMAGE
signadot routegroup apply -f epic-routegroup.yaml --set cluster=$CLUSTER
```

The last command prints the route group's preview URL,
`https://hotrod-frontend--epic-42-preview.preview.signadot.com`.

## 5. Test the feature end to end

Open the preview URL in a browser where you're signed in to [app.signadot.com](https://app.signadot.com)
and request a ride. With both pull requests in the request path, the frontend shows the surcharge:

![HotROD with the Dynamic Surcharge Applied banner](./images/dynamicsurcharge.png)

To compare the other combinations, open http://frontend.hotrod.svc:8080 with `signadot local connect`
running and pick a routing context in the
[Signadot Chrome extension](https://chromewebstore.google.com/detail/signadot/aigejiccjejdeiikegdjlofgcjhhnkim):

| Routing context | Result |
| --- | --- |
| None (baseline) | The ride works, no banner. |
| `route-surcharge-feature` | The ride works, no banner: nothing calls the new method yet. |
| `frontend-surcharge-feature` | The ride works, no banner, and the frontend logs `Failed to get surcharge`. |
| `epic-42-preview` | The banner shows `$1.25`. |

![Selecting a routing context in the Chrome extension](./images/ext.png)

## Automate it with GitHub Actions

The two workflows in `.github/workflows` run the same flow in CI. Copy them into each service
repository and set `SERVICE` to the service that repository builds. They need these repository
secrets:

| Secret | Value |
| --- | --- |
| `SIGNADOT_API_KEY` | An API key from a [service account](https://www.signadot.com/docs/guides/admin/service-accounts) |
| `SIGNADOT_ORG` | Your Signadot organization name |
| `SIGNADOT_CLUSTER` | The cluster name registered with Signadot |
| `DOCKER_USERNAME`, `DOCKER_PASSWORD` | Credentials for your container registry |

Replace `<your-dockerhub-username>` in both files with your registry path.

- `create-pr-sandbox.yml` builds the image on every push to a pull request and creates or updates a
  sandbox named `<service>-pr-<number>`. It keeps the sandbox's `epic` label, so new commits don't
  drop the pull request out of its feature preview.
- `link-epic-preview.yml` runs when an owner, member or collaborator comments `/epic EPIC-42`. It labels
  the pull request's sandbox, creates or updates the `epic-42-preview` route group, and replies with
  the preview URL. The comment reaches the shell through an environment variable and must match a
  pattern, so a crafted comment can't inject commands.

![The /epic comment on a pull request](./images/comment.png)

![The workflow run](./images/workflow.png)

![The reply with the preview URL](./images/preview.png)

## Clean up

```bash
signadot routegroup delete epic-42-preview
signadot sandbox delete route-surcharge-feature
signadot sandbox delete frontend-surcharge-feature
signadot local disconnect
kubectl delete namespace hotrod
```

In CI, the Signadot GitHub App deletes each sandbox when its pull request closes, and the route
group's `ttl` removes the group a day after its last sandbox is gone.

## Next steps

- [How to Test a Feature That Spans Multiple Pull Requests](https://www.signadot.com/docs/tutorials/multi-pr-feature-testing?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=multi-pr-features): the full tutorial for this example.
- [Preview environment tutorials](https://www.signadot.com/docs/tutorials/preview-environments?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=multi-pr-features): Vercel frontends, mobile apps and more.
- New to Signadot? [Create a free account](https://www.signadot.com/signup/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=multi-pr-features) (no credit card), then try it on your own services.
- Questions? Ask in the [Signadot community Slack](https://join.slack.com/t/signadotcommunity/shared_invite/zt-1estxm8pv-qfiaNfiFFCaW~eUlXsVoEQ).
