# Use KUBE_CONTEXT explicitly when deploying. No target switches your context.
SHELL := /bin/bash
# macOS ships make 3.81, which ignores .SHELLFLAGS, so each recipe sets its own flags.
SERVICES := storefront inventory pricing
REGISTRY ?= signadot
TAG ?= baseline
LOAD ?= minikube -p minikube image load
KUBE_CONTEXT ?= minikube
KUBECTL := kubectl --context $(KUBE_CONTEXT)

.PHONY: images deploy clean
images:
	@set -euo pipefail; for s in $(SERVICES); do \
	  docker build -t "$(REGISTRY)/boxoffice-demo-$$s:$(TAG)" -f "docker/$$s.Dockerfile" .; \
	  $(LOAD) "$(REGISTRY)/boxoffice-demo-$$s:$(TAG)"; \
	done

deploy:
	$(KUBECTL) apply -f k8s/namespace.yaml
	set -euo pipefail; $(KUBECTL) -n boxoffice create configmap boxoffice-db-init \
	  --from-file=01-schema.sql=db/schema.sql --from-file=02-seed.sql=db/seed.sql \
	  --dry-run=client -o yaml | $(KUBECTL) apply -f -
	@set -euo pipefail; for f in k8s/*.yaml; do \
	  sed -e 's|image: signadot/boxoffice-demo-|image: $(REGISTRY)/boxoffice-demo-|' \
	      -e 's|:baseline$$|:$(TAG)|' "$$f"; printf '\n---\n'; \
	done | $(KUBECTL) apply -f -
	@set -euo pipefail; for s in postgres redis $(SERVICES); do \
	  $(KUBECTL) -n boxoffice rollout status "deploy/$$s" --timeout=180s; \
	done

clean:
	$(KUBECTL) delete namespace boxoffice --ignore-not-found
