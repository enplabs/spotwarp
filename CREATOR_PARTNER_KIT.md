# SpotWarp — Creator Partner & Media Kit 🚀
*Official Partnership & Media Resources for AI/ML Creators & Developers*

---

## 1. 30-Second Quick Summary (For Video & Description)
> **"SpotWarp streams workspace delta-checkpoints (`.safetensors`, `.pt`) continuously to safe storage with <1% overhead, and automatically provisions a replacement GPU (even across Vast.ai ⇄ RunPod) over SSH in under 60 seconds if your spot instance gets evicted."**

---

## 2. Copy-Paste YouTube Video Description Snippets

### Standard Affiliate Blurb (Add to Video Description)
```markdown
⚡ Protect your Spot GPU runs from eviction with SpotWarp:
👉 Get 50% off your first 3 months: https://gpu-action.com/?ref={YOUR_CHANNEL_TAG}
• Continuous live auto-backup of checkpoints (.safetensors, .pt)
• Instant cross-cloud failover (Vast.ai ⇄ RunPod) in <60 seconds
• 100% open-core & local CLI daemon (pip install spotwarp / github.com/enplabs/spotwarp)
```

### Pinned Comment Template
```markdown
📌 Are you running LoRA / ComfyUI / PyTorch training on cheap Spot GPUs (RunPod, Vast.ai)?
Never lose training progress to sudden host evictions. 50% off your first 3 months of SpotWarp here: https://gpu-action.com/?ref={YOUR_CHANNEL_TAG}
```

---

## 3. GitHub & README Badge Code

Add this badge to your GitHub repository or ComfyUI custom node README:

```markdown
[![SpotWarp Protected](https://img.shields.io/badge/SpotWarp-Protected_GPU_Failover-2563EB?logo=linux&logoColor=white)](https://gpu-action.com/?ref={YOUR_CHANNEL_TAG})
```

---

## 4. Installation & Quick Setup (v3.4.3)

### Option A: Official Python PyPI (Recommended for AI/ML Environments)
```bash
pip install --upgrade spotwarp
```

### Option B: Universal 1-Liner (Linux / macOS)
```bash
curl -fsSL https://gpu-action.com/install.sh | bash
```
*(Windows PowerShell: `irm https://gpu-action.com/install.ps1 | iex`)*

### Quick Start & Zero-Config Daemon
```bash
# 1. 10-Second Interactive Setup (Auto-detects ~/.vast_api_key & ~/.runpod)
spotwarp init

# 2. Start Background Daemon to protect your workspace
spotwarp start -d

# 3. Check Live Status anytime
spotwarp status
```

---

## 5. Creator Commission Structure

**Flat 20% lifetime recurring commission, no tiers, from your very first referred subscriber.** Every subscriber who signs up through your link or promo code — Monthly Pass or Annual Pass — pays you 20% of what they pay us, for as long as their subscription stays active.

| Plan Your Referral Subscribes To | Their Discount | Your Recurring Commission |
| :---: | :---: | :---: |
| Monthly Pass ($49/mo) | 50% off first 3 months | 20% of whatever they're actually paying that cycle |
| Annual Pass ($490/yr) | 20% off first year | 20% of whatever they're actually paying that cycle |

* *Contact: Leo Chen (`info@gpu-action.com`) for payout details.*
