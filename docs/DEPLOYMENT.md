# Deployment Guide

## Helm charts

The [charts](../deployment/charts/api) directory contains Helm charts that can be used to deploy this app.

### Helm chart versioning and release process

Helm chart releases are automated and driven by Git tags.

To release a new Helm Chart version, create a Git tag in the format:

`vMAJOR.MINOR.PATCH[-PRERELEASE]`

Examples:
- `v1.2.3` → stable release
- `v1.3.0-alpha.1` → prerelease

The workflow triggers on tag creation.
The CI workflow:

- Reads the tag version (1.2.3 from v1.2.3)
- Patches `deployment/charts/api/Chart.yaml` at package time (does not commit to the repo)
- Packages the Helm chart with the correct version
- Publishes the chart via [helm/chart-releaser-action](https://github.com/helm/chart-releaser-action)

Whenever you make any change to a Chart, you must update the version in `Chart.yaml`.

* Increment the version to a higher value (e.g. `0.0.0-dev` → `0.0.1-dev`)
* This is required because the lint process checks that the new version is greater than the previous one
* If the version is not increased, linting will fail and the release will not run

> Note: The `Chart.yaml` version does not need to match the Git tag, but it must always be higher than the previous version.

To tag a git commit:

```bash
git tag vX.X.X
git push origin vX.X.X
```

### Deployment

To deploy the application using Helm, follow the instructions in the [worms-cache-api-helm repo](https://gitlab.com/nocacuk/BODC/server-config/kubernetes/worms-cache-api-helm). You may need to have permissions to access the repository.

## Docker images

Docker images are published to:

`ghcr.io/paidiver/worms-cache`

### Latest image

A new `latest` Docker image is built and published automatically on every push to `main`.

### Versioned development images

Versioned Docker images can be released manually using Git tags.

To release a new Docker image, create a tag using the following format:

```text
docker-vMAJOR.MINOR.PATCH[-PRERELEASE]
```

Examples:

```text
docker-v1.2.3
docker-v1.3.0-alpha.1
```

When the tag is pushed, the CI workflow:

1. Reads the version from the tag, for example `1.2.3` from `docker-v1.2.3`
2. Builds a new Docker image
3. Tags the image with the version and the commit SHA
4. Pushes the image to GitHub Container Registry

To create and push a Docker release tag:

```bash
git tag docker-vX.X.X
git push origin docker-vX.X.X
```
