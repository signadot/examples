SHELL = /bin/sh
.PHONY: build


build:
	docker build -t signadot/kafka-demo:latest .

k8s-all-in-one:
	rm -f k8s/all-in-one/demo.yaml
	for f in k8s/pieces/*.yaml; do \
		echo $$f ; \
		cat $$f >> k8s/all-in-one/demo.yaml ; \
		echo "---" >> k8s/all-in-one/demo.yaml ; \
	done