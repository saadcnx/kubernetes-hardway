# 🔐 Kubernetes Auth Hardway
### *Manual X.509 User Provisioning — From Private Key to RBAC Authorization*

<p align="center">
  <img src="https://img.shields.io/badge/Kubernetes-PKI-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white"/>
  <img src="https://img.shields.io/badge/OpenSSL-Cryptography-red?style=for-the-badge&logo=openssl&logoColor=white"/>
  <img src="https://img.shields.io/badge/RBAC-Authorization-green?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/X.509-Client%20Cert-blue?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Level-Advanced-red?style=for-the-badge"/>
</p>

> **Scenario:** A new engineer `saad-dev` needs cluster access — immediately. No `kubeadm` user commands, no automated tooling. Just raw OpenSSL cryptography, Kubernetes PKI, and manual kubeconfig assembly.
>
> **Challenge:** Prove that Kubernetes has **no internal User object** — identity comes entirely from a CA-signed X.509 certificate.

---

## 📌 What This Project Demonstrates

A complete, manual implementation of Kubernetes **human user authentication** from scratch using only:

- 🔑 OpenSSL RSA key generation
- 📄 CSR construction with embedded identity claims
- ✍️ Kubernetes CA manual certificate signing
- ⚙️ kubeconfig assembly via `kubectl config`
- 🛡️ RBAC Role + RoleBinding for group-based authorization

---

## 🏗️ The Full Authentication Flow

```
openssl genrsa          →  saad-dev.key        (Private Key)
         ↓
openssl req -new        →  saad-dev.csr        (Certificate Signing Request)
  CN = saad-dev                                  Username claim
  O  = developer-group                           Group claim
         ↓
openssl x509 -req       →  saad-dev.crt        (Signed by Kubernetes CA)
  -CA ~/.minikube/ca.crt
  -CAkey ~/.minikube/ca.key
         ↓
kubectl config          →  saad-dev.kubeconfig (Identity Bundle)
         ↓
kubectl --kubeconfig    →  API Server
         ↓
   [CA Verification]
   CN → Username: saad-dev
   O  → Group:    developer-group
         ↓
   [RBAC Check]
   Role: developer-pod-reader
   RoleBinding: → group: developer-group
         ↓
   ✅ pods listed successfully
```

> ⚡ **Key Insight:** Kubernetes stores **no User objects**. Identity is 100% derived from the certificate. `CN` becomes the username, `O` becomes the group — nothing more, nothing less.

---

## 🚀 Lab Walkthrough

### Phase 0 — Start the Cluster

```bash
minikube delete -p pki-lab

minikube start -p pki-lab \
  --driver=docker \
  --container-runtime=containerd

# Verify
kubectl config current-context   # → pki-lab
kubectl get nodes                 # → pki-lab Ready
```

---

### Phase 1 — Generate the Private Key

```bash
mkdir -p ~/k8s-hardway-user && cd ~/k8s-hardway-user

# 2048-bit RSA private key
openssl genrsa -out saad-dev.key 2048

ls -l saad-dev.key
```

> 🔒 **Production Note:** This private key is the identity proof. Never share it, never commit it to version control.

---

### Phase 2 — Build the Certificate Signing Request

```bash
openssl req -new \
  -key saad-dev.key \
  -out saad-dev.csr \
  -subj "/CN=saad-dev/O=developer-group"

# Verify the embedded identity claims
openssl req -in saad-dev.csr -noout -subject
```

**Expected:**
```
subject=CN = saad-dev, O = developer-group
```

| Field | Value | Kubernetes Meaning |
|---|---|---|
| `CN` | `saad-dev` | Username |
| `O` | `developer-group` | Group membership |

---

### Phase 3 — Sign with Kubernetes CA

```bash
# Locate Minikube's CA files
ls -l ~/.minikube/ca.crt ~/.minikube/ca.key

# Sign the CSR (valid for 30 days)
openssl x509 -req \
  -in saad-dev.csr \
  -CA ~/.minikube/ca.crt \
  -CAkey ~/.minikube/ca.key \
  -CAcreateserial \
  -out saad-dev.crt \
  -days 30 \
  -sha256

# Inspect the signed certificate
openssl x509 -in saad-dev.crt -noout -subject -issuer -dates
```

**Expected:**
```
subject=CN = saad-dev, O = developer-group
issuer=CN = minikubeCA
notBefore=...
notAfter=... (30 days later)
```

> ⚠️ **Production Warning:** In real clusters, never directly access `ca.key`. Use the Kubernetes CSR API (`certificates.k8s.io`) or an external CA process instead.

---

### Phase 4 — Assemble the kubeconfig

```bash
# Extract current cluster info
CLUSTER_NAME=$(kubectl config view --minify -o jsonpath='{.clusters[0].name}')
SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')

# Set cluster entry
kubectl config --kubeconfig=saad-dev.kubeconfig set-cluster $CLUSTER_NAME \
  --server=$SERVER \
  --certificate-authority=$HOME/.minikube/ca.crt \
  --embed-certs=true

# Set user credentials (embed the signed cert + private key)
kubectl config --kubeconfig=saad-dev.kubeconfig set-credentials saad-dev \
  --client-certificate=saad-dev.crt \
  --client-key=saad-dev.key \
  --embed-certs=true

# Create and activate the context
kubectl config --kubeconfig=saad-dev.kubeconfig set-context saad-dev@$CLUSTER_NAME \
  --cluster=$CLUSTER_NAME \
  --user=saad-dev \
  --namespace=default

kubectl config --kubeconfig=saad-dev.kubeconfig use-context saad-dev@$CLUSTER_NAME

# Verify the kubeconfig
kubectl config --kubeconfig=saad-dev.kubeconfig view
```

