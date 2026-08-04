# ⚡ SpotWarp: Zero-Downtime Spot GPU Failover Guard & Auto-Resumer

[![PyPI Version](https://img.shields.io/pypi/v/spotwarp.svg?color=blue&label=pypi)](https://pypi.org/project/spotwarp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Audited](https://img.shields.io/badge/Security-Zero--Key--Leakage-green.svg)](https://spotwarp.com)

**SpotWarp** is a lightweight, 100% local Python daemon that protects your AI inference & PyTorch model training workloads on cheap Spot GPUs (Vast.ai, RunPod, AWS Spot) by converting unstable, interruptible instances into highly reliable, auto-resuming, stateful infrastructure.

Save **up to 70% on GPU compute bills** without worrying about sudden evictions or data loss.

---

## 🆚 Spot GPU Eviction: Standard vs. SpotWarp

| Feature | Standard Spot Instance | With SpotWarp (v3.0) |
| :--- | :--- | :--- |
| **Eviction Consequence** | Workload dies, checkpoints are deleted, money is wasted. | **Zero Data Loss**. Local daemon migrates work instantly. |
| **Recovery Process** | Manual console log-in, search for a new GPU, manual setup. | **100% Autopilot**. Automatic rental & connection handover. |
| **Workload Continuation** | Restart training from epoch 0. | **Auto-Resume**. Script continues running via `nohup` over SSH. |
| **Security Risk** | Requires placing S3/GitHub keys on unstable rented hosts. | **Zero Key Leakage**. All API keys remain on your local machine. |

---

## 💎 Core Commercial Features

* 💸 **CFO-Approved GPU Savings**: Safely exploit cheap Spot pricing on Vast.ai and RunPod. SpotWarp gives you the reliability of a Dedicated On-Demand GPU for the price of a Spot instance.
* 🔄 **Stateful Workload Migration**: Runs high-speed `rsync` incremental backups in the background of your local client machine. When eviction strikes, it restores your workspace files to the replacement container before verification.
* 🔒 **Zero-Trust Security (100% Local)**: Your cloud provider API keys (`VAST_API_KEY`, `RUNPOD_API_KEY`) stay on your local PC. Rented containers never see your cloud credentials.
* 📦 **Zero-Configuration**: No need to install daemons, cron jobs, or synchronization tools inside the remote container. If `rsync` is missing on Windows, SpotWarp automatically installs a portable binary in 1 second.
* ⚡ **Training Auto-Resumer**: Automatically restarts your training scripts (`--resume-cmd`) in the background of the new container, pointing directly to your restored training checkpoints.

---

## 🚀 Quick Start in 2 Minutes

### 1. Installation (Local PC)
Install the official package via Pip:
```bash
pip install spotwarp
```

### 2. Export API Key & Set Up Local Environment
Set your Vast.ai API key on your local machine:
```bash
# On Linux/macOS
export VAST_API_KEY="your_vast_api_key"

# On Windows (PowerShell)
$env:VAST_API_KEY="your_vast_api_key"
```

### 3. Start the Guard (With Auto-Sync & Training Resume)
Run the guard daemon on your local PC. Point it to your license key and define how your training should resume:
```bash
spotwarp start --license-key YOUR_SPOTWARP_KEY --resume-cmd "python /workspace/train.py --resume"
```

---

## ⚙️ How It Works (The Warping Cycle)

```text
[Rented GPU Host]                     [Local PC (Client)]                    [New GPU Host]
  (Active Workload)
         │                                     │                                    │
         │ ─── (30s Sync: rsync delta) ──────> │ (Cached Workspace)                 │
         │                                     │                                    │
    [🚨 Evicted!]                              │                                    │
         ❌ ─── (API Eviction Warning) ──────> │                                    │
                                               │ ─── (Rent Alternative GPU) ──────> │
                                               │                                    │
                                               │ ─── (Rsync Restore Workspace) ───> │
                                               │                                    │
                                               │ ─── (Nohup Resume Command) ──────> [Run Workload]
                                                                                      (Continuing!)
```

1. **Eviction Detection**: SpotWarp polls the cloud API every 10 seconds. If an eviction warning is triggered, it executes a *Final Gasp Sync* to save the latest files.
2. **Alternative Host Search**: SpotWarp scans the marketplace for the cheapest matching GPU (e.g. RTX 3090) on a *different* host machine and rents it instantly.
3. **Delta Sync Restoration**: SpotWarp transfers the cached workspace folder to the new container.
4. **Nohup Handover**: SpotWarp connects via SSH to trigger the `--resume-cmd` in the background and verifies the Jupyter API connection.

---

## 📄 License & Security Audits
SpotWarp is distributed under the MIT License. The code executes 100% locally in user space on your local computer, ensuring full transparency and compliance.
