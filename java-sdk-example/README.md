# Signadot Java SDK Example
This example application uses Signadot's Java SDK to create a workspace and test the preview URL in the context of Integration Testing with workspaces.

# Testing
The test creates a workspace in the setup phase, runs tests against it and deletes the workspace upon completion of the tests. Heres' the command to run it:

```
SIGNADOT_API_KEY=<SIGNADOT_API_KEY_HERE> gradle clean test
```
