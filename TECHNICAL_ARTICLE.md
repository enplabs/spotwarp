# How We Built SpotWarp: A Local Spot GPU Failover Guard in Python

*Published by the SpotWarp Engineering Team*

Running LLMs, Stable Diffusion, or PyTorch models on on-demand cloud GPUs (like AWS p4d / g5 instances) costs $3.50 to $4.50 per hour. Meanwhile, Spot instances on platforms like Vast.ai or RunPod offer the exact same NVIDIA RTX 3090 / A100 GPUs for **$0.15 to $0.40 per hour — a 70% to 90% discount**.

However, AI startups often avoid Spot GPUs because of **evictions**. When a host reclaims a Spot instance, your API returns HTTP 500 errors or your 12-hour training run dies.

In this technical breakdown, we explain how we built `spotwarp` — a zero-downtime, local Python failover daemon — and how it detects and reacts to evictions automatically.

---

## The Architecture: Why Local Execution Matters

Most infrastructure proxies require you to upload your cloud API keys to a central server. For AI startups, handing over production cloud credentials to an unknown third party is a non-starter.

We solved this with a **Dual-Component Open Core Architecture**:

```
[Client Host Machine (100% Local)]
  • pip install spotwarp
  • Reads VAST_API_KEY locally (never transmitted)
  • Polls instance endpoints & monitors eviction signals
  • Spawns a replacement GPU locally on eviction

[SpotWarp Central API (https://gpu-action.com)]
  • Verifies license token
  • Serves node health data & marketplace pricing lookups
```

---

## How Failover Works

1. **Eviction Signal Detection**:
   Vast.ai's API surfaces an `actual_status != intended_status` or `cur_state == 'exited'` signal when a host reclaims an instance. The daemon polls for this.

2. **Matching Replacement Search**:
   The daemon queries Vast.ai's public bundles API for the cheapest available offer matching the *same GPU model* that was evicted (falling back to a budget RTX 3090 only if the model can't be determined) — so an H100 user doesn't get silently downgraded to something weaker.

3. **Workspace Restore & Handover**:
   In parallel, the daemon has been running a background delta-sync of the `/workspace/` folder to the local machine. On failover, it restores that workspace to the replacement instance and, if configured, resumes the training command over SSH.

---

## Open Source Security Audit

The client daemon is 100% open-source and requires **Zero Root/Sudo Privileges**.

- GitHub Repository: [https://github.com/enplabs/spotwarp](https://github.com/enplabs/spotwarp)
- PyPI Package: `pip install spotwarp`
- Documentation & Free Trial: [https://gpu-action.com](https://gpu-action.com)
