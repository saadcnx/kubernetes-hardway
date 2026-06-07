# 🔩 Kubernetes CRI Hardway
### *Bypassing the API Server — Raw Container Orchestration via gRPC*

<p align="center">
  <img src="https://img.shields.io/badge/Kubernetes-CRI-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white"/>
  <img src="https://img.shields.io/badge/containerd-Runtime-gray?style=for-the-badge&logo=containerd&logoColor=white"/>
  <img src="https://img.shields.io/badge/crictl-gRPC-blue?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Minikube-orange?style=for-the-badge&logo=kubernetes"/>
  <img src="https://img.shields.io/badge/Level-Advanced-red?style=for-the-badge"/>
</p>

> **Scenario:** The Kubernetes API Server is completely down. An emergency container must be deployed *right now*. `kubectl` is useless. Static pod manifests won't work. What do you do?
>
> **Answer:** Go one level deeper — talk directly to the container runtime.

---

## 📌 What This Project Demonstrates

This simulates a **catastrophic Kubernetes control plane failure** and documents how to manually orchestrate a running Pod **without**:

- ❌ `kubectl`
- ❌ API Server
- ❌ Kubelet scheduling
- ❌ Static Pod manifests

By interfacing directly with `containerd` via `crictl` over **Unix domain socket gRPC calls**, we replicate exactly what the Kubelet does under the hood — exposing the raw mechanics that Kubernetes abstracts away.

---

## 🏗️ Architecture: How Pods *Actually* Work

```
┌─────────────────────────────────────────────────────┐
│                  Standard Kubernetes Flow           │
│                                                     │
│  kubectl → API Server → Scheduler → Kubelet → CRI   │
│                                            ↓        │
│                                       containerd    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│               This Lab (API Server DOWN)            │
│                                                     │
│  crictl ──────────────────────────────→ CRI         │
│  (gRPC)                                  ↓          │
│                                     containerd      │
└─────────────────────────────────────────────────────┘
```

**Pod Sandbox** = Isolated Linux namespaces (Network NS, hostname, IP, mounts)  
**Container** = Application process injected *into* an existing sandbox

---

## 🚀 Lab Walkthrough

### Phase 1 — Spin Up the Environment

```bash
# Create an isolated Minikube node with containerd runtime
minikube delete -p cri-lab
minikube start -p cri-lab --driver=docker --container-runtime=containerd --cni=bridge

# SSH into the node
minikube ssh -p cri-lab
```

### Phase 2 — Configure the CRI Interface

```bash
# Verify the containerd socket exists
sudo ls -l /run/containerd/containerd.sock

# Point crictl to the correct gRPC endpoints
sudo tee /etc/crictl.yaml >/dev/null <<'EOF'
runtime-endpoint: unix:///run/containerd/containerd.sock
image-endpoint:   unix:///run/containerd/containerd.sock
timeout: 10
debug:   false
EOF

# Verify the interface
sudo crictl version

# Pull the emergency application image
sudo crictl pull docker.io/library/nginx:alpine
```

### Phase 3 — Stop Kubelet (Prevent Garbage Collection)

```bash
# Kubelet will SIGKILL any sandbox it doesn't recognize
# We must stop it before manual orchestration
sudo systemctl stop kubelet
```

### Phase 4 — Create the Pod Sandbox

```bash
mkdir -p ~/cri-hardway && cd ~/cri-hardway
sudo mkdir -p /tmp/cri-hardway-logs

cat > sandbox.json <<'EOF'
{
  "metadata": {
    "name":      "hardway-sandbox",
    "namespace": "default",
    "uid":       "cri-hardway-001",
    "attempt":   2
  },
  "hostname":      "hardway-sandbox",
  "log_directory": "/tmp/cri-hardway-logs",
  "linux": {
    "cgroup_parent": "machine.slice"
  }
}
EOF

# Execute the gRPC RunPodSandbox call
SANDBOX_ID=$(sudo crictl runp sandbox.json)
echo "✅ Sandbox Created: $SANDBOX_ID"

# Verify sandbox is Ready
sudo crictl pods --name hardway-sandbox
```

### Phase 5 — Inject the Application Container

```bash
cat > container.json <<'EOF'
{
  "metadata": {
    "name":    "emergency-app",
    "attempt": 1
  },
  "image": {
    "image": "docker.io/library/nginx:alpine"
  },
  "log_path": "emergency-app.log",
  "linux": {}
}
EOF

# CreateContainer → StartContainer (replicating Kubelet's exact gRPC sequence)
CONTAINER_ID=$(sudo crictl create $SANDBOX_ID container.json sandbox.json)
sudo crictl start $CONTAINER_ID
```

### Phase 6 — Validate Network Data-Path

