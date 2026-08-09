# ⚡ SpotWarp: Zero-Downtime Spot GPU Failover Guard & Auto-Resumer

[![PyPI Version](https://img.shields.io/pypi/v/spotwarp.svg?color=blue&label=pypi)](https://pypi.org/project/spotwarp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Audited](https://img.shields.io/badge/Security-Zero--Key--Leakage-green.svg)](https://gpu-action.com)

**SpotWarp** is a lightweight, 100% local Python daemon that protects your AI inference & PyTorch model training workloads on cheap Spot GPUs (Vast.ai + RunPod cross-cloud) by converting unstable, interruptible instances into highly reliable, auto-resuming, stateful infrastructure.

Save **up to 70% on GPU compute bills** without worrying about sudden evictions or data loss — and when your primary cloud is temporarily out of capacity, SpotWarp bridges you to a second cloud automatically, then brings you back the moment the cheaper option reopens.

---

## 🆚 Spot GPU Eviction: Standard vs. SpotWarp

| Feature | Standard Spot Instance | With SpotWarp (v3.2) |
| :--- | :--- | :--- |
| **Eviction Consequence** | Workload dies, checkpoints are deleted, money is wasted. | **Zero Data Loss**. Local daemon migrates work instantly. |
| **Recovery Process** | Manual console log-in, search for a new GPU, manual setup. | **100% Autopilot**. Parallel candidate racing rents & verifies a replacement in under a minute. |
| **If your cloud is out of stock** | Failover fails outright — nothing to migrate to. | **Cross-Cloud Bridge**. Automatically rents on RunPod as a fallback, spot pricing first, on-demand if spot isn't offered. |
| **Paying bridge-cloud rates forever** | N/A | **Auto-Failback**. Watches for your original cloud's cheaper capacity to return and migrates you back automatically — the bridge cloud is never a permanent home. |
| **Workload Continuation** | Restart training from epoch 0. | **Auto-Resume**. Script continues running via `nohup` over SSH. |
| **Security Risk** | Requires placing S3/GitHub keys on unstable rented hosts. | **Zero Key Leakage**. All API keys remain on your local machine. |

---

## 💎 Core Commercial Features

* 💸 **CFO-Approved GPU Savings**: Safely exploit cheap Spot pricing on Vast.ai. SpotWarp gives you the reliability of a Dedicated On-Demand GPU for the price of a Spot instance.
* 🏁 **Parallel Candidate Racing**: On eviction, SpotWarp rents several replacement candidates concurrently instead of trying them one at a time — a single slow or dead host no longer adds minutes to your downtime. Typical failover: well under a minute.
* 🌐 **Cross-Cloud Fallback (Vast.ai ⇄ RunPod)**: If your primary cloud has zero matching candidates at the moment of eviction, SpotWarp automatically bridges to RunPod — spot pricing first, retrying on-demand if RunPod has no spot capacity for that GPU model — so your workload stays protected instead of failing outright.
* ↩️ **Automatic Cost-Optimizing Failback**: A bridge-cloud replacement is never left running indefinitely at the higher rate. SpotWarp keeps checking your original cloud in the background and migrates the workload back the instant a cheaper matching candidate reappears — verified end-to-end on a single live instance: rented on Vast.ai, evicted, bridged to RunPod, then automatically migrated back to Vast.ai once capacity returned.
* 🔄 **Stateful Workload Migration**: Runs high-speed `rsync`/`scp` incremental backups in the background of your local client machine. When eviction strikes, it restores your workspace files to the replacement container before verification.
* ✅ **Real Connectivity Verification**: Replacement hosts are confirmed reachable via an actual SSH handshake before they're trusted — not a proxy signal like a Jupyter API ping that can report false negatives on a perfectly healthy host.
* 🔒 **Zero-Trust Security (100% Local)**: Your cloud provider API keys (`VAST_API_KEY`, `RUNPOD_API_KEY`) stay on your local PC. Rented containers never see your cloud credentials.
* 📦 **Zero-Configuration**: No need to install daemons, cron jobs, or synchronization tools inside the remote container.
* ⚡ **Training Auto-Resumer**: Automatically restarts your training scripts (`--resume-cmd`) in the background of the new container, pointing directly to your restored training checkpoints.

---

## 🚀 Quick Start in 2 Minutes

### 1. Installation (Local PC)
Install the official package via Pip:
```bash
pip install spotwarp
```

### 2. Export API Keys & Set Up Local Environment
Set your Vast.ai API key on your local machine. Add a RunPod API key too if you want the cross-cloud bridge (optional, but recommended — it's what keeps a bad-inventory day on Vast.ai from becoming downtime):
```bash
# On Linux/macOS
export VAST_API_KEY="your_vast_api_key"
export RUNPOD_API_KEY="your_runpod_api_key"   # optional, enables cross-cloud fallback + auto-failback

# On Windows (PowerShell)
$env:VAST_API_KEY="your_vast_api_key"
$env:RUNPOD_API_KEY="your_runpod_api_key"
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
         │ ─── (Sync: rsync/scp delta) ──────> │ (Cached Workspace)                 │
         │                                     │                                    │
    [🚨 Evicted!]                              │                                    │
         ❌ ─── (Detected within 5s) ────────> │                                    │
                                               │ ─── (Race 4 candidates) ──────────> │
                                               │      cheapest of the ready pool wins │
                                               │ ─── (Restore Workspace) ──────────> │
                                               │ ─── (Nohup Resume Command) ──────> [Run Workload]
                                                                                      (Continuing!)

  If Vast.ai has zero candidates:
                                               │ ─── (Bridge to RunPod) ────────────> [Temp Replacement]
                                               │ ⋯ keeps watching Vast.ai in the background ⋯
                                               │ ─── (Vast.ai capacity returns) ──> [Migrate back, cheaper]
```

1. **Eviction Detection**: SpotWarp polls the cloud API every 5 seconds. If eviction is detected, it triggers failover immediately.
2. **Parallel Candidate Racing**: SpotWarp rents up to 4 matching-GPU candidates concurrently and picks the cheapest one that proves SSH-reachable, instead of trying offers one at a time.
3. **Cross-Cloud Bridge (if needed)**: If no Vast.ai candidate exists at that moment, SpotWarp automatically rents on RunPod instead — spot pricing first, on-demand as a second attempt — so the workload is never left completely unprotected.
4. **Delta Sync Restoration**: SpotWarp transfers the cached workspace folder to the new container and confirms it's reachable over a real SSH connection.
5. **Nohup Handover**: SpotWarp connects via SSH to trigger the `--resume-cmd` in the background.
6. **Auto-Failback**: If step 3 was needed, SpotWarp keeps quietly re-checking Vast.ai for that GPU model. The moment a candidate reappears, it migrates the workload back automatically and releases the bridge-cloud host — no manual intervention, no forgotten expensive instance left running.

---

## 📄 License & Security Audits
SpotWarp is distributed under the MIT License. The code executes 100% locally in user space on your local computer, ensuring full transparency and compliance.