---

### Phase 5 — Test Authentication (Expect Forbidden)

```bash
# Best method — directly checks API server identity recognition
kubectl --kubeconfig=saad-dev.kubeconfig auth whoami
```

**Expected:**
```
ATTRIBUTE   VALUE
Username    saad-dev
Groups      [developer-group system:authenticated]
```

```bash
# Alternative — trigger the Forbidden error
kubectl --kubeconfig=saad-dev.kubeconfig get pods
```

**Expected:**
```
Error from server (Forbidden): pods is forbidden:
User "saad-dev" cannot list resource "pods" in API group "" in the namespace "default"
```

> ✅ **This is success.** The error says `Forbidden`, not `Unauthorized`.
>
> | Error | Meaning |
> |---|---|
> | `Unauthorized (401)` | Authentication FAILED — API server rejected the certificate |
> | `Forbidden (403)` | Authentication PASSED — API server knows who you are, RBAC denied the action |

---

### Phase 6 — Grant RBAC Access via Group

```bash
# Create a demo workload
kubectl run demo-nginx --image=nginx:alpine --restart=Never -n default

# Create a Role (read-only pod access)
kubectl create role developer-pod-reader \
  --verb=get,list,watch \
  --resource=pods \
  -n default

# Bind the Role to the GROUP (not the user directly)
kubectl create rolebinding developer-pod-reader-binding \
  --role=developer-pod-reader \
  --group=developer-group \
  -n default
```

> 💡 **Why bind to the group?** Because `O=developer-group` in the certificate is the group claim. Any future user with this group field in their certificate automatically inherits these permissions — no individual binding needed.

---

### Phase 7 — Validate Full Authorization

```bash
# Now list pods as saad-dev
kubectl --kubeconfig=saad-dev.kubeconfig get pods -n default
```

**Expected:**
```
NAME         READY   STATUS    RESTARTS   AGE
demo-nginx   1/1     Running   0          2m
```

```bash
# Granular permission check
kubectl --kubeconfig=saad-dev.kubeconfig auth can-i list pods -n default    # → yes
kubectl --kubeconfig=saad-dev.kubeconfig auth can-i delete pods -n default  # → no
kubectl --kubeconfig=saad-dev.kubeconfig auth can-i get deployments         # → no
```

---

## 🛑 Troubleshooting Guide

### `Forbidden` on first test
```
User "saad-dev" cannot list resource "pods"
```
✅ **Good.** Authentication passed. Proceed to Phase 6 (RBAC).

---

### `Unauthorized` / `certificate signed by unknown authority`
```bash
# Wrong CA embedded. Fix:
kubectl config --kubeconfig=saad-dev.kubeconfig set-cluster $CLUSTER_NAME \
  --server=$SERVER \
  --certificate-authority=$HOME/.minikube/ca.crt \
  --embed-certs=true

# Verify certificate chain
openssl x509 -in saad-dev.crt -noout -subject -issuer -dates
```

---

### `ca.key` not found
```bash
# Search all Minikube paths
find ~/.minikube -name "ca.key" -o -name "ca.crt"

# Or inside the control plane node
minikube ssh -p pki-lab
sudo find / -name "ca.key" 2>/dev/null
```

---

## 🧼 Cleanup

```bash
# Remove RBAC resources
kubectl delete rolebinding developer-pod-reader-binding -n default
kubectl delete role developer-pod-reader -n default
kubectl delete pod demo-nginx -n default --ignore-not-found

# Remove local cert files
rm -f saad-dev.key saad-dev.csr saad-dev.crt saad-dev.kubeconfig

# Destroy the cluster
minikube delete -p pki-lab
```

---

## 🎓 Interview Script

> *"I manually provisioned a Kubernetes human user using X.509 client certificate authentication — no automated tooling. I generated a 2048-bit RSA private key, built a CSR with `CN=saad-dev` and `O=developer-group`, and signed it directly against the Kubernetes cluster CA using OpenSSL. I then assembled a kubeconfig from scratch using `kubectl config` subcommands, embedding the signed certificate and private key. On first API call, the server returned `Forbidden` — which confirmed authentication succeeded but RBAC authorization was pending. I then created a `Role` with pod read permissions and a `RoleBinding` targeting the `developer-group` group, after which `saad-dev` could successfully list pods. The key insight: Kubernetes has no internal User object — identity is entirely derived from the X.509 certificate's `CN` and `O` fields."*

---

## 🎯 Key Takeaways

| Concept | Detail |
|---|---|
| **No User Objects** | Kubernetes stores no human user records in etcd |
| **CN = Username** | The certificate's Common Name becomes the API server username |
| **O = Group** | The Organization field becomes group membership |
| **401 vs 403** | Unauthorized = authn failed; Forbidden = authn passed, authz failed |
| **Group RBAC** | Bind roles to groups, not individual users — scales better |
| **CA Trust** | The API server trusts any certificate signed by its configured client CA |

---

## 🛠️ Tech Stack

| Tool | Purpose |
|---|---|
| `OpenSSL` | RSA key generation, CSR creation, certificate signing |
| `kubectl config` | Manual kubeconfig assembly |
| `Kubernetes RBAC` | Role + RoleBinding for group-based authorization |
| `Minikube` | Local cluster with accessible CA files |
| `X.509 PKI` | Authentication protocol |

---

## 👤 Author

**[Your Name]**
*Systems Engineer | Kubernetes Security Enthusiast*

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=flat&logo=linkedin)](https://linkedin.com)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat&logo=github)](https://github.com)

---

<p align="center">
  <i>Where most engineers click buttons, we sign certificates.</i>
</p>