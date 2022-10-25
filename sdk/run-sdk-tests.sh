#!/bin/bash

set -ex

export SIGNADOT_API_KEY
export SIGNADOT_ORG
export SIGNADOT_CLUSTER_NAME

./java/run-tests.sh
./node/run-tests.sh
./python/run-tests.sh 
