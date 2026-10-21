# Zero-Loss Checkpoint Recovery on SaladCloud: Architectural Overview

*Published by the SpotWarp Engineering Team (v3.5.1)*

SaladCloud provides unmatched price-to-performance by aggregating tens of thousands of consumer RTX 3080, 3090, 4080, and 4090 GPUs worldwide. Because nodes on a residential mesh can disconnect when host machines go offline, stateful workloads such as LoRA fine-tuning and PyTorch training require resilient checkpoint management.

`spotwarp` solves this with a **100% Local Same-Cloud (`Salad ➡️ Salad`) Failover Architecture**—eliminating the need for expensive cloud controller VMs or S3 object storage buckets.

---

## Architectural Principles

1. **Same-Cloud Retention (`Salad ➡️ Salad`)**:
   SpotWarp never migrates workloads off SaladCloud. When an active container instance is preempted or reallocated by SaladCloud Container Engine (SCE), SpotWarp tracks the replacement instance within your Salad container group and restores state directly onto the new Salad node.

2. **Zero Cloud Storage Overhead**:
   Traditional orchestration tools require spinning up a dedicated 24/7 cloud controller VM and paying for S3/GCS bucket storage and egress traffic. SpotWarp runs as a lightweight local daemon on the developer's workstation, syncing `/workspace/` checkpoints directly over SSH (`rsync` delta-sync or `scp`).

3. **Twelve-Factor Encrypted Secrets & Zero-Friction Trial**:
   Container recipes on SaladCloud inject `LICENSE_KEY` via end-to-end encrypted environment variables. By default, SpotWarp includes a 14-day zero-friction evaluation mode (`SALAD-TRIAL`) so developers can deploy immediately from the SaladCloud Portal without leaving their workflow.

---

## Verified Live Chaos Benchmark on SaladCloud

- **Container Group**: `ghcr.io/enplabs/spotwarp:pytorch2.1`
- **Event**: Forced node reallocation (`POST /instances/{id}/reallocate`) during Epoch 8 checkpointing
- **Data Integrity**: 100% SHA-256 bit-for-bit checkpoint match restored to replacement Salad node
- **Lost Training Epochs**: `0.00%`

---

## Resources
- GitHub Repository: [https://github.com/enplabs/spotwarp](https://github.com/enplabs/spotwarp)
- SaladCloud Recipe Spec: [`recipes/salad/salad_recipe.json`](recipes/salad/salad_recipe.json)
- PyPI Package: `pip install spotwarp`
