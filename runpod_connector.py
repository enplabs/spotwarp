import requests
import json
import time
import os
import sys

RUNPOD_GPU_TYPE_MAP = {
    "4090": "NVIDIA GeForce RTX 4090",
    "3090": "NVIDIA GeForce RTX 3090",
    "3090ti": "NVIDIA GeForce RTX 3090 Ti",
    "4080": "NVIDIA GeForce RTX 4080",
    "3080": "NVIDIA GeForce RTX 3080",
    "3070": "NVIDIA GeForce RTX 3070",
    "a100": "NVIDIA A100 80GB PCIe",
    "a100-sxm": "NVIDIA A100-SXM4-80GB",
    "a100-40": "NVIDIA A100-SXM4-40GB",
    "h100": "NVIDIA H100 80GB HBM3",
    "h100-pcie": "NVIDIA H100 PCIe",
    "h100-nvl": "NVIDIA H100 NVL",
    "h200": "NVIDIA H200",
    "b200": "NVIDIA B200",
    "l40s": "NVIDIA L40S",
    "l40": "NVIDIA L40",
    "l4": "NVIDIA L4",
    "a6000": "NVIDIA RTX A6000",
    "a5000": "NVIDIA RTX A5000",
    "a4000": "NVIDIA RTX A4000",
    "v100": "Tesla V100-PCIE-16GB",
}

