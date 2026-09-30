# SpotWarp — Quick Setup Guide (v3.4.3)

Three simple steps. Your credentials stay 100% local — zero cloud key uploads.

An interactive version of this guide is also at [gpu-action.com/quickstart](https://gpu-action.com/quickstart).

## 1. Install SpotWarp

On your own PC or server (Linux, macOS, or Windows):

### Standard Python pip (Recommended)
```bash
pip install --upgrade spotwarp
```

### Universal 1-Liner

**Linux / macOS:**
```bash
curl -fsSL https://gpu-action.com/install.sh | bash
```

**Windows PowerShell:**
```powershell
irm https://gpu-action.com/install.ps1 | iex
```

## 2. Zero-Config Setup

SpotWarp automatically detects your existing Vast.ai and RunPod keys from `~/.vast_api_key` or `~/.runpod/config.toml` (Zero-Config mode).

Or run the interactive 1-minute setup wizard to save keys locally to `~/.spotwarp/config.json`:

```bash
spotwarp init
```

The interactive wizard will prompt you for:
1. **SpotWarp License Key** (required — get one at gpu-action.com/pricing; the wizard exits if this is left blank)
2. **Vast.ai API Key** (auto-detected if present)
3. **RunPod API Key** (auto-detected if present, enables cross-cloud bridge fallback)
4. **Backup Directory** (default: `./backups/`)

## 3. Start the Guard

```bash
# Option A: 24/7 background daemon (safely close terminal)
spotwarp start -d

# Option B: Foreground live console
spotwarp start
```

### Auto-Resume Training (Optional)
To automatically resume training scripts inside the replacement container upon eviction:
```bash
spotwarp start --resume-cmd "python train.py --resume" -d
```

## 4. Daemon Management Commands

```bash
spotwarp status   # Check if background daemon is running & PID
spotwarp stop     # Gracefully stop the background daemon
spotwarp config   # View your current local configuration
```

## 5. Read what it's telling you

| Console output | Meaning |
|---|---|
| `License Verified: Active` | Good — you're authenticated, protection is live. |
| `Monitoring 0 instances` | Normal if no GPU rented yet, or wrong terminal window. |
| `Found new active instance` | Good — your rented GPU was auto-detected, backup starting. |
| `sync attempt failed (exit 255)` | Normal, once — fresh instance still booting SSH. Retries every 30s on its own. |
| `WARNING: 3 consecutive failures` | Investigate — not just booting anymore, SSH into the instance yourself to check. |

## Troubleshooting

| You see | It means |
|---|---|
| status 401 | License key mistyped or concatenated with another key — re-copy it as one piece. |
| 0 instances, GPU rented | `VAST_API_KEY` or `RUNPOD_API_KEY` isn't set in this window — run `spotwarp init` to save permanently. |
| `export` error | You're in PowerShell — use `$env:` instead. |
| backups missing | Check `./backups/<instance_id>/`, or your `--backup-dir` path. |

Still stuck? Email [info@gpu-action.com](mailto:info@gpu-action.com) with your license key and the console output around the issue.
