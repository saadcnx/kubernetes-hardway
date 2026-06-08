# 🔒 Kubernetes Webhook Hardway
### *Building a Real Validating Admission Webhook from Scratch — Python, TLS, RBAC, and Compliance Enforcement*

<p align="center">
  <img src="https://img.shields.io/badge/Kubernetes-Admission%20Webhook-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white"/>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/TLS-mTLS%20%2B%20CA-green?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Policy-Compliance%20Enforcement-red?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Level-Advanced-red?style=for-the-badge"/>
</p>

> **Scenario:** Enterprise policy mandates that no Pod in `production` can use a `:latest` image tag or run without a CPU limit. Kubernetes by default allows both. Your job: build a **real dynamic blocking engine** using the Kubernetes Admission Webhook architecture — from TLS certificates to policy logic to live enforcement.

---

## 📌 What This Project Demonstrates

- 🏗️ How the Kubernetes **Admission Controller** pipeline works internally
- 🐍 Writing a **production-grade Python webhook server** with TLS
- 🔐 Generating a **custom CA + SAN certificate** for webhook HTTPS
- 📋 Registering a **`ValidatingWebhookConfiguration`** against the API Server
- 🚫 Enforcing **compliance policies** (image tag pinning + CPU limits)
- 🧪 Validating with real deny/allow test cases
- 💣 Testing **`failurePolicy: Fail`** — what happens when the webhook goes down
- 🌐 Understanding **namespace scoping** via `namespaceSelector`

---

## 🏗️ Architecture: How Admission Webhooks Work

```
kubectl apply -f pod.yaml
        │
        ▼
  API Server receives request
        │
        ▼
  ┌─────────────────────────────┐
  │  ValidatingWebhookConfiguration │
  │  namespaceSelector: production  │
  │  rules: pods CREATE/UPDATE      │
  └─────────────────────────────┘
        │ matches? yes
        ▼
  HTTPS POST → policy-checker-svc.security-system.svc/validate-pods
        │
        ▼
  ┌─────────────────────────────────────┐
  │  Python Webhook Server              │
  │                                     │
  │  Parse AdmissionReview JSON         │
  │  ├── Check image tag (latest?)      │
  │  └── Check resources.limits.cpu    │
  │                                     │
  │  violations found?                  │
  │  ├── YES → allowed: false, 403      │
  │  └── NO  → allowed: true            │
  └─────────────────────────────────────┘
        │
        ▼
  API Server enforces decision
  ├── allowed: true  → Pod created ✅
  └── allowed: false → Error from server (Forbidden) ❌
```

### Key Protocol Detail

```
HTTP transport:  always 200 OK  (webhook responded successfully)
AdmissionReview: allowed: false  (the actual policy decision)
                 status.code: 403
```

> The webhook speaks HTTP 200 to the API server. The **rejection** lives inside the JSON body — not the HTTP status code.

---

## 📁 Repository Structure

```
kubernetes-webhook-hardway/
│
├── README.md                        ← You are here
├── setup.sh                         ← One-command full lab setup
├── cleanup.sh                       ← Tear down everything
├── .gitignore
│
├── webhook-server/
│   ├── server.py                    ← Python webhook (policy engine)
│   └── Dockerfile                   ← Container image
│
├── manifests/
│   ├── policy-checker-deploy.yaml   ← Deployment + Service
│   └── strict-policy-webhook.yaml   ← ValidatingWebhookConfiguration
│
├── certs/
│   ├── generate-certs.sh            ← CA + TLS cert generator
│   └── .gitignore                   ← Excludes *.key, *.crt from git
│
├── test-pods/
│   ├── bad-latest-pod.yaml          ← Should be DENIED (latest tag)
│   ├── bad-no-cpu-limit.yaml        ← Should be DENIED (no CPU limit)
│   ├── bad-untagged.yaml            ← Should be DENIED (untagged = latest)
│   ├── good-pod.yaml                ← Should be ALLOWED
│   └── dev-bypass-pod.yaml          ← Should be ALLOWED (dev namespace)
│
└── screenshots/
    └── README.md                    ← Screenshot guide
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/your-username/kubernetes-webhook-hardway
cd kubernetes-webhook-hardway
bash setup.sh
```

Then test:
```bash
kubectl apply -f test-pods/bad-latest-pod.yaml    # ❌ DENIED
kubectl apply -f test-pods/good-pod.yaml          # ✅ ALLOWED
```

---

## 🚀 Manual Lab Walkthrough

### Phase 0 — Start Minikube

```bash
minikube delete -p admission-lab
minikube start -p admission-lab \
  --driver=docker \
  --container-runtime=containerd

kubectl get nodes
```

---

### Phase 1 — Create Namespaces + Label

