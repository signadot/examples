#!/bin/bash

set -ex

cd `dirname $0`
npm install && npm run test