```bash
# Confirm Running status
sudo crictl ps --name emergency-app

# Extract the sandbox IP
POD_IP=$(sudo crictl inspectp $SANDBOX_ID | grep -m1 '"ip"' | awk -F '"' '{print $4}')
echo "🌐 Sandbox IP: $POD_IP"

# Hit the endpoint
curl -I http://$POD_IP
```

**Expected output:**
```
HTTP/1.1 200 OK
Server: nginx/x.x.x
```

---

## 🛑 Real-World Troubleshooting — Engineering Hardships

Three critical infrastructure issues were encountered and resolved during this lab:

---

### Issue 1: OCI Cgroup Driver Mismatch

**Error:**
```
FATA[0000] run pod sandbox: failed to start sandbox...
expected cgroupsPath to be of format "slice:prefix:name" for systemd cgroups,
got "/k8s.io/..." instead
```
<img width="1247" height="316" alt="error_cgroup_cgroupfs_using_here_but_in_minikube_systemd_format_is_using" src="https://github.com/user-attachments/assets/5e2545fd-87ac-4f7c-8d48-aaf43c209e07" />

**Root Cause:** Minikube configures containerd with the `systemd` cgroup driver. An empty `linux: {}` in `sandbox.json` causes crictl to fall back to the `cgroupfs` path schema, which systemd rejects.



**Fix:**
```json
"linux": {
  "cgroup_parent": "machine.slice"
}

```

<img width="1142" height="353" alt="slice_method_for_systemd_cgroup_error_fixed" src="https://github.com/user-attachments/assets/4f899fd7-03e2-4cdc-b9b8-0b04ba68ab8e" />

---

### Issue 2: Kubelet Garbage Collection Loop

**Error (journalctl):**

```
RunPodSandbox ... returns sandbox id "8c5019..."
StopPodSandbox for "8c5019..."
received sandbox exit event ... exit_status:137
```

**Root Cause:** The active Kubelet monitors the `k8s.io` containerd namespace. Since this manually created sandbox has no record in the API Server's etcd, Kubelet treats it as a rogue resource and issues `SIGKILL` (exit code 137) via its garbage collection loop.

**Fix:**
```bash
sudo systemctl stop kubelet
```
<img width="1251" height="488" alt="stoped_kubelet_that_stoping_our_custom_podsandbox" src="https://github.com/user-attachments/assets/8d8d66a7-6f0e-4e14-a0a6-b76c0c2939bc" />

---

### Issue 3: gRPC Duplicate Name Reservation

**Error:**
```
FATA[0000] run pod sandbox: failed to reserve sandbox name
... is reserved for "c280df..."
```

**Root Cause:** A previous failed run left a stale metadata lock on the sandbox name in containerd's internal state store.

**Fix:** Increment the `attempt` counter in `sandbox.json`:
```json
"metadata": {
  "name":    "hardway-sandbox",
  "attempt": 2
}
```

---

## 💥 Disaster Recovery Simulation

To prove complete decoupling from the control plane:

```bash
# Kill the API Server container
APISERVER_ID=$(sudo crictl ps --name kube-apiserver -q)
sudo crictl stop $APISERVER_ID

# From your local machine — this FAILS
kubectl get nodes
# Error: connection to the server was refused

# But inside the node — our container is STILL RUNNING
sudo crictl ps
```

> ✅ The Nginx container keeps serving traffic even with a dead API Server — because execution is entirely local to the CRI layer.

---

## 🧼 Cleanup

```bash
# Inside the node
sudo crictl stop  $CONTAINER_ID
sudo crictl rm    $CONTAINER_ID
sudo crictl stopp $SANDBOX_ID
sudo crictl rmp   $SANDBOX_ID
sudo systemctl start kubelet

# On your host machine
minikube delete -p cri-lab
```

---

## 🎓 Key Takeaways

| Concept | What Was Demonstrated |
|---|---|
| **CRI Autonomy** | Container lifecycles are fully independent of the API Server |
| **Kubelet Internals** | Kubelet is a gRPC client: `RunPodSandbox → CreateContainer → StartContainer` |
| **Cgroup Driver Alignment** | `systemd` slices vs `cgroupfs` paths — a real production misconfiguration |
| **Sandbox Architecture** | A Pod is a shared Linux namespace boundary, not a container |
| **Failure Resilience** | Running workloads survive control plane crashes without interruption |

---

## 🛠️ Tech Stack

| Tool | Role |
|---|---|
| `containerd` | Low-level container runtime (OCI compliant) |
| `crictl` | CRI-compatible CLI for direct gRPC calls |
| `Minikube` | Local Kubernetes node simulation |
| `systemd` | Host cgroup management (machine.slice) |
| `Nginx:alpine` | Emergency workload container |

---

## 👤 Author

**Saad khan**  
*DevOps Engineer | Kubernetes Internals Enthusiast*


---

<p align="center">
  <i>Built during a hands-on CRI deep-dive — where the control plane dies but the containers live on.</i>
</p>
