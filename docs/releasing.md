# Releasing T-MINUS

The release workflow runs when a `v*` tag is pushed. It builds the wheel and source distribution,
installs the wheel in a fresh virtual environment, runs a scanner smoke test, creates the GitHub
release and publishes to PyPI.

Before the first release, configure PyPI Trusted Publishing for this GitHub repository:

- owner and repository: this repository's GitHub location
- workflow: `release.yml`
- environment: `pypi`

The workflow uses GitHub's OIDC token, so no PyPI API token is stored in the repository.

Release only after the CI workflow is green:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The tag is the deliberate publish action. Running the workflow manually only builds and tests the
artifacts; it does not create a GitHub release or publish to PyPI.
