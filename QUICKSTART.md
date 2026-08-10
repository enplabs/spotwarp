# SpotWarp — Setup Guide

Five steps, in order. Windows PowerShell and macOS/Linux commands are both shown where they differ — copy the one for your machine.

An interactive version of this guide is also at [gpu-action.com/quickstart](https://gpu-action.com/quickstart).

## 1. Get a GPU to protect

SpotWarp doesn't rent or resell GPUs — you rent directly from Vast.ai, and SpotWarp watches whatever you've rented there.

Sign up at **vast.ai** → Account → API Keys, generate a key. Then rent a GPU instance yourself from their console (any Spot-priced GPU). Keep the API key handy for step 4.

## 2. Install SpotWarp

On your own PC — not the rented GPU:

```bash
pip install --upgrade spotwarp
```

Always include `--upgrade`. Without it, pip silently does nothing if any version is already installed — you can end up running code that's months old with no warning.

## 3. Set your API keys

Current terminal window only. These stay 100% local — SpotWarp never sees or stores them. RunPod is optional; it only enables cross-cloud fallback.

**Windows — PowerShell:**
```powershell
$env:VAST_API_KEY="your_key"
$env:RUNPOD_API_KEY="your_key"  # optional
```

**macOS / Linux:**
```bash
export VAST_API_KEY="your_key"
export RUNPOD_API_KEY="your_key"  # optional
```

> **Common mistake:** `export` is bash-only — it errors out in PowerShell (`CommandNotFoundException`). Use `$env:` on Windows. This has to be re-run every time you open a new terminal window.

## 4. Start the guard

Same window as step 3.

Minimum:
```bash
spotwarp start --license-key YOUR_LICENSE_KEY
```

Full — auto-resume training + custom backup drive:
```powershell
spotwarp start --license-key YOUR_LICENSE_KEY `
  --resume-cmd "python train.py --resume" `
  --backup-dir "D:\SpotwarpBackups"
```

Paste your license key as **one unbroken piece** — a dropped `TRIAL_` prefix or two keys pasted together is the #1 cause of a 401 error below.

No training script running yet? Drop `--resume-cmd` entirely. No preferred backup location? Drop `--backup-dir` — it defaults to `./backups/` next to where you ran the command. **Leave this window open** — closing it stops protection.

## 5. Read what it's telling you

| Console output | Meaning |
|---|---|
| `License Verified: Active` | ✅ Good — you're authenticated, protection is live. |
| `Monitoring 0 instances` | ⏳ Normal if no GPU rented yet, or wrong terminal window (step 3 didn't carry over). |
| `Found new active instance: …` | ✅ Good — your rented GPU was auto-detected, backup starting. |
| `sync attempt failed (exit 255)` | ⏳ Normal, once — fresh instance still booting SSH. Retries every 30s on its own. |
| `WARNING: 3 consecutive failures` | ⚠️ Investigate — not just booting anymore, SSH into the instance yourself to check. |

## Troubleshooting

| You see | It means |
|---|---|
| status 401 | License key mistyped or concatenated with another key — re-copy it as one piece. |
| 0 instances, GPU rented | `VAST_API_KEY` isn't set in this window — re-run step 3 here. |
| `export` error | You're in PowerShell — use `$env:` instead. |
| backups missing | Check `./backups/<instance_id>/`, or your `--backup-dir` path. |

Still stuck — email [info@gpu-action.com](mailto:info@gpu-action.com) with your license key and the console output around the issue.
