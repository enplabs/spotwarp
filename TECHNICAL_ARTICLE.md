# How We Built a 0.05s Spot GPU Failover Guard in 300 Lines of Python

*Published by the GPU-Action Engineering Team*

Running LLMs, Stable Diffusion, or PyTorch models on on-demand cloud GPUs (like AWS p4d / g5 instances) costs $3.50 to $4.50 per hour. Meanwhile, Spot instances on platforms like Vast.ai or RunPod offer the exact same NVIDIA RTX 3090 / A100 GPUs for **$0.15 to $0.40 per hour — a 70% to 90% discount**.

However, AI startups often avoid Spot GPUs because of **evictions**. When a host reclaims a Spot instance, your API returns HTTP 500 errors or your 12-hour training run dies.

In this technical breakdown, we explain how we built `gpu-action` — a zero-downtime, local Python failover daemon — and how it handles evictions in under 0.05 seconds.

---

## The Architecture: Why Local Execution Matters

Most infrastructure proxies require you to upload your cloud API keys to a central server. For AI startups, handing over production cloud credentials to an unknown third party is a non-starter.

We solved this with a **Dual-Component Open Core Architecture**:

```
[Client Host Machine (100% Local)]
  • pip install gpu-action
  • Reads VAST_API_KEY locally (never transmitted)
  • Pings instance endpoints & monitors eviction signals
  • Spawns replacement GPU locally on eviction

[GPU-Action Central API (https://gpu-action.com)]
  • Verifies $49/mo license token
  • Serves 24/7 global node health scores & lowest-cost marketplace rankings
```

---

## How 0.05s Failover Works

1. **Eviction Signal Interception**:
   Vast.ai API emits an `actual_status != intended_status` or `cur_state == 'exited'` signal when a host reclaims an instance.

2. **Automated Backup Node Selection**:
   The daemon queries the central GPU-Action Node Intelligence API (`/api/v0/bundles`) to fetch the top-ranked, lowest-latency RTX 3090/A100 offer on the market.

3. **Instance Provisioning & Proxy Reroute**:
   The daemon executes an automated API call to instantiate the replacement GPU and updates the local proxy routing table in under 50ms.

---

## Open Source Security Audit

The client daemon is 100% open-source and requires **Zero Root/Sudo Privileges**. 

- GitHub Repository: [https://github.com/enplabs/gpu-action](https://github.com/enplabs/gpu-action)
- PyPI Package: `pip install gpu-action`
- Documentation & Free Trial: [https://gpu-action.com](https://gpu-action.com)
