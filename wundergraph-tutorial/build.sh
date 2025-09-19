#!/bin/bash
set -e

cd ~/git/thrid-party/wundergraph/cosmo/demo

# Build demo images
docker build -t signadot/wundergraph-demo-products:latest -f ./docker/products.Dockerfile .
docker build -t signadot/wundergraph-demo-products_fg:latest -f ./docker/products_fg.Dockerfile .
docker build -t signadot/wundergraph-demo-employees:latest -f ./docker/employees.Dockerfile .
docker build -t signadot/wundergraph-demo-mood:latest -f ./docker/mood.Dockerfile .
docker build -t signadot/wundergraph-demo-availability:latest -f ./docker/availability.Dockerfile .

