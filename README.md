# mastodon-SRE — Deployment Guide

Follow the steps in order. Every step says what to create, what command to
run, and how to check it worked before moving to the next one. Optional
steps are marked **[OPTIONAL]** with the condition for when you need them.

All examples assume namespace `mastodon` for app components and
`traefik-system` for Traefik. Change both consistently if you use different
names.

---

## Step 0 — Cluster-wide prerequisites (once per cluster, ever)

These are NOT per-Mastodon-instance. Install once. If you're adding a
second Mastodon instance to a cluster that already has these, skip to Step 1.

### 0.1 — Edit `charts/cnpg/Chart.yaml`

Remove this block (the CNPG operator must not be tied to an app release):

```yaml
dependencies:
  - name: cloudnative-pg
    repository: https://cloudnative-pg.github.io/charts
    version: "1.30.0"
```

### 0.2 — Install the CloudNativePG operator

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm repo update
helm upgrade --install cnpg-operator cnpg/cloudnative-pg \
  -n cnpg-system --create-namespace
```

Check:
```bash
kubectl get pods -n cnpg-system
```

### 0.3 — [OPTIONAL: only if you want full-text search] Install the ECK operator

```bash
helm repo add elastic https://helm.elastic.co
helm repo update
helm upgrade --install elastic-operator elastic/eck-operator \
  -n elastic-system --create-namespace
```

Check:
```bash
kubectl get pods -n elastic-system
```

If you don't want search, skip this — `charts/eck` is never installed and
`charts/mastodon`'s `elasticsearch.enabled` stays `false`.

### 0.4 — [OPTIONAL: only if the cluster has no ingress controller yet]

You're using annotation-based `Ingress` (not HTTPRoute), which is Traefik's
default provider — no Gateway API CRDs needed. `charts/mastodon` and
`charts/fediscoverer` already default to `ingress.enabled: true`,
`httproute.enabled: false`, so nothing else to change there.

Create the Cloudflare token secret Traefik needs:
```yaml
# secrets/cloudflare-api-token.yaml
# Used by: charts/traefik -> traefik.env (CF_DNS_API_TOKEN)
# What it does: lets Traefik create the DNS TXT record Let's Encrypt needs
# for the DNS-01 challenge, so it can issue certs without exposing
# port 80/443. Token only needs Zone:DNS:Edit scope on your domain's zone.
apiVersion: v1
kind: Secret
metadata:
  name: cloudflare-api-token
  namespace: traefik-system
type: Opaque
stringData:
  api-token: CHANGE_ME_your-real-cloudflare-dns-edit-token
```
```bash
kubectl create namespace traefik-system
kubectl apply -f secrets/cloudflare-api-token.yaml
```

Install Traefik:
```bash
helm dependency build ./charts/traefik
helm install traefik ./charts/traefik -n traefik-system
```

Check:
```bash
kubectl get pods -n traefik-system
kubectl get ingressclass
```

**If your cluster already runs an ingress controller (e.g. k3s ships
Traefik by default), skip this entirely** and instead point
`charts/mastodon`/`charts/fediscoverer`'s `ingress.className` (or
`httproute.parentRefs`) at whatever already exists.

---

## Step 1 — Redis (`charts/redis-ha`)

Create the secret:
```yaml
# secrets/mastodon-redis-app-creds.yaml
# Used by: charts/redis-ha -> redisHA.existingSecret (key "auth")
#          charts/mastodon -> redis.existingSecret (key "password" by default)
# What it does: Sentinel/Redis AUTH password for the whole HA group. Both
# keys hold the same value so you don't have to edit charts/mastodon's
# default existingSecretKeys.password.
apiVersion: v1
kind: Secret
metadata:
  name: mastodon-redis-app-creds
  namespace: mastodon
type: Opaque
stringData:
  auth: CHANGE_ME_your-real-redis-password
  password: CHANGE_ME_your-real-redis-password
```
```bash
kubectl create namespace mastodon
kubectl apply -f secrets/mastodon-redis-app-creds.yaml
```

Install:
```bash
helm repo add dandy https://dandydeveloper.github.io/charts
helm dependency build ./charts/redis-ha
helm install mastodon-redis-ha ./charts/redis-ha -n mastodon
```

Check:
```bash
kubectl get pods -n mastodon -l app=redis-ha
```
All replicas should reach `Running`/`Ready`. Note down the Sentinel master
group name used — the chart default is `mastodon-app` — you'll need it in
Step 4.

---

## Step 2 — Postgres (`charts/cnpg`)

Create the app DB secret:
```yaml
# secrets/mastodon-pg-app-creds.yaml
# Used by: charts/cnpg -> cluster.bootstrap.existingSecret
#          charts/mastodon -> postgresql.existingSecret
# What it does: CNPG provisions the Postgres role "mastodon" with this
# password at cluster bootstrap. Mastodon then connects using the same
# secret. Changing this later requires changing the password in Postgres
# too — this only sets the INITIAL password.
apiVersion: v1
kind: Secret
metadata:
  name: mastodon-pg-app-creds
  namespace: mastodon
