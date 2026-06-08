# ⚙️ kubernetes-ApiServer-Hardway
### *Learning Kubernetes Internals the Hard Way — No Shortcuts, No Abstractions*

<p align="center">
  <img src="https://img.shields.io/badge/Kubernetes-Internals-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white"/>
  <img src="https://img.shields.io/badge/Labs-4%20Projects-orange?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Level-Advanced-red?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Hands--On-100%25-green?style=for-the-badge"/>
</p>

> Most engineers use Kubernetes. Few understand what happens underneath.
>
> This series tears open every layer — from raw container runtime gRPC calls, to manual PKI cryptography, to hand-written RBAC policies, to building a real admission webhook from scratch. No `kubeadm` shortcuts. No UI. No automation helpers. Just the internals, exposed.

---

## 📂 What's Inside This Repo

This repository contains **4 hands-on labs**, each targeting a different layer of the Kubernetes control plane:

---

### 1. 🔩 [kubernetes-cri-hardway](./kubernetes-cri-hardway)
**Bypassing the API Server with crictl**

> The API Server is completely down. A container must be deployed right now.

- Spin up a Pod Sandbox directly via **CRI gRPC calls** using `crictl`
- Replicate exactly what kubelet does under the hood: `RunPodSandbox → CreateContainer → StartContainer`
- Debug real production errors: cgroup driver mismatch, kubelet garbage collection loop, duplicate name reservation
- Prove that **running containers survive a dead API Server**

**Key skills:** `containerd` · `crictl` · `cgroup systemd` · `CRI gRPC` · `Pod Sandbox`

---

### 2. 🔐 [kubernetes-auth-hardway](./kubernetes-auth-hardway)
**Manual X.509 User Provisioning — From Private Key to kubeconfig**

> A new engineer needs cluster access immediately. No `kubeadm`. No tooling. Just OpenSSL.

- Generate a **2048-bit RSA private key** and build a CSR with identity claims (`CN=saad-dev`, `O=developer-group`)
- Sign the certificate against the **Kubernetes cluster CA** manually
- Assemble a **kubeconfig from scratch** using `kubectl config` subcommands
- Prove authentication by triggering the `Forbidden (403)` response — not `Unauthorized (401)`

**Key skills:** `OpenSSL` · `X.509 PKI` · `kubeconfig` · `CN/O fields` · `API Server auth`

---

### 3. 🛡️ [kubernetes-rbac-hardway](./kubernetes-rbac-hardway)
**Hand-Crafted Security Policy — Pure YAML, Zero Automation**

> Grant `saad` read-only pod access in `production` — nothing more, nothing less.

- Write `Role` and `RoleBinding` YAML manifests **by hand**
- Enforce **namespace-scoped permission boundaries**
- Bind RBAC to X.509 certificate identity (`CN` = username, `O` = group)
- Validate with `kubectl auth can-i` impersonation — prove both what's **allowed** and what's **denied**

**Key skills:** `Role` · `RoleBinding` · `namespaceSelector` · `kubectl auth can-i` · `group binding`

---

### 4. 🔒 [kubernetes-webhook-hardway](./kubernetes-webhook-hardway)
**Building a Real Validating Admission Webhook from Scratch**

> Block every Pod in `production` that uses `:latest` or has no CPU limit — dynamically, at admission time.

- Write a **production-grade Python webhook server** (no frameworks, stdlib only)
- Generate a **custom CA + SAN TLS certificate** for HTTPS
- Register a `ValidatingWebhookConfiguration` against the API Server
- Handle the real-world `?timeout=3s` path bug from the API Server
- Test `failurePolicy: Fail` — cluster fails **closed** when webhook goes down

**Key skills:** `AdmissionReview` · `ValidatingWebhookConfiguration` · `TLS/CA` · `failurePolicy` · `namespaceSelector`

---

## 🗺️ Series Learning Path

```
┌─────────────────────────────────────────────────────────────────┐
│                  Kubernetes Request Lifecycle                    │
│                                                                 │
│  kubectl apply                                                  │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              kube-apiserver                             │   │
│  │                                                         │   │
│  │  1. Authentication ←── Practice 2: kubernetes-auth-hardway   │   │
│  │         │                                               │   │
│  │  2. Authorization  ←── Practice 3: kubernetes-rbac-hardway   │   │
│  │         │                                               │   │
│  │  3. Admission      ←── Practice 4: kubernetes-webhook-hardway│   │
│  │         │                                               │   │
│  │  4. etcd write                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│       │                                                         │
│       ▼                                                         │
│  kubelet receives pod spec                                      │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CRI (containerd)  ←── Practice 1: kubernetes-cri-hardway    │   │
│  │  RunPodSandbox                                          │   │
│  │  CreateContainer                                        │   │
│  │  StartContainer                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

Each Practice targets a **specific layer** of this pipeline. Together they cover the full lifecycle of a Kubernetes workload from API request to running container.

---

## 🚀 Getting Started

### Prerequisites

```bash
# Required tools
minikube   >= v1.30
kubectl    >= v1.27
docker     >= v24
openssl    (any recent version)
python3    >= 3.10   # (Lab 4 only)
```

### Clone and explore

```bash
git clone https://github.com/saadcnx/kubernetes-apiserver-hardway
cd kubernetes-apiserver-hardway

# Each lab is self-contained — start with any one
ls -1
# kubernetes-cri-hardway/
# kubernetes-auth-hardway/
# kubernetes-rbac-hardway/
# kubernetes-webhook-hardway/
```

### Recommended order

If you're new to Kubernetes internals, follow this sequence:

```
practice 1 → practice 2 → practice 3 → practice 4
CRI          Auth         RBAC         Webhook
```

Lab 2 (Auth) feeds directly into Lab 3 (RBAC) — the `saad-dev` certificate created in Lab 2 is the identity used in Lab 3.

---

## 🎯 What You'll Be Able to Explain After This Series

| Question | Covered In |
|---|---|
| How does a Pod actually start at the container runtime level? | Practice 1 |
| How does Kubernetes know *who* is making an API request? | Practice 2 |
| How does Kubernetes decide *what* a user is allowed to do? | Practice 3 |
| How does Kubernetes enforce policies *before* objects are created? | Practice 4 |
| What survives a complete API Server crash? | Practice 1 |
| What is the difference between `401 Unauthorized` and `403 Forbidden`? | Practice 2 |
| Why should you bind RBAC to groups instead of individual users? | Practice 3 |
| Why does a webhook return HTTP 200 even when it's rejecting a request? | Practice 4 |

---

## 👤 Author

**Saad**
*DevOps Engineer | Kubernetes Internals Enthusiast*
---

<p align="center">
  <i>You don't truly know Kubernetes until you've broken it on purpose.</i>
</p>
