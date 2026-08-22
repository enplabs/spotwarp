import requests
import time
import sys

# ==============================================================================
# SpotWarp: Cross-Cloud GPU Failover Connector (RunPod REST API v1)
# Version: 3.3.3 (100% Zero Key Leakage & Strict Hardware Matching)
# ==============================================================================
VERSION = "3.3.3"

class RunPodGPUConnector:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://rest.runpod.io/v1"

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def set_api_key_from_env(self):
        import os
        key = os.getenv("RUNPOD_API_KEY")
        if not key:
            from dotenv import load_dotenv
            load_dotenv()
            key = os.getenv("RUNPOD_API_KEY")
        if key:
            self.api_key = key
        return key

    def request_gpu_spot_pod(self, gpu_type="NVIDIA GeForce RTX 4090", image_name="runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04", allow_ondemand_fallback=True):
        """
        Deploys a Pod via the RunPod REST API — interruptible (spot) first,
        falling back to on-demand (full price) if that fails.

        Live-testing 2026-08-09 found two distinct interruptible-only failure
        modes across the 14-tier sweep: transient ("no longer any instances
        available") and structural (RunPod simply never lists spot pricing
        for that GPU at all — confirmed for V100 and RTX 3080, both of which
        errored "no spot price found for gpu type" on every attempt). Either
        way the fix is the same: retry once as on-demand rather than leaving
        the customer with zero cross-cloud protection for that eviction.
        RunPod-as-fallback is meant to be a temporary safety net (see
        check_runpod_failback, which migrates back to cheaper Vast the
        moment it can) — paying on-demand for that short bridge window is a
        reasonable trade for actually having a fallback at all.
        """
        if not self.api_key:
            self.set_api_key_from_env()
        if not self.api_key:
            print("[-] RunPod API Key not set.")
            return None

        attempts = [True, False] if allow_ondemand_fallback else [True]
        for interruptible in attempts:
            pricing_label = "spot" if interruptible else "on-demand"
            print(f"[*] Requesting RunPod Pod ({gpu_type}, {pricing_label} pricing)...")
            body = {
                "imageName": image_name,
                "gpuTypeIds": [gpu_type],
                "gpuCount": 1,
                "containerDiskInGb": 20,
                "volumeInGb": 20,
                "ports": ["8888/http", "22/tcp"],
                "interruptible": interruptible,
                "supportPublicIp": True,
            }

            try:
                r = requests.post(f"{self.base_url}/pods", json=body, headers=self._headers(), timeout=30)
                if r.status_code not in (200, 201):
                    print(f"[-] RunPod API Error ({pricing_label}): {r.status_code} {r.text}")
                    if interruptible and allow_ondemand_fallback:
                        print("[*] Retrying as on-demand (full price)...")
                        continue
                    return None

                pod_data = r.json()
                pod_id = pod_data["id"]
                print(f"[+] RunPod Pod requested successfully ({pricing_label}). Pod ID: {pod_id}")

                print("[*] Waiting for RunPod allocation and networking...")
                for i in range(12):
                    status_res = self.get_pod_network_info(pod_id)
                    if status_res and status_res.get("ip") and status_res.get("ssh_port"):
                        print(f"[+] RunPod Pod is active! SSH: {status_res['ip']}:{status_res['ssh_port']}, Jupyter: {status_res.get('jupyter_port')}")
                        return {
                            "pod_id": pod_id,
                            "ip": status_res["ip"],
                            "ssh_port": status_res["ssh_port"],
                            "jupyter_port": status_res.get("jupyter_port"),
                            "interruptible": interruptible,
                        }
                    print(f"  - Check {i+1}/12: Waiting for network address assignment...")
                    time.sleep(10)

                print("[-] RunPod network assignment timed out.")
                return None

            except Exception as e:
                print(f"[-] RunPod Pod Allocation Error ({pricing_label}): {str(e)}")
                if interruptible and allow_ondemand_fallback:
                    continue
                return None

        return None

    def get_pod_network_info(self, pod_id):
        """
        Queries pod status to retrieve the mapped public IP and port for SSH (22/tcp)
        and Jupyter HTTP (8888/tcp).
        """
        try:
            r = requests.get(f"{self.base_url}/pods/{pod_id}", headers=self._headers(), timeout=15)
            if r.status_code != 200:
                return None
            pod_info = r.json()
            ip = pod_info.get("publicIp")
            ports = pod_info.get("portMappings") or {}
            ssh_port = ports.get("22")
            jupyter_port = ports.get("8888")

            if ip and ssh_port:
                return {"ip": ip, "ssh_port": ssh_port, "jupyter_port": jupyter_port}
            return None
        except Exception:
            return None

    def terminate_pod(self, pod_id):
        """
        Terminates the RunPod instance to avoid charges.
        """
        print(f"[*] Terminating RunPod Pod {pod_id}...")
        if not self.api_key:
            self.set_api_key_from_env()

        try:
            r = requests.delete(f"{self.base_url}/pods/{pod_id}", headers=self._headers(), timeout=30)
            if r.status_code in (200, 202, 204):
                print("[+] RunPod Pod terminated successfully.")
                return True
            print(f"[-] Termination failed: {r.status_code} {r.text}")
            return False
        except Exception as e:
            print(f"[-] RunPod Termination Error: {str(e)}")
            return False


if __name__ == "__main__":
    connector = RunPodGPUConnector()
    print("[*] RunPod Connector initialized.")