class RunPodGPUConnector:
    """
    SpotWarp RunPod GPU Connector (v3.4)
    Full Bidirectional GraphQL Client for Pod Monitoring, Deployment & Teardown.
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("RUNPOD_API_KEY")
        if not self.api_key:
            self.set_api_key_from_env()
        self.url = "https://api.runpod.io/graphql"
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def set_api_key_from_env(self):
        key = os.getenv("RUNPOD_API_KEY")
        if not key:
            rp_file = os.path.expanduser("~/.runpod/config.toml")
            if os.path.exists(rp_file):
                try:
                    with open(rp_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        import re
                        m = re.search(r'api_key\s*=\s*["\']([^"\']+)["\']', content)
                        if m:
                            key = m.group(1)
                except Exception:
                    pass
        if not key:
            cfg_file = os.path.expanduser("~/.spotwarp/config.json")
            if os.path.exists(cfg_file):
                try:
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        key = cfg.get("runpod_api_key")
                except Exception:
                    pass
        if key:
            self.api_key = key
            self.headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}"
            }
        return key

    def resolve_gpu_type_id(self, gpu_name_or_token: str) -> str:
        if not gpu_name_or_token:
            return "NVIDIA GeForce RTX 4090"
        
        token = str(gpu_name_or_token).lower().replace(" ", "").replace("_", "").replace("-", "")
        for k, v in RUNPOD_GPU_TYPE_MAP.items():
            k_clean = k.replace("-", "").replace("_", "")
            if k_clean in token or token in k_clean:
                return v
        
        for k, v in RUNPOD_GPU_TYPE_MAP.items():
            if k in str(gpu_name_or_token).lower():
                return v

        return "NVIDIA GeForce RTX 4090"

    def check_spot_stock(self, gpu_type_or_token: str) -> dict:
        target_gpu_id = self.resolve_gpu_type_id(gpu_type_or_token)
        query = """
        query {
          gpuTypes {
            id
            displayName
            lowestPrice(input: {gpuCount: 1}) {
              minimumBidPrice
              uninterruptablePrice
            }
          }
        }
        """
        try:
            r = requests.post(self.url, json={"query": query}, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                gpus = data.get("data", {}).get("gpuTypes", [])
                for g in gpus:
                    if g.get("id") == target_gpu_id:
                        lowest = g.get("lowestPrice") or {}
                        spot_bid = lowest.get("minimumBidPrice")
                        ondemand = lowest.get("uninterruptablePrice")
                        is_avail = spot_bid is not None
                        return {
                            "available": is_avail,
                            "spot_price": spot_bid,
                            "ondemand_price": ondemand,
                            "gpu_id": target_gpu_id,
                            "display_name": g.get("displayName")
                        }
        except Exception as e:
            print(f"[RunPod] Stock query error: {e}")
        return {"available": False, "spot_price": None, "ondemand_price": None, "gpu_id": target_gpu_id}

    def get_user_pods(self) -> list:
        if not self.api_key:
            self.set_api_key_from_env()
        if not self.api_key:
            return []

        query = """
        query {
          myself {
            pods {
              id
              name
              desiredStatus
              imageName
              costPerHr
              machine {
                gpuDisplayName
              }
              runtime {
                uptimeInSeconds
                ports {
                  ip
                  isIpPublic
                  privatePort
                  publicPort
                  type
                }
              }
            }
          }
        }
        """
        try:
            r = requests.post(self.url, json={"query": query}, headers=self.headers, timeout=10)
            if r.status_code != 200:
                return []
            res_data = r.json()
            raw_pods = res_data.get("data", {}).get("myself", {}).get("pods", [])
            
            parsed_pods = []
            for p in raw_pods:
                runtime = p.get("runtime") or {}
                ports = runtime.get("ports") or []
                ip = None
                ssh_port = None
                jupyter_port = None
                for port_obj in ports:
                    priv = port_obj.get("privatePort")
                    if priv == 22:
                        ip = port_obj.get("ip")
                        ssh_port = port_obj.get("publicPort")
                    elif priv in (8888, 8080):
                        jupyter_port = port_obj.get("publicPort")

                gpu_name = p.get("machine", {}).get("gpuDisplayName") if p.get("machine") else "Unknown"
                
                parsed_pods.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "desiredStatus": p.get("desiredStatus"),
                    "imageName": p.get("imageName"),
                    "gpu_name": gpu_name,
                    "cost_per_hr": p.get("costPerHr"),
                    "uptime": runtime.get("uptimeInSeconds", 0),
                    "ip": ip,
                    "ssh_port": ssh_port,
                    "jupyter_port": jupyter_port,
                    "is_running": p.get("desiredStatus") == "RUNNING" and ip is not None and ssh_port is not None
                })
            return parsed_pods
        except Exception as e:
            print(f"[RunPod] Get user pods error: {e}")
            return []

    def get_pod_network_info(self, pod_id: str) -> dict:
        query = """
        query ($podId: String!) {
          pod(input: {podId: $podId}) {
            id
            desiredStatus
            runtime {
              uptimeInSeconds
              ports {
                ip
                privatePort
                publicPort
              }
            }
            machine {
              gpuDisplayName
            }
          }
        }
        """
        variables = {"podId": str(pod_id)}
        try:
            r = requests.post(self.url, json={"query": query, "variables": variables}, headers=self.headers, timeout=10)
            if r.status_code != 200:
                return None
            res_data = r.json()
            pod_info = res_data.get("data", {}).get("pod")
            if not pod_info:
                return None
            
            runtime = pod_info.get("runtime") or {}
            ports = runtime.get("ports") or []
            info = {
                "ip": None,
                "ssh_port": None,
                "jupyter_port": None,
                "status": pod_info.get("desiredStatus"),
                "gpu_name": pod_info.get("machine", {}).get("gpuDisplayName", "Unknown") if pod_info.get("machine") else "Unknown"
            }
            for p in ports:
                priv = p.get("privatePort")
                if priv == 22:
                    info["ip"] = p.get("ip")
                    info["ssh_port"] = p.get("publicPort")
                elif priv in (8888, 8080):
                    info["jupyter_port"] = p.get("publicPort")
            
            return info
        except Exception:
            return None

    def request_gpu_spot_pod(self, gpu_type="NVIDIA GeForce RTX 4090", template_id="runpod-torch-v21", disk_gb=20):
        """
        Deploys a Spot Pod on RunPod via podRentInterruptable mutation with PUBLIC_KEY injected.
        Waits until network address (IP and SSH port) is live and ready.
        """
        if not self.api_key:
            self.set_api_key_from_env()
        if not self.api_key:
            print("[-] RunPod API Key not set.")
            return None

        exact_gpu_type = self.resolve_gpu_type_id(gpu_type)
        print(f"[*] Requesting RunPod Spot Pod ({exact_gpu_type})...")

        stock_info = self.check_spot_stock(exact_gpu_type)
        if not stock_info.get("available"):
            print(f"[-] RunPod Spot GPU '{exact_gpu_type}' currently OUT OF STOCK.")
            return None
        
        spot_price = stock_info.get("spot_price") or 0.25
        bid_price = round(spot_price * 1.15, 2)
        print(f"[+] RunPod Spot GPU in stock at ${spot_price:.3f}/hr (Bidding ${bid_price:.3f}/hr).")

        # Fetch user's registered public SSH key for passwordless entry
        user_pub_key = None
        try:
            r_user = requests.post(self.url, json={"query": "{ myself { pubKey } }"}, headers=self.headers, timeout=10)
            if r_user.status_code == 200:
                user_pub_key = r_user.json().get("data", {}).get("myself", {}).get("pubKey")
        except Exception:
            pass

        env_list = []
        if user_pub_key:
            env_list.append({"key": "PUBLIC_KEY", "value": user_pub_key})

        mutation = """
        mutation ($input: PodRentInterruptableInput!) {
          podRentInterruptable(input: $input) {
            id
            imageName
            desiredStatus
            machineId
          }
        }
        """
        variables = {
            "input": {
                "templateId": template_id,
                "gpuTypeId": exact_gpu_type,
                "gpuCount": 1,
                "bidPerGpu": bid_price,
                "volumeInGb": disk_gb,
                "containerDiskInGb": disk_gb,
                "supportPublicIp": True,
                "env": env_list
            }
        }
        
        try:
            r = requests.post(self.url, json={"query": mutation, "variables": variables}, headers=self.headers, timeout=15)
            if r.status_code != 200:
                print(f"[-] RunPod API Error: {r.status_code} {r.text}")
                return None
            
            res_data = r.json()
            errors = res_data.get("errors")
            if errors:
                print(f"[-] RunPod GraphQL Errors: {json.dumps(errors)}")
                return None
                
            pod_data = res_data.get("data", {}).get("podRentInterruptable")
            if not pod_data:
                return None

            pod_id = pod_data["id"]
            print(f"[+] RunPod Spot Pod allocated successfully! Pod ID: {pod_id}")
            
            print("[*] Waiting for RunPod network routing and container initialization...")
            for i in range(30):  # 150s timeout: essential for large enterprise images (A100/H100)
                time.sleep(5)
                status_res = self.get_pod_network_info(pod_id)
                if status_res and status_res.get("ip") and status_res.get("ssh_port"):
                    print(f"[+] RunPod Pod is ACTIVE! SSH: {status_res['ip']}:{status_res['ssh_port']}, GPU: {exact_gpu_type}")
                    return {
                        "pod_id": pod_id,
                        "ip": status_res["ip"],
                        "ssh_port": status_res["ssh_port"],
                        "jupyter_port": status_res.get("jupyter_port"),
                        "gpu_name": exact_gpu_type
                    }
            
            print("\n[-] RunPod network assignment timed out.")
            return None

        except Exception as e:
            print(f"[-] RunPod Pod Allocation Error: {str(e)}")
            return None

    def terminate_pod(self, pod_id: str) -> bool:
        print(f"[*] Terminating RunPod Pod {pod_id}...")
        if not self.api_key:
            self.set_api_key_from_env()
            
        mutation = """
        mutation ($input: PodTerminateInput!) {
          podTerminate(input: $input)
        }
        """
        variables = {"input": {"podId": str(pod_id)}}
        try:
            r = requests.post(self.url, json={"query": mutation, "variables": variables}, headers=self.headers, timeout=10)
            if r.status_code == 200 and not r.json().get("errors"):
                print(f"[+] RunPod Pod {pod_id} terminated successfully.")
                return True
            print(f"[-] Termination failed: {r.text}")
            return False
        except Exception as e:
            print(f"[-] RunPod Termination Error: {str(e)}")
            return False

if __name__ == "__main__":
    connector = RunPodGPUConnector()
    print("[*] RunPod Connector v3.4 initialized.")
    pods = connector.get_user_pods()
    print(f"[*] Current active user pods: {len(pods)}")
    for p in pods:
        print(f"  - {p['id']} | {p['name']} | Status: {p['desiredStatus']} | IP: {p['ip']}:{p['ssh_port']}")
