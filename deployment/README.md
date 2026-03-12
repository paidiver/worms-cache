# PAIDIVER Worms Cache API deployment

The PAIDIVER Worms Cache API provides a database-backed REST API for caching and querying WoRMS taxonomic data. This document outlines the steps to deploy the application using Helm and Helmfile on a Kubernetes cluster.

The application source code and Helm charts are hosted under
https://github.com/paidiver/worms-cache.

These instructions guide you through deploying the application using Helm and Helmfile. They assume a Kubernetes cluster is already available and accessible.

> IMPORTANT: All the commands in this section are running on the `charts` directory, so make sure to `cd charts` before running the commands.

---
## Table of Contents

- [Prerequisites](#prerequisites)
- [Helm Charts configuration](#helm-charts-configuration)
- [Deployment Steps: New Deployment](#deployment-steps---new-deployment)
- [Connecting to Postgres](#connect-to-postgres)
- [Deployment Steps: Upgrade Deployment](#deployment-steps---upgrade-deployment)

---
## Prerequisites

Before deploying, ensure the following tools are installed and available in your shell:

- **[Docker](https://www.docker.com/get-started)** – required for building or pulling container images.
- **[kubectl](https://kubernetes.io/docs/tasks/tools/)** – command-line tool for interacting with Kubernetes.
- **[Helm](https://helm.sh/docs/intro/install/)** – package manager for Kubernetes charts.
- **[Helm diff](https://github.com/databus23/helm-diff)** - a Helm plugin that shows a preview of what a `helm upgrade` (or `helmfil apply`) would change
- **[Helmfile](https://github.com/helmfile/helmfile?tab=readme-ov-file#installation)** – manages deployments of multiple Helm charts as a single unit.
- **Git Bash (Windows) or a Linux shell**

---

## Helm Charts configuration

The [deployment/charts](charts) directory contains Helm charts that can be used to deploy this app.

### Helm Chart Versioning & Release Process

Helm chart releases are automated and driven by Git tags.

To release a new Helm Chart version, create a Git tag in the format:

`vMAJOR.MINOR.PATCH[-PRERELEASE]`

Examples:
- `v1.2.3` → stable release
- `v1.3.0-alpha.1` → prerelease

The workflow triggers on tag creation.
The CI workflow:

- Reads the tag version (1.2.3 from v1.2.3)
- Patches deployment/charts/Chart.yaml at package time (does not commit to the repo)
- Packages the Helm chart with the correct version
- Publishes the chart via [helm/chart-releaser-action](https://github.com/helm/chart-releaser-action)

The repo itself continues to have 0.0.0-dev in Chart.yaml for development.
The release version is derived solely from the Git tag.

### Usage

[Helm](https://helm.sh) must be installed to use the charts.  Please refer to
Helm's [documentation](https://helm.sh/docs) to get started.

Once Helm has been set up correctly, add the repo as follows:

```bash
helm repo add worms-cache https://paidiver.github.io/worms-cache
```

If you had already added this repo earlier, run `helm repo update` to retrieve
the latest versions of the packages.  You can then run `helm search repo
worms-cache` to see the charts.

To install the api chart:

```bash
helm install my-api worms-cache/api
```

To uninstall the chart:

```bash
helm uninstall my-api
```

### Release Charts outside of CI

For local testing, you can run the release script in `charts/release-script.sh` to package and publish charts manually. This script uses the `cr` CLI tool to upload packages to GitHub Releases and update the Helm repo index. First, you need to install `cr` and `yq` and authenticate with GitHub:

```bash
brew install yq
brew install chart-releaser
export CR_TOKEN=your_github_pat
```

Then you can run the release script:

```bash
cd charts
bash release-script.sh
```

This will package the chart, upload it to GitHub Releases, and update the Helm repo index. The script is designed to be idempotent and can be run multiple times without creating duplicate releases.

---

## Deployment Steps - New Deployment

### ⚠️ Git Bash or a Linux shell are required to run the commands below.

### 1. Set environment variables

1. Copy the [.env.example](.env.example) file
2. Rename the copy `.env`
3. Check the preset values
4. Fill in the required passwords:
   1. **GHCR_TOKEN**: GitHub access token (bodcsoft user) found in OnePassword under `DSG_BODC_EXTERNAL_TOOLS`. Search for "GitHub Container Registry access for Paidiver Worms Cache API".
   2. **POSTGRES_PASSWORD**: Found in OnePassword under `DSG_BODC_GENERIC`. Search for "PAIDIVER DEV Postgres worms-cache user password".
   3. **POSTGRES_SUPERUSER_PASSWORD**: Found in OnePassword under `DSG_BODC_GENERIC`. Search for "PAIDIVER DEV Postgres worms-cache admin user password".
   4. **DJANGO_SECRET_KEYFound** in OnePassword under `DSG_BODC_GENERIC`. Search for "PAIDIVER DEV Django secret key".

### 2. Source the .env file

```bash
set -a
source .env
set +a
```

### 3. Set your Kubernetes context

   Make sure your shell points to the correct cluster.

   - Confirm that the output from the following command matches the intended cluster:
       ```bash
       kubectl config current-context
       ```

   - Confirm you can run commands in the cluster and namespace:
       ```bash
       kubectl get pods -n $NAMESPACE
       ```

---

### 4. Create deployment secrets

   The deployment requires the following Kubernetes secrets:
   - **GitHub image pull secret** – used to pull container images from private repositories.
   - **Postgres credentials secret** – contains database passwords.
   - **Django secret key**

Check if secrets exist:
```bash
kubectl get secrets -n $NAMESPACE
```
If the secrets don't exist, create them.

1. **GitHub Image Pull Secret**
    ```bash
    ghcr_secret_template=$(
    sed \
    -e "s/{{NAMESPACE}}/$NAMESPACE/g" \
    -e "s/{{GHCR_SECRET_NAME}}/$GHCR_SECRET_NAME/g" \
    -e "s/{{GHCR_USERNAME}}/$GHCR_USERNAME/g" \
    -e "s/{{GHCR_TOKEN}}/$GHCR_TOKEN/g" \
    utils/ghcr-pull-secret.yaml
    )
    echo "$ghcr_secret_template" | kubectl apply -f -
    ```
2. **Postgres Credentials Secret**
    ```bash
    postgres_secret_template=$(
    sed \
    -e "s/{{NAMESPACE}}/$NAMESPACE/g" \
    -e "s/{{POSTGRES_SECRET_NAME}}/$POSTGRES_SECRET_NAME/g" \
    -e "s/{{POSTGRES_PASSWORD}}/$POSTGRES_PASSWORD/g" \
    -e "s/{{POSTGRES_SUPERUSER_PASSWORD}}/$POSTGRES_SUPERUSER_PASSWORD/g" \
    utils/postgres-secret.yaml
    )
    echo "$postgres_secret_template" | kubectl apply -f -
    ```
3. **Django Secret Key**
    ```bash
    django_secret_template=$(
    sed \
    -e "s/{{NAMESPACE}}/$NAMESPACE/g" \
    -e "s/{{DJANGO_SECRET_NAME}}/$DJANGO_SECRET_NAME/g" \
    -e "s/{{DJANGO_SECRET_KEY}}/$DJANGO_SECRET_KEY/g" \
    utils/django-secret.yaml
    )
    echo "$django_secret_template" | kubectl apply -f -
    ```
Confirm the secrets have been created:

```bash
kubectl get secrets -n $NAMESPACE
```

---
### 3. Create Postgres PersistentVolumeClaim

1. **Check POSTGRES_PVC_SIZE**

   Ensure the value for storage capacity set in POSTGRES_PVC_SIZE in `.env` is adequate for your deployment or adjust as necessary.


2. **Create PersistentVolumeClaim**

    ```bash
    pvc_template=$(
    sed \
    -e "s/{{RELEASE_NAME}}/$RELEASE_NAME/g" \
    -e "s/{{NAMESPACE}}/$NAMESPACE/g" \
    -e "s/{{POSTGRES_PVC_NAME}}/$POSTGRES_PVC_NAME/g" \
    -e "s/{{POSTGRES_PVC_SIZE}}/$POSTGRES_PVC_SIZE/g" \
    utils/postgres-pvc.yaml
    )
    echo "$pvc_template" | kubectl apply -f -
    ```

   Confirm the PVC has been created:

   ```bash
   kubectl get pvc -n $NAMESPACE
   ```

3. **Purge Volume**

   The NFS-backed PersistentVolume storage for Postgres is created containing some metadata,
   causing Postgres to assume persisted data exists and skip initialisation of the required user and database.
   The below "purge-volume" job ensures the PVC is completely empty and allows Postgres to initialise as expected.

    ```bash
    purge_volume_job_template=$(
    sed \
    -e "s/{{NAMESPACE}}/$NAMESPACE/g" \
    -e "s/{{POSTGRES_PVC_NAME}}/$POSTGRES_PVC_NAME/g" \
    utils/purge-volume.yaml
    )
    echo "$purge_volume_job_template" | kubectl apply -f -
    ```
    View job logs to confirm the job has succeeded and the directory is empty.

---


### 4. Cluster Issuer for TLS certificates

The cluster issuer is a cert-manager resource that defines how TLS certificates should be obtained for the API's ingress. This deployment uses Let's Encrypt as the certificate authority.

1. **Check CLUSTER_ISSUER_NAME**

   Ensure the value for CLUSTER_ISSUER_NAME in `.env` is set to your intended name or adjust as necessary.

2. **Create Cluster Issuer**

    ```bash
    cluster_issuer_template=$(
    sed \
    -e "s/{{NAMESPACE}}/$NAMESPACE/g" \
    -e "s/{{CLUSTER_ISSUER_NAME}}/$CLUSTER_ISSUER_NAME/g" \
    utils/cluster-issuer.yaml
    )
    echo "$cluster_issuer_template" | kubectl apply -f -
    ```

3. **Confirm Cluster Issuer Creation**

   ```bash
   kubectl get clusterissuer -n $NAMESPACE
   ```

### 4. Update Helm repositories

Add the Paidiver chart repo and ensure Helm has the latest chart information:

   ```bash
   helm repo add worms-cache https://paidiver.github.io/worms-cache
   helm repo update
   ```
### 5. Set chart version in Helmfile

Open the [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl) and ensure the `releases.version` field matches the intended chart version.

The version is derived from Git tags on the [PAIDIVER Worms Cache API](https://github.com/paidiver/worms-cache) repo,
or check the latest version by running
```bash
helm search repo -l worms-cache
```
---
### 6. Set Docker image version in Helmfile

Open the [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl) and ensure the `releases.values.api.image.tag` field matches the Docker image version you wish to deploy.

---
### 7. Preview changes
Run a dry-run diff to see what Helm will install or change:
```bash
helmfile -e {env} diff
```
---
### 8. Apply deployment
Once satisfied with the diff:
```bash
helmfile -e {env} apply
```

Check the Postgres pod logs that the required user and database have been created.
```
postgresql 16:41:30.55 INFO  ==> Changing password of postgres
postgresql 16:41:30.75 INFO  ==> Creating user worms_cache
postgresql 16:41:31.04 INFO  ==> Granting access to "worms_cache" to the database "worms_cache"
postgresql 16:41:31.34 INFO  ==> Setting ownership for the 'public' schema database "worms_cache" to "worms_cache"
```

#### ⚠️ Note for new deployments/redeployments after teardown:

It's expected for the API pod not to start immediately after initial container (State of the API pod will show Init:0/1).
This is normal while the initContainer waits for Postgres to be fully set up.

Follow the steps described in [Initialise PostGIS](#9-initialise-postgis) to finish initialising Postgres and allow the API pod to start.

---

### 9. Initialise PostGIS

PostGIS extends the capabilities of the PostgreSQL relational database by adding support for storing, indexing, and querying geospatial data. For further information, refer to the [official PostGIS documentation](https://postgis.net/).
1. [Connect to Postgres](#connect-to-postgres) as the postgres user.


2. Verify that the PostGIS extension is installed:
    ```bash
    SELECT * FROM pg_available_extensions WHERE name = 'postgis';
    ```
3. Initialize PostGIS:
    ```bash
    CREATE EXTENSION postgis;
    ```
4. Verify that PostGIS is properly initialized:
    ```bash
    SELECT PostGIS_Full_Version();
    ```
    You should see an output of the postgis_full_version like this:
    ```bash
    POSTGIS="3.4.4 e5ae0d4" [EXTENSION] PGSQL="170" GEOS="3.14.0-CAPI-1.20.4" PROJ="6.3.2" LIBXML="2.9.14" LIBJSON="0.16" LIBPROTOBUF="1.5.2" WAGYU="0.5.0 (Internal)"
    ```
---

### Connect to Postgres

To connect to the Postgres database from your local machine, you can use Kubernetes port forwarding. This section assumes the Postgres instance is deployed in your cluster and credentials are stored in a Kubernetes secret.

#### 1. Set environment variables

1. Copy the [.env.example](.env.example) file
2. Rename the copy `.env`

```bash
set -a
source .env
set +a
```

#### 2. Find the Postgres pod

List pods in the namespace and locate your Postgres pod:

```bash
kubectl get pods -n $NAMESPACE
```

Identify the pod name, e.g., `worms-cache-api-postgresql-0`.

#### 3. Locate the Postgres admin user password

The credentials are stored in a secret whose name can be found in the `$postgresSecret` variable defined in the [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl).

```bash
kubectl -n $NAMESPACE get secrets/$POSTGRES_SECRET_NAME -o jsonpath="{.data.postgres-password}" | base64 --decode
```

#### 4. Forward the Postgres port to localhost

Use `kubectl port-forward` to access Postgres locally (replace pod name if necessary):

```bash
kubectl port-forward -n $NAMESPACE pod/worms-cache-api-postgresql-0 5432:5432
```
This forwards the remote Postgres port 5432 to your local machine on `localhost:5432.
Keep this terminal open while you connect.

#### 5. Connect

Use an application like DBeaver or IntelliJ that can make PostgreSQL connections to create a new connection to Postgres.
- Username: `postgres`
- Password: password found in step 4
- Host: localhost
- Port: 5432
- DB: See POSTGRES_DB in .env

---

## Deployment Steps - Upgrade Deployment

### ⚠️ Git Bash or a Linux shell are required to run the commands below.

### 1. Set environment variables

1. Copy the [.env.example](.env.example) file
2. Rename the copy `.env`

### 2. Source the .env file

```bash
set -a
source .env
set +a
```

### 3. Check the preset values

The following variables in `.env` are required to have values to upgrade an existing deployment:
- RELEASE_NAME
- NAMESPACE
- GHCR_SECRET_NAME
- DJANGO_SECRET_NAME
- POSTGRES_SECRET_NAME
- POSTGRES_PVC_NAME

The Secret names can be confirmed by running the following command:

```bash
kubectl get secrets -n $NAMESPACE
```

### 4. Set your Kubernetes context

Make sure your shell points to the correct cluster.
The Kubeconfig file can be downloaded from the Rancher Dashboard for the cluster, then saved to your local machine.

![Download Kubeconfig from Rancher](docs/images/download-kubeconfig.png)

   ```bash
   export KUBECONFIG=/path/to/kubeconfig
   ```
- Confirm that the output from the following command matches the intended cluster:
    ```bash
    kubectl config current-context
    ```

- Confirm you can run commands in the cluster and namespace:
    ```bash
    kubectl get pods -n $NAMESPACE
    ```
---
### 5. Update Helm repositories

Add the Paidiver chart repo and ensure Helm has the latest chart information:

   ```bash
   helm repo add worms-cache https://paidiver.github.io/worms-cache
   helm repo update
   ```
### 6. Set chart version in Helmfile

Open the [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl) and ensure the `releases.version` field matches the intended chart version.

The version is derived from Git tags on the [PAIDIVER Worms Cache API](https://github.com/paidiver/worms-cache) repo,
or check the latest version by running
```bash
helm search repo -l worms-cache
```
---
### 7. Set Docker image version in Helmfile

Open the [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl) and ensure the `releases.values.api.image.tag` field matches the Docker image version you wish to deploy.

---
### 8. Preview changes
Run a dry-run diff to see what Helm will install or change:
```bash
helmfile -e {env} diff
```
---
### 9. Apply deployment
Once satisfied with the diff:
```bash
helmfile -e {env} apply
```
