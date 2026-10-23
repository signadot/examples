# HotROD iOS App: Preview Backend Changes from a Mobile App

A SwiftUI app for [HotROD](https://github.com/signadot/hotrod) that shows how a mobile developer can
try backend changes before they reach production. Each change runs in a Signadot sandbox, and the
app sends that sandbox's routing key in a `baggage` header. Requests with the key reach the
sandboxed services; requests without it reach the shared baseline. The app keeps calling the same
backend address either way.

> **Step-by-step tutorial:** [Preview Backend Changes in a Mobile App](https://www.signadot.com/docs/tutorials/mobile-app-previews?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=ios-app)
> walks through this example and shows how to do the same on Android, React Native and Flutter.

## How the app sends the routing key

`AppState` in `HotRodApp/Models.swift` holds the selected environment and turns its routing key into
two headers. `HotRODAPIService` in `HotRodApp/Services/APIService.swift` adds them to every request:

```swift
var routingHeaders: [String: String] {
    guard let routingKey = selectedEnvironment.routingKey else {
        return [:]
    }
    return [
        "baggage": "sd-routing-key=\(routingKey)",
        "tracestate": "sd-routing-key=\(routingKey)"
    ]
}
```

With the baseline selected, there are no extra headers. The app calls `http://frontend.hotrod:8080`
and `http://location.hotrod:8081`, which resolve on your Mac through `signadot local connect`.

## What's in this directory

| Path | What it is |
| --- | --- |
| `HotRodApp/Models.swift` | Environment options, the base URL and the routing headers. |
| `HotRodApp/Services/APIService.swift` | `HotRODAPIService`, which calls HotROD with the routing headers, and `MockAPIService`. |
| `HotRodApp/Views/EnvironmentSelectorView.swift` | The developer menu: Production (Baseline) or a custom sandbox routing key. |
| `HotRodApp/Views/HomeView.swift` | Location and driver selection and booking. |
| `signadot-config/` | Sandboxes for two HotROD changes: `route-fast-eta` (ETAs in seconds), `driver-sd-license` (`SD-` license plates), and `combined-features` (both). |

## Prerequisites

- macOS with Xcode 16.4 or later. The project targets iOS 18.5.
- A [Signadot account](https://www.signadot.com/signup/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=ios-app)
  and a Kubernetes cluster with the
  [Signadot Operator](https://www.signadot.com/docs/installation/signadot-operator) installed.
- The [Signadot CLI](https://www.signadot.com/docs/getting-started/installation/signadot-cli),
  logged in with `signadot auth login`, plus `kubectl` and `jq`.

## Run it

1. Deploy HotROD into the `hotrod` namespace:

   ```bash
   kubectl create namespace hotrod
   kubectl -n hotrod apply -k 'https://github.com/signadot/hotrod/k8s/overlays/prod/devmesh'
   kubectl -n hotrod wait --for=condition=available deployment --all --timeout=5m
   ```

2. Create the sandboxes. They set HotROD environment variables, so no image build is needed:

   ```bash
   export CLUSTER=<your-cluster>
   signadot sandbox apply -f signadot-config/route-fast-eta.yaml --set cluster=$CLUSTER
   signadot sandbox apply -f signadot-config/combined-features.yaml --set cluster=$CLUSTER
   signadot sandbox get route-fast-eta -o json | jq -r .routingKey
   ```

3. Connect your Mac to the cluster, so the simulator can reach `frontend.hotrod` and
   `location.hotrod`:

   ```bash
   signadot local connect --cluster=$CLUSTER
   ```

4. Open `HotRodApp.xcodeproj` in Xcode and run the app on an iPhone simulator.

5. Tap the wrench icon to open **Developer Mode**, choose **Custom Sandbox...** in the
   **Test Environment** menu, paste the routing key from step 2 and tap **Connect**. Then book a
   ride.

To confirm that the sandbox handled the request, read the forked route pod's logs:

```bash
kubectl -n hotrod get pods | grep route-fast-eta
kubectl -n hotrod logs <route-fast-eta-pod> -c hotrod | grep "Finding route"
```

## Limitations

The app is a UI prototype. Its requests to HotROD are real and carry the routing headers, but it
fills in the driver rows itself, and the trip and rating screens use `MockAPIService`. So the
driver list shows the intended result of each sandbox, and the pod logs (or the `curl` check in
the tutorial) are the real proof. In your own app, the screen renders whatever the sandboxed
backend returns.

## Next steps

- [Preview Backend Changes in a Mobile App](https://www.signadot.com/docs/tutorials/mobile-app-previews?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=ios-app): the full tutorial for this example.
- [Testing multi-PR features](https://www.signadot.com/docs/tutorials/multi-pr-feature-testing?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=ios-app): build a route group whose routing key the app can use when a feature spans several pull requests.
- New to Signadot? [Create a free account](https://www.signadot.com/signup/?utm_source=github&utm_medium=readme&utm_campaign=examples&utm_content=ios-app) (no credit card), then try it on your own services.
- Questions? Ask in the [Signadot community Slack](https://join.slack.com/t/signadotcommunity/shared_invite/zt-1estxm8pv-qfiaNfiFFCaW~eUlXsVoEQ).
