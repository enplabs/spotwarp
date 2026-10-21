# ⚡ SpotWarp: Zero-Loss Fault-Tolerance & Checkpoint Recovery for SaladCloud

[![PyPI Version](https://img.shields.io/pypi/v/spotwarp.svg?color=blue&label=pypi&cacheSeconds=60&cb=352)](https://pypi.org/project/spotwarp/)
[![GitHub Release](https://img.shields.io/github/v/release/enplabs/spotwarp?color=orange&label=standalone%20binary&cacheSeconds=60&cb=352)](https://github.com/enplabs/spotwarp/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![SaladCloud Ready](https://img.shields.io/badge/SaladCloud-Same--Cloud_Recovery-green.svg)](https://gpu-action.com)

<div align="center">
  <img src="https://raw.githubusercontent.com/enplabs/spotwarp/main/static/spotwarp_demo.gif?v=352" alt="SpotWarp Live Failover Demo" width="100%" />
</div>

SaladCloud offers the most cost-effective distributed GPU compute in the world. However, because residential and gaming nodes can disconnect or be preempted at any moment, running multi-hour PyTorch training, LoRA fine-tuning, or stateful generative jobs without automated checkpoint protection risks losing hours of progress.

**SpotWarp** is a lightweight, 100% local client-side daemon and companion SaladCloud Container Recipe designed exclusively to keep your workloads locked and running inside **SaladCloud** (`Salad ➡️ Salad` Same-Cloud Recovery). It continuously streams incremental `/workspace` backups to your local machine over SSH (`rsync`/`scp`) and automatically restores your exact training state onto the replacement SaladCloud node the moment a reallocation occurs—with **zero S3 storage fees** and **zero cloud controller VM overhead**.

---

## 🆚 SaladCloud Workloads: Standard vs. With SpotWarp

| Feature | Standard Interruptible Container | With SpotWarp (v3.5.2) |
| :--- | :--- | :--- |
| **Workspace State on Node Preemption** | Ephemeral container storage is wiped when the host disconnects. | **Continuously backed up** to your local machine in the background before preemption happens. |
| **Node Reallocation Handling** | New Salad node starts with a clean slate (`Epoch 0`). | **100% Autopilot (`Salad ➡️ Salad`)**. Detects the replacement Salad node and restores `/workspace` automatically. |
| **External Cloud Storage Cost** | Requires paying for S3/GCS buckets and egress bandwidth. | **$0 Cloud Storage Overhead**. Syncs directly between your Salad container and your local workstation. |
| **Workload Continuation** | Manual SSH intervention required. | **Auto-Resume**. Automatically triggers your `--resume-cmd` inside the new Salad container via `nohup`. |
| **Credential Security** | Placing third-party storage keys inside remote containers. | **Zero Key Leakage**. Your `SALAD_API_KEY` and SSH private keys never leave your local machine. |

---

## 💎 Core Architecture & Features

* 🛡️ **Same-Cloud Retention (`Salad ➡️ Salad`)**: Built specifically to keep long-running AI workloads inside SaladCloud. When an edge node disconnects, SpotWarp waits for SaladCloud Container Engine (SCE) to allocate a replacement node in your container group, verifies SSH gateway readiness, and restores your workspace automatically.
* ⚡ **Continuous Delta-Sync Backup**: Runs background `rsync` (or `scp` on Windows) incremental syncs of `/workspace/` every 30 seconds while skipping files modified within the last 10 seconds to prevent torn checkpoint reads.
* 🔁 **Warm Standby (on by default)**: While SpotWarp guards a container group it keeps the group at 2 replicas, so a second node is already running when the active one is lost. In our live test (2026-10-21, one run, 5 MB checkpoint) the restore and restart took 17.1 s once the standby was running. The second replica is billed by SaladCloud like any other running replica. Turn it off with `--no-standby` (or `SPOTWARP_WARM_STANDBY=0`, or `"warm_standby": false` in `~/.spotwarp/config.json`). Without a standby, recovery waits for SaladCloud to allocate a new node, which takes minutes.
* 🔑 **Twelve-Factor Encrypted Secret Support**: Follows SaladCloud best practices by reading `LICENSE_KEY` via encrypted environment variables, with a built-in **Zero-Friction 14-Day SaladCloud Evaluation Mode** (`SALAD-TRIAL`) so developers can deploy from the Salad Portal with zero initial sign-up friction.
* 🔒 **100% Local Execution**: No third-party proxy servers or cloud controller VMs required.

---

## 🚀 Quick Start with SaladCloud

### Step 1. Deploy the Container on SaladCloud
Use the official recipe specification in [`recipes/salad/salad_recipe.json`](recipes/salad/salad_recipe.json) or deploy `ghcr.io/enplabs/spotwarp:pytorch2.1` on the SaladCloud Portal with SSH enabled and your public key attached.

### Step 2. Install the Local Guard Daemon
On your local workstation (Linux, macOS, or Windows):

```bash
pip install --upgrade spotwarp
```

Or via universal 1-liner:
```bash
# Linux / macOS
curl -fsSL https://gpu-action.com/install.sh | bash

# Windows PowerShell
irm https://gpu-action.com/install.ps1 | iex
```

### Step 3. Configure & Start Same-Cloud Protection
```bash
# Interactive 30-second setup (saves SALAD_API_KEY and SALAD_ORG locally)
spotwarp init

# Start 24/7 background guard with automatic training resume
spotwarp start -d --org <YOUR_SALAD_ORG> --container <CONTAINER_NAME> \
  --resume-cmd "python3 /workspace/train.py --resume"

# Add --no-standby to skip the second (warm standby) replica and its cost
```

### Step 4. Manage the Daemon
```bash
spotwarp status   # Check active Salad container monitoring & PID
spotwarp stop     # Stop background daemon
spotwarp config   # View local configuration
```

---

## ⚙️ How `Salad ➡️ Salad` Recovery Works

```text
[SaladCloud Node A]                   [Your Local Workstation]               [SaladCloud Node B]
 (Active Training)                       (SpotWarp Daemon)                  (Replacement Allocated)
         │                                       │                                     │
         │ ─── (1. Continuous rsync/scp) ──────> │ (Cached /workspace)                 │
         │                                       │                                     │
   [🚨 Preempted!]                               │                                     │
         ❌ ─── (2. Detected via Salad API) ────> │                                     │
                                                 │ ─── (3. Verify New Node SSH) ─────> │
                                                 │ ─── (4. Upload /workspace) ───────> │
                                                 │ ─── (5. Execute --resume-cmd) ────> [Training Resumed!]
```

1. **Continuous Backup**: SpotWarp syncs `/workspace/` from your active Salad container (`ssh_ip:ssh_port`) to `./backups/<container_name>/`.
2. **Preemption Detection**: SpotWarp polls the SaladCloud Container Engine API every 5 seconds.
3. **Replacement Verification**: As soon as SaladCloud allocates a new running instance for your container group, SpotWarp verifies SSH connectivity through the Salad gateway.
4. **Zero-Loss Restoration & Auto-Resume**: Cached checkpoints are uploaded to `/workspace/` on the new Salad node, and your `--resume-cmd` is launched automatically in the background.

---

## 📄 License
Distributed under the MIT License. All client daemon logic executes locally in user space.
