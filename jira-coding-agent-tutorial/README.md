# From Jira ticket to tested pull request with Signadot

Pipeline configuration and test files for the Jira Coding Agent tutorial, using
[HotROD](https://github.com/signadot/hotrod) as the application. Bitbucket Pipelines builds each
pull request's image, creates a Signadot sandbox with the changed services and runs Playwright
against it. The pull request report links to the preview and test results.

The added test checks that the ride banner still displays the driver's ID when the arrival message
changes. Pull requests that change only documentation, tests or test configuration skip the sandbox
and test Job.

For setup and the Jira workflow, follow the
[full tutorial](https://www.signadot.com/docs/tutorials/jira-coding-agent-signadot-sandboxes).

## What's in this directory

The `files` directory mirrors the root of your HotROD repository. The tutorial copies it in with
`cp -R ../signadot-examples/jira-coding-agent-tutorial/files/. .`. The example targets
HotROD revision `36525ff00bb760fd44df64ec277da94d63522ac1`.

| File | Purpose |
| --- | --- |
| `bitbucket-pipelines.yml` | Builds the image, creates the sandbox, runs tests and triggers cleanup |
| `.signadot/jira-agent/changed-services.sh` | Lists changed services; selects all four for shared-code changes |
| `.signadot/jira-agent/delete-sandbox.sh` | Deletes the sandbox if it exists |
| `.signadot/jira-agent/sandbox.sh` | Generates the sandbox spec for the changed services |
| `.signadot/jira-agent/run-tests.sh` | Submits the test Job and checks its result |
| `.signadot/jira-agent/report.sh` | Posts the result, preview and Job links to Bitbucket Code Insights |
| `.signadot/jira-agent/runner.yaml` | Configures the Playwright runner and repository credentials |
| `.signadot/jira-agent/playwright-job.yaml` | Checks out the PR commit and runs HotROD's Playwright suite |
| `playwright-tests/ride-banner.spec.ts` | Checks that the ride banner shows the driver's ID |

`runner.yaml` pins `mcr.microsoft.com/playwright:v1.45.1-jammy`, the version of `@playwright/test` in
HotROD's lockfile at the tested revision. For your own repository, read that version from your
lockfile and use the matching `mcr.microsoft.com/playwright:v<version>-jammy` image.

## Bitbucket plan

Free includes Pipelines; Standard provides more build minutes. Check your workspace's
[plan and available build minutes](https://support.atlassian.com/bitbucket-cloud/docs/manage-your-plan-and-billing/)
before starting.

## Repository variables

Add these under **Repository settings > Pipelines > Repository variables**, as the tutorial shows.

| Name | Secured | Example | Notes |
| --- | --- | --- | --- |
| `SIGNADOT_ORG` | No | `my-org` | Organization from `signadot auth status` |
| `SIGNADOT_API_KEY` | Yes | | API key from a service account with the `member` role |
| `SIGNADOT_CLUSTER` | No | `my-cluster` | Cluster name from `signadot cluster list` |
| `DOCKERHUB_USERNAME` | No | `my-dockerhub-user` | Docker Hub account the image is pushed to |
| `DOCKERHUB_TOKEN` | Yes | | Docker Hub access token with read and write access |

Before running the pipeline, [create a public Docker Hub repository](https://docs.docker.com/docker-hub/repos/create/)
named `hotrod` under `DOCKERHUB_USERNAME`. The pipeline pushes
`docker.io/<DOCKERHUB_USERNAME>/hotrod:<commit>`, and the cluster pulls it without credentials.

## Troubleshooting

| What you see | What to check |
| --- | --- |
| **Enable Pipelines** is greyed out in a new workspace | Turn on two-step verification for your Bitbucket account under **Personal Bitbucket settings > Two-step verification**, then reload the page. |
| `git push` to the new repository is refused with "exceeded its user limit" | Check the workspace's user count and plan under **Plans and billing**. If the count is within the limit, ask Atlassian support to check the workspace's access restrictions. |
| No pipeline runs on the agent's pull request | Check that `bitbucket-pipelines.yml` is on `main` and that Pipelines is enabled for the repository. |
| `docker login` fails in **Build and push the image** | Check `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`. |
| `signadot sandbox apply` reports an authentication error | Check `SIGNADOT_ORG` and `SIGNADOT_API_KEY`, and whether the key has expired. |
| The sandbox readiness wait times out | Run `kubectl -n hotrod get pods` and look for `ImagePullBackOff`. The Docker Hub repository must be public. |
| The Job stays queued | Run `signadot jrg get hotrod-playwright` and `kubectl -n signadot-tests get pods,events`. The runner has one pod, so Jobs run one at a time. |
| The Job fails before the tests start | Check the `hotrod-repo-read` Secret and that its repository access token has read access to this repository. |
| The Jira Coding Agent asks for a repository but none is listed | Connect Bitbucket to the Jira space under **Development > Connections**, then start the session again. |

## Run times

Allow about six minutes for the pipeline. The first run can take longer while dependencies and
images are downloaded.

The Job uploads `playwright-report.tgz`, with Playwright's HTML report, traces and videos. Find it
under **Artifacts** on the Job's page in the Signadot Dashboard. Each Job times out after 20 minutes
(`jobTimeout` in `runner.yaml`).

## Cleanup

Merging or declining a pull request into `main` triggers sandbox deletion. Sandboxes also expire
three days after their last update. After the tutorial, check for remaining sandboxes:

```bash
signadot sandbox list
```

If a tutorial sandbox remains, run `signadot sandbox delete NAME`, replacing `NAME` with its name
from the list. Then delete the Job Runner Group and its repository credential:

```bash
signadot jrg delete hotrod-playwright
kubectl -n signadot-tests delete secret hotrod-repo-read
```

If you created `signadot-tests` exclusively for this tutorial, you can also run
`kubectl delete namespace signadot-tests`. Keep it if other workloads use it.

Revoke the repository access token, the Docker Hub token and the Signadot API key you created for the
tutorial. Delete the service account only if nothing else uses it.
