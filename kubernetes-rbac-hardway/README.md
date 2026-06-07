# 🛡️ Kubernetes RBAC Hardway
### *Hand-Crafted Security Policy — Pure YAML, Zero Automation*

<p align="center">
  <img src="https://img.shields.io/badge/Kubernetes-RBAC-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white"/>
  <img src="https://img.shields.io/badge/Authorization-Role%20%2B%20RoleBinding-green?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Namespace-Scoped-orange?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/X.509-Identity-blue?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Level-Advanced-red?style=for-the-badge"/>
</p>

> **Scenario:** User `saad` is authenticated via a manually signed X.509 certificate. Now grant them access to **only** the `production` namespace — read-only pod access, nothing more — using handwritten YAML manifests. No UI. No automation. No helpers.
>
> **This is where Authentication ends and Authorization begins.**

---

## 📌 What This Project Demonstrates

- ✍️ Writing `Role` and `RoleBinding` manifests from scratch
- 🔒 Namespace-scoped permission boundaries
- 👤 Binding RBAC to X.509 certificate identity (`CN` = username)
- 👥 Group-based binding using certificate `O` field
- 🧪 Permission validation via `kubectl auth can-i` impersonation
- ❌ Proving what is **denied** is as important as what is allowed

---

## 🏗️ RBAC Mental Model

```
Certificate (X.509)
  CN = saad          →  Username: saad
  O  = developer-group →  Group: developer-group

         ↓

Role (pod-reader) — in namespace: production
  apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]

         ↓

RoleBinding (read-pods-binding) — in namespace: production
  subject: User → saad
  roleRef:  Role → pod-reader

         ↓

Result:
  saad CAN  → list/get/watch pods in production  ✅
  saad CAN'T → delete/create pods               ❌
  saad CAN'T → access pods in default namespace  ❌
  saad CAN'T → touch any other resource          ❌
```

> **RBAC Rule:** A RoleBinding's effect is strictly limited to the namespace it lives in. Permissions never bleed across namespace boundaries.

---

## 🚀 Lab Walkthrough

### Prerequisites

