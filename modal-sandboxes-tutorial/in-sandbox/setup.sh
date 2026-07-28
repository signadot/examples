#!/usr/bin/env bash
# Configure the Signadot CLI inside the Modal sandbox and connect to the cluster.
# SIGNADOT_ORG / SIGNADOT_API_KEY come from the Modal secret `signadot-credentials`.
set -euo pipefail

CLUSTER="${1:?usage: setup.sh <signadot-cluster-name>}"

: "${SIGNADOT_ORG:?SIGNADOT_ORG must be set (Modal secret signadot-credentials)}"
: "${SIGNADOT_API_KEY:?SIGNADOT_API_KEY must be set (Modal secret signadot-credentials)}"

# gVisor (the Modal sandbox runtime) exposes neither /etc/machine-id nor
# /proc/sys/kernel/random/uuid, which the Signadot CLI uses to identify this
# "machine". Generate one for this sandbox.
if [ ! -s /etc/machine-id ]; then
    python3 -c "import uuid; open('/etc/machine-id','w').write(uuid.uuid4().hex + '\n')"
    echo "Generated /etc/machine-id: $(cat /etc/machine-id)"
fi

mkdir -p "$HOME/.signadot"
cat > "$HOME/.signadot/config.yaml" <<EOF
local:
  connections:
  - cluster: ${CLUSTER}
    type: ControlPlaneProxy
EOF
echo "Wrote ~/.signadot/config.yaml (cluster=${CLUSTER}, type=ControlPlaneProxy)"

# --unprivileged: Modal sandboxes run on gVisor, which does not implement
# netfilter NAT, so the privileged localnet setup (virtual IPs + cluster DNS)
# is unavailable. Unprivileged mode still supports everything this workflow
# needs: inbound tunneling for local sandboxes and `signadot local proxy`
# for reaching in-cluster services.
signadot local connect --unprivileged --wait connect --wait-timeout 120s
signadot local status
