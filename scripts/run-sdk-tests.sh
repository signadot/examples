#!/bin/bash

set -ex

export SIGNADOT_API_KEY
export SIGNADOT_ORG_NAME
export SIGNADOT_CLUSTER_NAME

../java-sdk-example/run-tests.sh
../node-sdk-example/run-tests.sh
../python-sdk-example/run-tests.sh 