This lab assumes the `saad` user identity already exists via a signed X.509 certificate from the [kubernetes-auth-hardway](https://github.com/your-username/kubernetes-auth-hardway) lab.

```
Certificate CN: saad
Certificate O:  developer-group
```

> If your CN is `saad-dev`, replace `saad` with `saad-dev` in all commands below.

---

### Phase 0 — Baseline: Confirm Zero Access

```bash
# Before any RBAC — saad has NO permissions at all
kubectl auth can-i list pods -n production --as=saad
# → no
```

This is the starting point. Every permission we grant from here is explicit and intentional.

---

### Phase 1 — Create the Production Namespace

```bash
kubectl create namespace production

# Verify
kubectl get ns production
```

**Expected:**
```
NAME         STATUS   AGE
production   Active   ...
```

---

### Phase 2 — Deploy a Test Workload

```bash
kubectl run prod-nginx \
  --image=nginx:alpine \
  --restart=Never \
  -n production

kubectl get pods -n production
```

**Expected:**
```
NAME         READY   STATUS    RESTARTS   AGE
prod-nginx   1/1     Running   0          ...
```

---

### Phase 3 — Write the Role Manifest

```bash
cat > developer-role.yaml <<'EOF'
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: production
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
EOF
```

**YAML Breakdown:**

| Field | Value | Meaning |
|---|---|---|
| `apiGroups: [""]` | Core API group | Where pods, services, configmaps live |
| `resources: ["pods"]` | pods only | No secrets, no deployments, no services |
| `verbs: ["get", "list", "watch"]` | Read-only | No create, delete, update, patch |

```bash
kubectl apply -f developer-role.yaml

# Inspect what was created
kubectl describe role pod-reader -n production
```

**Expected output (key section):**
```
Resources  Non-Resource URLs  Resource Names  Verbs
pods       []                 []              [get list watch]
```

---

### Phase 4 — Write the RoleBinding Manifest

```bash
cat > developer-binding.yaml <<'EOF'
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods-binding
  namespace: production
subjects:
- kind: User
  name: saad
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
EOF
```

**YAML Breakdown:**

| Section | Field | Meaning |
|---|---|---|
| `subjects` | `kind: User` | Binding to a human user identity |
| `subjects` | `name: saad` | Must match the certificate CN exactly |
| `roleRef` | `name: pod-reader` | The Role defined in Phase 3 |

```bash
kubectl apply -f developer-binding.yaml

# Inspect the binding
kubectl describe rolebinding read-pods-binding -n production
```

**Expected:**
```
Role:
  Kind:  Role
  Name:  pod-reader
Subjects:
  Kind  Name  Namespace
  ----  ----  ---------
  User  saad
```

---

### Phase 5 — Validate with Impersonation

```bash
# ✅ ALLOWED — reads in production
kubectl auth can-i list  pods -n production --as=saad   # → yes
kubectl auth can-i get   pods -n production --as=saad   # → yes
kubectl auth can-i watch pods -n production --as=saad   # → yes

# ❌ DENIED — write operations
kubectl auth can-i delete pods -n production --as=saad  # → no
kubectl auth can-i create pods -n production --as=saad  # → no
kubectl auth can-i patch  pods -n production --as=saad  # → no

# ❌ DENIED — different namespace (namespace boundary proof)
kubectl auth can-i list pods -n default --as=saad       # → no
kubectl auth can-i list pods -n kube-system --as=saad   # → no

# ❌ DENIED — different resources
kubectl auth can-i list services -n production --as=saad    # → no
kubectl auth can-i list secrets  -n production --as=saad    # → no
```

> `kubectl auth can-i` is the definitive RBAC auditing tool. The `--as` flag lets admins impersonate any identity to verify authorization decisions without needing that user's kubeconfig.

---

### Phase 6 — Live Test with Real Certificate

If the `saad.kubeconfig` file was created in the auth hardway lab:

```bash
# ✅ This should work
kubectl --kubeconfig=saad.kubeconfig get pods -n production
```

**Expected:**
```
NAME         READY   STATUS    RESTARTS   AGE
prod-nginx   1/1     Running   0          5m
```

```bash
# ❌ This should fail — write operation
kubectl --kubeconfig=saad.kubeconfig delete pod prod-nginx -n production
```

**Expected:**
```
Error from server (Forbidden): pods "prod-nginx" is forbidden:
User "saad" cannot delete resource "pods" in API group "" in the namespace "production"
```

```bash
# ❌ This should fail — wrong namespace
kubectl --kubeconfig=saad.kubeconfig get pods -n default
```

**Expected:**
```
Error from server (Forbidden): pods is forbidden:
User "saad" cannot list resource "pods" in API group "" in the namespace "default"
```

---

### Phase 7 (Optional) — Group-Based Binding

A more scalable production approach — bind the Role to the **group** instead of the individual user. Any user whose certificate has `O=developer-group` automatically gets access.

```bash
cat > developer-group-binding.yaml <<'EOF'
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: developer-group-read-pods-binding
  namespace: production
subjects:
- kind: Group
  name: developer-group
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
EOF

kubectl apply -f developer-group-binding.yaml

# Test group impersonation
kubectl auth can-i list pods -n production --as=saad --as-group=developer-group
# → yes
```

> **Why groups scale better:** Add a new team member by signing their certificate with `O=developer-group`. Zero RBAC changes needed — they inherit permissions automatically.

---

## 📁 Repository File Structure

```
kubernetes-rbac-hardway/
├── README.md
├── manifests/
│   ├── developer-role.yaml
│   ├── developer-binding.yaml
│   └── developer-group-binding.yaml   ← (optional, group-based)
└── .gitignore
```

---

## 🧼 Cleanup

```bash
kubectl delete rolebinding read-pods-binding -n production
kubectl delete rolebinding developer-group-read-pods-binding -n production --ignore-not-found
kubectl delete role pod-reader -n production
kubectl delete pod prod-nginx -n production --ignore-not-found
kubectl delete namespace production
```

---

## 🎓 Interview Script

> *"I manually implemented a namespace-scoped Kubernetes RBAC policy using hand-written YAML. I defined a `Role` named `pod-reader` in the `production` namespace, granting only `get`, `list`, and `watch` on pods within the core API group. I then created a `RoleBinding` connecting this Role to the user `saad` — the exact Common Name from their X.509 certificate. I validated the policy using `kubectl auth can-i` with impersonation, confirming the user could list pods in `production` but was denied delete operations and blocked from accessing any other namespace. I also demonstrated the more scalable group-based binding pattern using the certificate's `O` field."*

---

## 🎯 Key Takeaways

| Concept | Detail |
|---|---|
| **Role = Blueprint** | Defines what actions are allowed on which resources |
| **RoleBinding = Bridge** | Connects an identity (User/Group/SA) to a Role |
| **Namespace Boundary** | RoleBinding effects are strictly limited to its namespace |
| **CN = Username** | RBAC `subjects.name` must match certificate CN exactly |
| **O = Group** | Group binding scales better than per-user binding |
| **Deny by Default** | Everything not explicitly allowed is automatically denied |
| **`auth can-i`** | The gold standard for RBAC auditing and validation |

---

## 🔗 Related Labs

| Lab | Topic |
|---|---|
| [kubernetes-cri-hardway](https://github.com/your-username/kubernetes-cri-hardway) | Bypassing API Server via raw CRI gRPC |
| [kubernetes-auth-hardway](https://github.com/your-username/kubernetes-auth-hardway) | X.509 user provisioning & authentication |
| **kubernetes-rbac-hardway** ← *You are here* | Hand-crafted RBAC authorization |

---

## 🛠️ Tech Stack

| Tool | Purpose |
|---|---|
| `kubectl apply` | Declarative manifest deployment |
| `kubectl auth can-i` | RBAC permission auditing with impersonation |
| `Kubernetes RBAC` | Role-based access control engine |
| `X.509 PKI` | Identity source (CN = user, O = group) |
| `Minikube` | Local cluster environment |

---

## 👤 Author

**[Your Name]**
*Systems Engineer | Kubernetes Security Enthusiast*

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=flat&logo=linkedin)](https://linkedin.com)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat&logo=github)](https://github.com)

---

<p align="center">
  <i>In Kubernetes, trust nothing by default. Grant everything deliberately.</i>
</p>