```bash
kubectl create namespace security-system
kubectl create namespace production
kubectl create namespace dev

# Webhook watches only namespaces with this label
kubectl label namespace production environment=production

kubectl get ns --show-labels
```

> **Why the label matters:** The `ValidatingWebhookConfiguration` uses `namespaceSelector: matchLabels: environment: production`. Without this label, the webhook ignores the namespace entirely.

---

### Phase 2 — Generate TLS Certificates

```bash
bash certs/generate-certs.sh
```

**What this creates:**

| File | Purpose |
|---|---|
| `ca.key` | CA private key (never commit) |
| `ca.crt` | CA certificate (embedded in webhook config as `caBundle`) |
| `tls.key` | Webhook server private key (never commit) |
| `tls.crt` | Webhook server certificate (signed by our CA) |

```bash
# Verify SAN entries
openssl x509 -in certs/tls.crt -noout -text | grep -A4 "Subject Alternative Name"
```

**Expected:**
```
DNS:policy-checker-svc
DNS:policy-checker-svc.security-system
DNS:policy-checker-svc.security-system.svc
DNS:policy-checker-svc.security-system.svc.cluster.local
```

> SAN (Subject Alternative Name) is required. The API Server calls the webhook via its Kubernetes DNS name — the certificate must cover all those DNS forms.

---

### Phase 3 — Build the Webhook Docker Image

```bash
# Point Docker to Minikube's daemon (image stays inside the cluster)
eval $(minikube -p admission-lab docker-env)

docker build -t policy-checker:v1 ./webhook-server/
docker images | grep policy-checker
```

---

### Phase 4 — Create TLS Secret

```bash
kubectl create secret tls policy-webhook-tls \
  --cert=certs/tls.crt \
  --key=certs/tls.key \
  -n security-system

kubectl get secret policy-webhook-tls -n security-system
```

---

### Phase 5 — Deploy the Webhook Server

```bash
kubectl apply -f manifests/policy-checker-deploy.yaml
kubectl rollout status deployment/policy-checker -n security-system
kubectl get pods,svc -n security-system

# Watch live logs
kubectl logs -n security-system deploy/policy-checker
```

**Expected:**
```
Policy webhook listening on HTTPS :8443
```

---

### Phase 6 — Register the Webhook

```bash
# Embed the CA cert as base64 — API server uses this to verify webhook TLS
CA_BUNDLE=$(base64 -w0 certs/ca.crt 2>/dev/null || base64 certs/ca.crt | tr -d '\n')
export CA_BUNDLE

envsubst < manifests/strict-policy-webhook.yaml | kubectl apply -f -

kubectl describe validatingwebhookconfiguration strict-policy-webhook
```

---

### Phase 7 — Test: DENY Cases

#### Bad: `:latest` tag
```bash
kubectl apply -f test-pods/bad-latest-pod.yaml
```
```
Error from server (Forbidden): admission webhook "policy.saad.dev" denied the request:
Compliance Lockdown failed: container 'nginx' uses forbidden latest/missing tag: 'nginx:latest'
```

#### Bad: Missing CPU limit
```bash
kubectl apply -f test-pods/bad-no-cpu-limit.yaml
```
```
Error from server (Forbidden):
Compliance Lockdown failed: container 'nginx' is missing resources.limits.cpu
```

#### Bad: Untagged image
```bash
kubectl apply -f test-pods/bad-untagged.yaml
```
```
Error from server (Forbidden):
Compliance Lockdown failed: container 'nginx' uses forbidden latest/missing tag: 'nginx'
```

---

### Phase 8 — Test: ALLOW Case

```bash
kubectl apply -f test-pods/good-pod.yaml
```
```
pod/good-nginx created
```

```bash
kubectl get pods -n production
kubectl logs -n security-system deploy/policy-checker
# → [ALLOW] Pod passed compliance policy
```

---

### Phase 9 — Test: Namespace Bypass (dev)

```bash
kubectl apply -f test-pods/dev-bypass-pod.yaml
```
```
pod/dev-bad-latest created
```

> The `dev` namespace has no `environment=production` label — the webhook's `namespaceSelector` skips it entirely. This proves the policy boundary works correctly.

---

### Phase 10 — Test: UPDATE Operation

```bash
# Try updating good pod to use latest image
kubectl set image pod/good-nginx nginx=nginx:latest -n production
```
```
Error from server (Forbidden):
Compliance Lockdown failed: container 'nginx' uses forbidden latest/missing tag: 'nginx:latest'
```

> Webhook rules include `operations: ["CREATE", "UPDATE"]` — both are intercepted.

---

### Phase 11 — Test: `failurePolicy: Fail` (Strict Secure Mode)

