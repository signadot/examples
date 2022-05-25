#!/bin/bash

set -ex

cd `dirname $0`

python3 -m pip install -r test-requirements.txt
python3 tests/integration/create_sandbox_test.py
python3 tests/integration/resources_test.py
ROUTE_IMAGE=signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd python3 tests/integration/usecase1_test.py
ROUTE_IMAGE=signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3 FRONTEND_IMAGE=signadot/hotrod-frontend:5069b62ddc2625244c8504c3bca6602650494879 python3 tests/integration/usecase2_test.py
