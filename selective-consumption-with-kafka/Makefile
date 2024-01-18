SHELL = /bin/sh
.PHONY: build


build:
	docker build -t signadot/kafka-demo:latest .

build-multi-arch:
	docker build -t signadot/kafka-demo:latest-linux-amd64 \
		--platform linux/amd64 --provenance false .
	docker build -t signadot/kafka-demo:latest-linux-arm64 \
		--platform linux/arm64 --provenance false .
	docker push signadot/kafka-demo:latest-linux-amd64
	docker push signadot/kafka-demo:latest-linux-arm64
	docker manifest create --amend signadot/kafka-demo:latest \
		signadot/kafka-demo:latest-linux-amd64 \
		signadot/kafka-demo:latest-linux-arm64
	docker manifest push signadot/kafka-demo:latest

k8s-all-in-one:
	rm -f k8s/all-in-one/demo.yaml
	for f in k8s/pieces/*.yaml; do \
		echo $$f ; \
		cat $$f >> k8s/all-in-one/demo.yaml ; \
		echo "---" >> k8s/all-in-one/demo.yaml ; \
	done