import requests
import json
import time
import sys

# RunPod API Client via GraphQL endpoint
class RunPodGPUConnector:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.url = "https://api.runpod.io/v1/graphql"
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def set_api_key_from_env(self):
        import os
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        key = os.getenv("RUNPOD_API_KEY")
        if key:
            self.api_key = key
            self.headers["Authorization"] = f"Bearer {key}"
        return key

    def request_gpu_spot_pod(self, gpu_type="NVIDIA RTX 4090", image_name="ghcr.io/enplabs/spotwarp:pytorch2.1"):
        """
        Deploys a Spot Pod on RunPod using GraphQL mutation.
        """
        if not self.api_key:
            self.set_api_key_from_env()
        if not self.api_key:
            print("[-] RunPod API Key not set.")
            return None

        print(f"[*] Requesting RunPod Spot Pod ({gpu_type})...")
        mutation = """
        mutation ($input: PodFindAndDeploySpotInput!) {
          podFindAndDeploySpot(input: $input) {
            id
            imageName
            machineId
          }
        }
        """
        variables = {
            "input": {
                "gpuTypeId": gpu_type,
                "gpuCount": 1,
                "imageName": image_name,
                "volumeInGb": 20,
                "containerDiskInGb": 20,
                "ports": "8888/http,22/tcp",
                "supportPublicIp": True
            }
        }
        
        try:
            r = requests.post(self.url, json={"query": mutation, "variables": variables}, headers=self.headers)
            if r.status_code != 200:
                print(f"[-] RunPod API Error: {r.status_code} {r.text}")
                return None
            
            res_data = r.json()
            errors = res_data.get("errors")
            if errors:
                print(f"[-] RunPod GraphQL Errors: {json.dumps(errors)}")
                return None
                
            pod_data = res_data["data"]["podFindAndDeploySpot"]
            pod_id = pod_data["id"]
            print(f"[+] RunPod Spot Pod requested successfully. Pod ID: {pod_id}")
            
            # Wait for allocation and obtain public IP / SSH port
            print("[*] Waiting for RunPod allocation and networking...")
            for i in range(12):
                time.sleep(10)
                status_res = self.get_pod_network_info(pod_id)
                if status_res and status_res.get("ip") and status_res.get("ssh_port"):
                    print(f"[+] RunPod Pod is active! SSH: {status_res['ip']}:{status_res['ssh_port']}, Jupyter: {status_res.get('jupyter_port')}")
                    return {
                        "pod_id": pod_id,
                        "ip": status_res["ip"],
                        "ssh_port": status_res["ssh_port"],
                        "jupyter_port": status_res.get("jupyter_port")
                    }
                print(f"  - Check {i+1}/12: Waiting for network address assignment...")
            
            print("[-] RunPod network assignment timed out.")
            return None

        except Exception as e:
            print(f"[-] RunPod Pod Allocation Error: {str(e)}")
            return None

    def get_pod_network_info(self, pod_id):
        """
        Queries pod status to retrieve the mapped public IP and port for SSH (22/tcp)
        and Jupyter HTTP (8888/tcp or 8080/tcp).
        """
        query = """
        query ($podId: String!) {
          pod(input: {podId: $podId}) {
            id
            runtime {
              ports {
                ip
                privatePort
                publicPort
              }
            }
          }
        }
        """
        variables = {"podId": pod_id}
        try:
            r = requests.post(self.url, json={"query": query, "variables": variables}, headers=self.headers)
            if r.status_code != 200:
                return None
            res_data = r.json()
            pod_info = res_data.get("data", {}).get("pod")
            if not pod_info or not pod_info.get("runtime"):
                return None
            
            ports = pod_info["runtime"].get("ports", [])
            info = {"ip": None, "ssh_port": None, "jupyter_port": None}
            for p in ports:
                private_p = p.get("privatePort")
                if private_p == 22:
                    info["ip"] = p.get("ip")
                    info["ssh_port"] = p.get("publicPort")
                elif private_p in (8888, 8080):
                    info["jupyter_port"] = p.get("publicPort")
            
            if info["ip"] and info["ssh_port"]:
                return info
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
            
        mutation = """
        mutation ($input: PodTerminateInput!) {
          podTerminate(input: $input)
        }
        """
        variables = {"input": {"podId": pod_id}}
        try:
            r = requests.post(self.url, json={"query": mutation, "variables": variables}, headers=self.headers)
            if r.status_code == 200 and not r.json().get("errors"):
                print("[+] RunPod Pod terminated successfully.")
                return True
            print(f"[-] Termination failed: {r.text}")
            return False
        except Exception as e:
            print(f"[-] RunPod Termination Error: {str(e)}")
            return False

if __name__ == "__main__":
    connector = RunPodGPUConnector()
    print("[*] RunPod Connector initialized.")
