# SpotWarp — SaladCloud Quick Setup Guide (v3.5.1)

Three simple steps to protect your SaladCloud GPU containers with automated local checkpoint backups and Same-Cloud (`Salad ➡️ Salad`) failover.

## 1. Install SpotWarp on Your Local Machine

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

## 2. Configure Your SaladCloud Credentials

Run the interactive setup wizard to save your settings locally to `~/.spotwarp/config.json`:

```bash
spotwarp init
```

The wizard will prompt you for:
1. **SpotWarp License Key** (Press Enter to start immediately with the built-in **14-Day SaladCloud Trial** `SALAD-TRIAL`, or enter a paid key from `gpu-action.com`)
2. **SaladCloud API Key** (`SALAD_API_KEY` — remains 100% on your local machine)
3. **SaladCloud Organization Name** (`SALAD_ORG`)
4. **SaladCloud Project Name** (default: `default`)
5. **Local Backup Directory** (default: `./backups`)

## 3. Start the SaladCloud Failover Guard

```bash
# Option A: 24/7 background daemon
spotwarp start -d

# Option B: Foreground live console
spotwarp start
```

### Auto-Resume Training on New Salad Nodes (Optional)
To automatically restart your training script inside the replacement SaladCloud container after checkpoints are restored:
```bash
spotwarp start -d --resume-cmd "python3 /workspace/train.py --resume"
```

## 4. Daemon Management Commands

```bash
spotwarp status   # Check active daemon status, PID, and recent logs
spotwarp stop     # Gracefully stop the background daemon
spotwarp config   # View your local SaladCloud configuration
```

## Support
Questions or feedback? Contact [info@gpu-action.com](mailto:info@gpu-action.com).
