DOCKER ?= docker
YARN ?= yarn

build-docker:
	$(YARN) build-image --tag signadot/backstage-sample-app:latest

push-docker: build-docker
	$(DOCKER) push signadot/backstage-sample-app:latest
