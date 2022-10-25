#!/bin/bash

set -ex

cd `dirname $0`
gradle clean test