type: kubernetes.io/basic-auth
stringData:
  username: mastodon
  password: CHANGE_ME_your-real-pg-app-password
```

**[OPTIONAL: only if you want fediscoverer]** create its DB secret too:
```yaml
# secrets/fediscoverer-pg-creds.yaml
# Used by: charts/cnpg -> fediscoverer.existingSecret (creates this role +
#          databases fediscoverer_production / _cache / _queue)
#          charts/fediscoverer -> config.database.password.secretKeyRef
#          (name must be exactly this — see Step 6 edit)
# What it does: same pattern as mastodon-pg-app-creds, for the
# fediscoverer app. Username must stay exactly "fediscoverer" — the app
# code requires it.
apiVersion: v1
kind: Secret
metadata:
  name: fediscoverer-pg-creds
  namespace: mastodon
type: kubernetes.io/basic-auth
stringData:
  username: fediscoverer
  password: CHANGE_ME_your-real-fediscoverer-pg-password
```
If you don't want fediscoverer, set `fediscoverer.enabled: false` in
`charts/cnpg/values.yaml` and skip this secret.

Backup is `enabled: true` by default in `charts/cnpg/values.yaml`. **Either**
create the backup secret, **or** set `backup.enabled: false` before install.

```yaml
# secrets/mastodon-pg-backup-creds.yaml
# Used by: charts/cnpg -> backup.existingSecret (provider: s3 by default)
# What it does: WAL archiving + scheduled base backups authenticate to your
# S3-compatible bucket with these. If missing/wrong, the Cluster still
# comes up — backups just silently fail. Keys shown are for provider: s3;
# switching to azure/gcs needs different key names (see
# charts/cnpg/values.yaml comments).
apiVersion: v1
kind: Secret
metadata:
  name: mastodon-pg-backup-creds
  namespace: mastodon
type: Opaque
stringData:
  ACCESS_KEY_ID: CHANGE_ME_your-real-s3-access-key
  ACCESS_SECRET_KEY: CHANGE_ME_your-real-s3-secret-key
```
Also set `backup.destinationPath` in `charts/cnpg/values.yaml` to your real
bucket path before installing.

Apply whichever secrets you created:
```bash
kubectl apply -f secrets/mastodon-pg-app-creds.yaml
kubectl apply -f secrets/fediscoverer-pg-creds.yaml        # only if using fediscoverer
kubectl apply -f secrets/mastodon-pg-backup-creds.yaml     # only if backup.enabled: true
```

Install:
```bash
helm install mastodon-postgresql ./charts/cnpg -n mastodon
```

Check:
```bash
kubectl get cluster -n mastodon
kubectl get pooler -n mastodon
```
Wait for the `Cluster` status to show `Cluster in healthy state` before
continuing.

---

## Step 3 — [OPTIONAL: only if you enabled search in Step 0.3] Elasticsearch (`charts/eck`)

No secret needed — the ECK operator manages its own internal auth/certs.

```bash
helm dependency build ./charts/eck
helm install mastodon-elasticsearch ./charts/eck -n mastodon
```

Check:
```bash
kubectl get elasticsearch -n mastodon
kubectl get pods -n mastodon -l elasticsearch.k8s.elastic.co/cluster-name=mastodon-es
```

This cluster serves TLS with a self-signed cert. In Step 4, either point
`elasticsearch.caSecret` at it or disable TLS consistently on both sides.

If you skipped search, skip this step — leave `elasticsearch.enabled: false`
in Step 4.

---

## Step 4 — Mastodon (`charts/mastodon`)

Create the app secrets:
```yaml
# secrets/mastodon-app-secrets.yaml
# Used by: charts/mastodon -> mastodon.secrets.existingSecret
# What it does: Rails session signing, VAPID push keys, and Active Record
# Encryption keys. Generated ONCE per instance and must never change after
# real user data exists — doing so breaks existing sessions and makes
# encrypted DB columns unreadable.
# Generate real values (run once, before first install, inside the
# mastodon image):
#   bin/rails db:encryption:init                    -> the three are-* keys
#   bin/rails secret                                 -> secret-key-base
#   bin/rails mastodon:webpush:generate_vapid_key    -> vapid pair
apiVersion: v1
kind: Secret
metadata:
  name: mastodon-app-secrets
  namespace: mastodon
type: Opaque
stringData:
  secret-key-base: CHANGE_ME_real_64char_secret_key_base
  vapid-private-key: CHANGE_ME_real_vapid_private_key
  vapid-public-key: CHANGE_ME_real_vapid_public_key
  are-primary-key: CHANGE_ME_real_are_primary_key
  are-deterministic-key: CHANGE_ME_real_are_deterministic_key
  are-derivation-salt: CHANGE_ME_real_are_derivation_salt
