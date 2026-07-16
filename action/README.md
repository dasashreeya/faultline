# Faultline Gate Action

Use this composite action after checking out a repository that contains a
`faultline.yaml` target config.

```yaml
name: faultline

on:
  pull_request:
  workflow_dispatch:

jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: dasashreeya/faultline/action@<commit-sha>
        with:
          path: examples/support_bot
          min-score: "85"
```

The action installs Python and `uv`, runs `faultline break`, renders
`faultline report`, then fails the job if `faultline gate` sees a score below
the configured threshold. Pin a release tag or full commit SHA in production.

For development inside this repository, `uses: ./action` remains supported.
The composite action runs Faultline from its own checkout, so it also works
when consumed from another repository whose root is not a Python project.
