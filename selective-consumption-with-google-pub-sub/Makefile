SHELL = /bin/sh
.PHONY: build push


# Build your own image and push it to a registry your cluster can pull from:
#   make build push IMAGE=<your-registry>/pubsub-demo:latest
# Add PLATFORM=linux/arm64 if your nodes are ARM.
IMAGE ?= signadot/pubsub-demo:latest
PLATFORM ?= linux/amd64

build:
	docker build --platform $(PLATFORM) -t $(IMAGE) .

push:
	docker push $(IMAGE)

build-multi-arch:
	docker build -t signadot/pubsub-demo:latest-linux-amd64 \
		--platform linux/amd64 --provenance false .
	docker build -t signadot/pubsub-demo:latest-linux-arm64 \
		--platform linux/arm64 --provenance false .
	docker push signadot/pubsub-demo:latest-linux-amd64
	docker push signadot/pubsub-demo:latest-linux-arm64
	docker manifest create --amend signadot/pubsub-demo:latest \
		signadot/pubsub-demo:latest-linux-amd64 \
		signadot/pubsub-demo:latest-linux-arm64
	docker manifest push signadot/pubsub-demo:latest

k8s-all-in-one:
	rm -f k8s/all-in-one/demo.yaml
	for f in k8s/pieces/*.yaml; do \
		echo $$f ; \
		cat $$f >> k8s/all-in-one/demo.yaml ; \
		echo "---" >> k8s/all-in-one/demo.yaml ; \
	done