```

**Choose storage: S3 (recommended) or PVC**

**[OPTION A — S3]**, create:
```yaml
# secrets/mastodon-s3-creds.yaml
# Used by: charts/mastodon -> mastodon.s3.existingSecret
# What it does: web/sidekiq pods read/write media uploads (avatars,
# attachments, custom emoji) directly to this bucket.
apiVersion: v1
kind: Secret
metadata:
  name: mastodon-s3-creds
  namespace: mastodon
type: Opaque
stringData:
  access-key-id: CHANGE_ME_real_s3_access_key_id
  secret-access-key: CHANGE_ME_real_s3_secret_access_key
```
and set in values: `s3.enabled: true`, `s3.hostname`, `s3.bucket`,
`s3.region`, `s3.existingSecret: mastodon-s3-creds`.

**[OPTION B — PVC]**, skip the secret above and instead set
`pvc.enabled: true` — but first confirm your StorageClass supports
`ReadWriteMany` (most cloud block storage does not; this option fails
silently as pods stuck in `Pending` otherwise).

Apply secrets:
```bash
kubectl apply -f secrets/mastodon-app-secrets.yaml
kubectl apply -f secrets/mastodon-s3-creds.yaml   # only if using S3
```

Set these values before install (put in a `values-mastodon.yaml`):
```yaml
mastodon:
  localDomain: mastodon.yourdomain.tld
  secrets:
    existingSecret: mastodon-app-secrets

postgresql:
  hostname: mastodon-postgresql-pooler-rw   # cnpg pooler service from Step 2
  port: 5432
  database: mastodon
  existingSecret: mastodon-pg-app-creds

redis:
  mode: sentinel
  sentinels: "mastodon-redis-ha-announce-0,mastodon-redis-ha-announce-1,mastodon-redis-ha-announce-2"  # verify actual service names from Step 1
  masterGroup: mastodon-app
  existingSecret: mastodon-redis-app-creds

# [OPTIONAL: only if you did Step 3]
elasticsearch:
  enabled: true
  hostname: mastodon-es-es-http.mastodon.svc
  port: 9200
```

Install:
```bash
helm install mastodon ./charts/mastodon -n mastodon -f values-mastodon.yaml
```

Check:
```bash
kubectl get pods -n mastodon
kubectl get jobs -n mastodon    # dbPrepare / dbMigrate must be Complete
```

If you enabled search for the first time, also run once (expensive — see
warning in `charts/mastodon/values.yaml`):
```bash
helm upgrade mastodon ./charts/mastodon -n mastodon -f values-mastodon.yaml \
  --set mastodon.hooks.deploySearch.enabled=true
```

---

## Step 5 — [OPTIONAL: only if you want fediscoverer] `charts/fediscoverer`

### 5.1 — Edit `charts/fediscoverer/values.yaml`

Change:
```yaml
    secretKeyRef:
      name: postgresql-auth
```
to:
```yaml
    secretKeyRef:
      name: fediscoverer-pg-creds
```
(This must match the secret name `charts/cnpg` actually created in Step 2.)

### 5.2 — Create its app secret

```yaml
# secrets/fediscoverer-app-secrets.yaml
# Used by: charts/fediscoverer -> config.existingSecret
# What it does: fediscoverer's own Rails session signing key — separate
# app from Mastodon, shares only the Postgres cluster.
apiVersion: v1
kind: Secret
metadata:
  name: fediscoverer-app-secrets
  namespace: mastodon
type: Opaque
stringData:
  secret-key-base: CHANGE_ME_real_64char_fediscoverer_secret_key_base
```
```bash
kubectl apply -f secrets/fediscoverer-app-secrets.yaml
```

### 5.3 — Set values and install

```yaml
config:
  domain: fediscoverer.yourdomain.tld
  existingSecret: fediscoverer-app-secrets
  database:
    host: mastodon-postgresql-pooler-rw
    port: 5432
```
```bash
helm install fediscoverer ./charts/fediscoverer -n mastodon -f values-fediscoverer.yaml
```

Check:
```bash
kubectl get pods -n mastodon -l app.kubernetes.io/name=fediscoverer
kubectl get jobs -n mastodon    # db-migrate must be Complete
```

---

## Full verification

```bash
kubectl get pods -A -n mastodon
kubectl get pods -n traefik-system   # if you installed Traefik
kubectl get cluster,pooler -n mastodon
kubectl get elasticsearch -n mastodon   # if search enabled
```

Visit `https://mastodon.yourdomain.tld` — you should reach the Mastodon
landing page. If you enabled `createAdmin`, retrieve the generated password
from the job logs:
```bash
kubectl logs -n mastodon job/<create-admin-job-name>
```
