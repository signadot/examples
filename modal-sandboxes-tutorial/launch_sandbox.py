"""Launch a Modal Sandbox configured as a Signadot-connected cloud dev environment.

Usage:
    modal run launch_sandbox.py --cluster <signadot-cluster-name>

Then connect with:
    modal shell <sandbox-id>
"""

import modal

app = modal.App("signadot-dev-env")

GO_VERSION = "1.24.5"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "curl", "ca-certificates", "vim", "procps", "lsof", "jq")
    .run_commands(
        # Go toolchain (HotROD services are written in Go). Symlink into
        # /usr/local/bin so login shells (modal shell) find it regardless of
        # profile PATH resets.
        f"curl -fsSL https://go.dev/dl/go{GO_VERSION}.linux-amd64.tar.gz | tar -C /usr/local -xz",
        "ln -s /usr/local/go/bin/go /usr/local/bin/go && ln -s /usr/local/go/bin/gofmt /usr/local/bin/gofmt",
        # Node.js 22 + Claude Code
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g @anthropic-ai/claude-code",
        # Signadot CLI
        "curl -sSLf https://raw.githubusercontent.com/signadot/cli/main/scripts/install.sh | sh",
    )
    .env(
        {
            "PATH": "/usr/local/go/bin:/root/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        }
    )
    .add_local_file("in-sandbox/setup.sh", "/opt/dev-env/setup.sh", copy=True)
    .add_local_file("in-sandbox/CLAUDE.md", "/root/workspace/CLAUDE.md", copy=True)
    .add_local_file("local-route.yaml", "/root/workspace/local-route.yaml", copy=True)
)


@app.local_entrypoint()
def main(cluster: str):
    # Create the sandbox against a persistent (deployed) app so it outlives
    # this `modal run` invocation. Sandboxes attached to the ephemeral run
    # app would be terminated as soon as this entrypoint returns.
    sandbox_app = modal.App.lookup("signadot-dev-env", create_if_missing=True)
    sb = modal.Sandbox.create(
        image=image,
        app=sandbox_app,
        secrets=[
            # SIGNADOT_ORG + SIGNADOT_API_KEY
            modal.Secret.from_name("signadot-credentials"),
            # CLAUDE_CODE_OAUTH_TOKEN (subscription) or ANTHROPIC_API_KEY
            modal.Secret.from_name("claude-code-auth"),
        ],
        timeout=4 * 60 * 60,  # 4h interactive dev session
        cpu=2,
        memory=4096,
    )
    print(f"Sandbox created: {sb.object_id}")
    print("Running Signadot setup (local connect)...")
    p = sb.exec("bash", "/opt/dev-env/setup.sh", cluster)
    for line in p.stdout:
        print(line, end="")
    for line in p.stderr:
        print(line, end="")
    if p.wait() != 0:
        print("Setup failed — shell in to debug:")
    print(f"\nConnect with:  modal shell {sb.object_id}")
