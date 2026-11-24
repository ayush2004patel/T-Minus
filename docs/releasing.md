# Releasing T-MINUS

The release workflow runs when a `v*` tag is pushed. It builds the wheel and source distribution,
installs the wheel in a fresh virtual environment, runs a scanner smoke test, creates the GitHub
release and publishes to PyPI. Version 1.0.1 is the current published release.

Before publishing a later release, make sure the repository secret `PYPI_API_TOKEN` contains a
valid PyPI API token. The workflow passes that secret to the PyPI publishing action.

Release only after the CI workflow is green:

```bash
git tag v<version>
git push origin v<version>
```

The tag is the deliberate publish action. Running the workflow manually only builds and tests the
artifacts; it does not create a GitHub release or publish to PyPI.