```bash
# Scale webhook to zero (simulate it going down)
kubectl scale deployment policy-checker -n security-system --replicas=0

# Try creating a perfectly valid pod
kubectl apply -f test-pods/good-pod.yaml
```
```
Error from server (InternalError): failed calling webhook "policy.saad.dev":
Post "https://...": dial tcp: connection refused
```

> **This is by design.** `failurePolicy: Fail` means if the webhook is unreachable, **all requests to that resource are rejected**. The cluster fails closed — security over availability. The alternative `failurePolicy: Ignore` would silently allow everything when webhook is down.

```bash
# Restore the webhook
kubectl scale deployment policy-checker -n security-system --replicas=1
kubectl rollout status deployment/policy-checker -n security-system
```

---

## 🛑 Troubleshooting

### 404 on `/validate-pods`
**Root cause:** Kubernetes API Server appends `?timeout=3s` to the webhook path. Strict `==` path matching fails.
```python
# Wrong
if self.path != "/validate-pods":

# Correct
if not self.path.startswith("/validate-pods"):
```

### `x509: certificate signed by unknown authority`
The `caBundle` in the webhook config doesn't match the CA that signed `tls.crt`.
```bash
# Regenerate and re-apply
bash certs/generate-certs.sh
CA_BUNDLE=$(base64 -w0 certs/ca.crt) envsubst < manifests/strict-policy-webhook.yaml | kubectl apply -f -
```

### Webhook pod not Ready
```bash
kubectl describe pod -n security-system -l app=policy-checker
kubectl logs -n security-system deploy/policy-checker
# Check: is TLS secret mounted? Is port 8443 reachable?
```

---

## 🧼 Cleanup

```bash
bash cleanup.sh
```

Or manually:
```bash
kubectl delete validatingwebhookconfiguration strict-policy-webhook
kubectl delete namespace production dev security-system
minikube delete -p admission-lab
```

---

## 🎓 Interview Script

> *"I built a Kubernetes Validating Admission Webhook from scratch in Python. The webhook server listened on HTTPS:8443, secured with a custom CA and SAN certificate. I registered a `ValidatingWebhookConfiguration` that intercepted Pod CREATE and UPDATE operations only in namespaces labeled `environment=production`. When the API server sent an `AdmissionReview` JSON payload, my server parsed the Pod spec and enforced two rules: no `:latest` or untagged images, and every container must have `resources.limits.cpu`. Violations returned HTTP 200 with `allowed: false` and `status.code: 403` inside the response body — because the HTTP status is the transport result, not the policy decision. I configured `failurePolicy: Fail` so the cluster fails closed if the webhook is unreachable, and validated namespace scoping by proving the `dev` namespace bypassed the policy entirely."*

---

## 🎯 Key Takeaways

| Concept | Detail |
|---|---|
| **Admission Controller** | Intercepts API requests before persistence — last defense before etcd |
| **ValidatingWebhookConfiguration** | Cluster-level resource that registers webhook rules with the API server |
| **HTTP 200 vs allowed:false** | Transport and policy are separate — always return 200, deny in body |
| **caBundle** | API server verifies webhook TLS using the embedded CA certificate |
| **SAN required** | Webhook cert must cover all K8s DNS forms of the service name |
| **namespaceSelector** | Limits webhook scope — namespace label controls who gets intercepted |
| **failurePolicy: Fail** | Webhook down = all requests rejected (fail closed = secure default) |
| **startswith vs ==** | API server adds `?timeout=3s` — strict path match breaks the webhook |

---

## 🔗 Related Labs (Kubernetes Hardway Series)

| Lab | Topic |
|---|---|
| [kubernetes-cri-hardway](https://github.com/your-username/kubernetes-cri-hardway) | Bypassing API Server via raw CRI gRPC |
| [kubernetes-auth-hardway](https://github.com/your-username/kubernetes-auth-hardway) | X.509 user provisioning & authentication |
| [kubernetes-rbac-hardway](https://github.com/your-username/kubernetes-rbac-hardway) | Hand-crafted RBAC authorization |
| **kubernetes-webhook-hardway** ← *You are here* | Validating Admission Webhook from scratch |

---

## 🛠️ Tech Stack

| Tool | Purpose |
|---|---|
| `Python 3.12` | Webhook HTTP server (stdlib only, no frameworks) |
| `OpenSSL` | CA + SAN TLS certificate generation |
| `containerd` | Container runtime |
| `Minikube` | Local Kubernetes cluster |
| `ValidatingWebhookConfiguration` | Admission webhook registration |
| `kubectl` | Cluster management and testing |

---

## 👤 Author

**Saad khan**
*DevOps Engineer | Kubernetes Security Enthusiast*

---

<p align="center">
  <i>Real security is not configured — it is enforced. At admission time.</i>
</p>