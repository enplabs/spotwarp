#!/usr/bin/env python3
"""
SpotWarp CLI: Spot-Instance Failover Guard Agent
--------------------------------------------------
100% Local Execution - Your VAST_API_KEY and RUNPOD_API_KEY stay 100% local.
Pings local/remote Vast.ai instances and automatically triggers zero-downtime 
failover upon eviction, with smart data sync and cross-cloud RunPod fallback.

Usage:
  pip install spotwarp
  spotwarp start --license-key YOUR_KEY --runpod-api-key RP_KEY --resume-cmd "python /workspace/train.py --resume"
"""

import os
import sys
import time
import json
import re
import argparse
import requests
import subprocess
import threading
import shutil

# Standardize terminal encoding to UTF-8 on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

CENTRAL_SERVER = "https://gpu-action.com"
LICENSE_VERIFY_ENDPOINT = f"{CENTRAL_SERVER}/api/v1/verify_license"
TEMPLATE_HASH_ID = "5d762fad90ee6aa0f8636464e142ad29"

def install_rsync_windows() -> bool:
    """Downloads and extracts a portable, self-contained rsync binary for Windows."""
    local_dir = os.path.expanduser("~/.gpu_action/bin")
    cygwin_dir = os.path.join(local_dir, "cygwin64")
    rsync_exe_path = os.path.join(cygwin_dir, "rsync.exe")
    
    if os.path.exists(rsync_exe_path):
        if cygwin_dir not in os.environ["PATH"]:
            os.environ["PATH"] = cygwin_dir + os.path.pathsep + os.environ["PATH"]
        return True
        
    print("\n[SpotWarp Windows Installer] Portable rsync not found. Initializing auto-setup...")
    os.makedirs(local_dir, exist_ok=True)
    zip_path = os.path.join(local_dir, "rsync-win.zip")
    url = "https://github.com/rn7s2/rsync-win/releases/download/v0.1.3/rsync-win.zip"
    
    try:
        import urllib.request
        import zipfile
        print(f"[Installer] Downloading portable package from: {url}")
        urllib.request.urlretrieve(url, zip_path)
        print("[Installer] Extracting package files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(local_dir)
        os.remove(zip_path)
        
        if os.path.exists(rsync_exe_path):
            print(f"[Installer] Setup complete! Portable rsync ready at: {cygwin_dir}")
            if cygwin_dir not in os.environ["PATH"]:
                os.environ["PATH"] = cygwin_dir + os.path.pathsep + os.environ["PATH"]
            return True
        else:
            print("[-] Verification failed: rsync.exe not found post-extraction.")
            return False
    except Exception as e:
        print(f"[-] Auto-setup failed: {e}")
        return False

class GpuActionGuard:
    def __init__(self, license_key: str, vast_api_key: str = None, runpod_api_key: str = None, resume_cmd: str = None):
        self.license_key = license_key
        self.vast_api_key = vast_api_key or os.getenv("VAST_API_KEY", "")
        self.runpod_api_key = runpod_api_key or os.getenv("RUNPOD_API_KEY", "")
        self.resume_cmd = resume_cmd
        self.headers = {"Accept": "application/json", "Authorization": f"Bearer {self.vast_api_key}"}
        self.is_valid_license = False
        self.tracked_instances = {}  # maps instance_id -> (host, ssh_port, host_id)
        self.backup_threads = {}
        self.stop_events = {}
        
        # Smart detection of rsync local presence (with Windows auto-setup)
        self.use_rsync = shutil.which("rsync") is not None
        if not self.use_rsync and sys.platform == 'win32':
            if install_rsync_windows():
                self.use_rsync = shutil.which("rsync") is not None

    def verify_license(self) -> bool:
        """Verifies active subscription or 14-day trial status with central server."""
        try:
            r = requests.post(
                LICENSE_VERIFY_ENDPOINT,
                json={"license_key": self.license_key},
                headers={"User-Agent": "SpotWarp-Guard/3.0"},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("valid"):
                    self.is_valid_license = True
                    print(f"[SpotWarp Guard] License Verified: Active ({data.get('plan', 'Developer Pass')})")
                    return True
                else:
                    print(f"[SpotWarp Guard] License Invalid or Expired: {data.get('message')}")
                    return False
            else:
                print(f"[SpotWarp Guard] License verification endpoint returned status {r.status_code}.")
                self.is_valid_license = True
                return True
        except Exception as e:
            print(f"[SpotWarp Guard] License verification warning: {e}. Running in local grace mode.")
            self.is_valid_license = True
            return True

    def check_vast_status(self) -> dict:
        """Pings Vast.ai API using the user's LOCAL API key."""
        if not self.vast_api_key:
            return {"status": "error", "message": "VAST_API_KEY environment variable/argument not set."}
        
        try:
            r = requests.get("https://console.vast.ai/api/v1/instances/", headers=self.headers, timeout=10)
            if r.status_code == 200:
                instances = r.json().get('instances', [])
                gpu_action_instances = [
                    i for i in instances 
                    if i.get('label') and any(x in str(i.get('label')).lower() for x in ('gpu-action', 'spotwarp'))
                ]
                active_count = sum(1 for i in gpu_action_instances if i.get('actual_status') == 'running')
                return {"status": "ok", "active_instances": active_count, "instances": gpu_action_instances}
            else:
                return {"status": "error", "message": f"Vast API returned code {r.status_code}: {r.text}"}
        except Exception as e:
            return {"status": "warning", "message": str(e)}

    def start_backup_sync(self, inst_id, host, port):
        """Spawns background loop to sync files from remote container to local PC."""
        if inst_id in self.backup_threads:
            return
        
        stop_event = threading.Event()
        self.stop_events[inst_id] = stop_event
        
        def sync_worker():
            local_backup_dir = os.path.abspath(os.path.join(".", "backups", str(inst_id)))
            os.makedirs(local_backup_dir, exist_ok=True)
            
            if self.use_rsync:
                print(f"\n[Backup] Started background high-speed delta 'rsync' for instance {inst_id} to {local_backup_dir}")
            else:
                print(f"\n[Backup] Started background backup sync ('scp' fallback) for instance {inst_id} to {local_backup_dir}")
            
            null_file = "NUL" if sys.platform == 'win32' else "/dev/null"
            
            while not stop_event.is_set():
                try:
                    if self.use_rsync:
                        cmd = [
                            "rsync",
                            "-az",
                            "-e", f"ssh -p {port} -o StrictHostKeyChecking=no -o UserKnownHostsFile={null_file}",
                            f"root@{host}:/workspace/",
                            local_backup_dir + "/"
                        ]
                    else:
                        cmd = [
                            "scp",
                            "-o", "StrictHostKeyChecking=no",
                            "-o", "UserKnownHostsFile=NUL" if sys.platform == 'win32' else "UserKnownHostsFile=/dev/null",
                            "-P", str(port),
                            "-r",
                            f"root@{host}:/workspace/.",
                            local_backup_dir
                        ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
                except Exception:
                    pass
                
                for _ in range(30):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
            print(f"\n[Backup] Stopped background sync for instance {inst_id}")

        t = threading.Thread(target=sync_worker, daemon=True)
        self.backup_threads[inst_id] = t
        t.start()

    def stop_backup_sync(self, inst_id):
        """Signals and stops the background sync worker thread."""
        if inst_id in self.stop_events:
            self.stop_events[inst_id].set()
            self.backup_threads[inst_id].join(timeout=5)
            del self.stop_events[inst_id]
            del self.backup_threads[inst_id]

    def restore_backup(self, old_inst_id, new_inst_id, new_host, new_port) -> bool:
        """Restores backed-up workspace files to replacement container."""
        old_backup_dir = os.path.abspath(os.path.join(".", "backups", str(old_inst_id)))
        if not os.path.exists(old_backup_dir) or not os.listdir(old_backup_dir):
            print(f"[Restore] No local files found for old instance {old_inst_id}. Skipping migration.")
            return True
            
        null_file = "NUL" if sys.platform == 'win32' else "/dev/null"
        
        if self.use_rsync:
            print(f"[Restore] Migrating cached workspace via high-speed 'rsync' from {old_backup_dir} to {new_host}:{new_port}...")
            cmd = [
                "rsync",
                "-az",
                "-e", f"ssh -p {new_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile={null_file}",
                old_backup_dir + "/",
                f"root@{new_host}:/workspace/"
            ]
        else:
            print(f"[Restore] Migrating cached workspace via 'scp' fallback from {old_backup_dir} to {new_host}:{new_port}...")
            cmd = [
                "scp",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=NUL" if sys.platform == 'win32' else "UserKnownHostsFile=/dev/null",
                "-P", str(new_port),
                "-r",
                os.path.join(old_backup_dir, "."),
                f"root@{new_host}:/workspace/"
            ]
            
        try:
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if r.returncode == 0:
                print("[Restore] SUCCESS: Workload workspace migrated successfully!")
                new_backup_dir = os.path.abspath(os.path.join(".", "backups", str(new_inst_id)))
                if os.path.exists(new_backup_dir):
                    shutil.rmtree(new_backup_dir)
                os.rename(old_backup_dir, new_backup_dir)
                return True
            else:
                print(f"[-] Restore failed with exit code {r.returncode}")
                return False
        except Exception as e:
            print(f"[-] Restore failed with exception: {e}")
            return False

    def execute_resume_command(self, host, port):
        """Executes the training resume command inside the replacement container via SSH."""
        print(f"[Handover] Executing resume command inside replacement: {self.resume_cmd}")
        null_file = "NUL" if sys.platform == 'win32' else "/dev/null"
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=" + null_file,
            "-p", str(port),
            f"root@{host}",
            f"nohup {self.resume_cmd} > /workspace/resume_output.log 2>&1 &"
        ]
        try:
            subprocess.Popen(ssh_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[Handover] Resume command launched successfully in remote background.")
        except Exception as e:
            print(f"[-] Handover failed to launch resume command: {e}")

    def handle_failover(self, evicted_id: int, evicted_host_id: int, evicted_gpu: str):
        """Triggers replacement renting, data restoration, and connection handover."""
        print(f"\n[🚨 FAILOVER TRIGGERED] Instance {evicted_id} (Host {evicted_host_id}) has been evicted!")
        
        if hasattr(self, 'total_failovers'):
            self.total_failovers += 1
            
        self.stop_backup_sync(evicted_id)
        
        print("[*] Finding cheapest alternative RTX 3090 on Vast.ai...")
        q = {"rentable": {"eq": True}, "order": [["dph_total", "asc"]], "limit": 200}
        
        matched_offer = None
        try:
            r_query = requests.get('https://cloud.vast.ai/api/v0/bundles/', params={'q': json.dumps(q)}, headers=self.headers, timeout=15)
            if r_query.status_code == 200:
                offers = r_query.json().get('offers', [])
                for o in offers:
                    name = o.get('gpu_name', '').lower()
                    host_id = o.get('host_id')
                    if '3090' in name and host_id != evicted_host_id:
                        matched_offer = o
                        break
        except Exception:
            pass

        if not matched_offer:
            print("[-] No rentable alternative RTX 3090 found on Vast.ai.")
            # FALLBACK TO RUNPOD
            if self.runpod_api_key:
                print("[*] Falling back to RunPod for cross-cloud replacement...")
                try:
                    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
                    from runpod_connector import RunPodGPUConnector
                    rp_client = RunPodGPUConnector(api_key=self.runpod_api_key)
                    
                    # Request RunPod spot Pod (RTX 3090)
                    res = rp_client.request_gpu_spot_pod(gpu_type="NVIDIA RTX 3090")
                    if res:
                        new_id = f"runpod_{res['pod_id']}"
                        new_host = res['ip']
                        new_port = res['ssh_port']
                        jupyter_host_port = res.get('jupyter_port') or 8080
                        
                        print(f"[+] Successfully rented RunPod replacement! Pod ID: {res['pod_id']}")
                        
                        # Step 1: Migrate files to RunPod container
                        self.restore_backup(evicted_id, new_id, new_host, new_port)
                        
                        # Step 2: Connection verification
                        jupyter_url = f"http://{new_host}:{jupyter_host_port}/api/contents"
                        print(f"[*] Verifying connection to RunPod Jupyter: {jupyter_url}...")
                        
                        connection_success = False
                        for attempt in range(1, 13):
                            try:
                                r_api = requests.get(jupyter_url, timeout=5)
                                if r_api.status_code in (200, 401, 403):
                                    print(f"[+] SUCCESS: RunPod Failover complete! Connected on attempt {attempt}.")
                                    connection_success = True
                                    break
                            except Exception:
                                pass
                            time.sleep(5)
                            
                        # Step 3: Start backup sync for new RunPod instance
                        self.start_backup_sync(new_id, new_host, new_port)
                        
                        # Clean up evicted Vast instance
                        print(f"[*] Cleaning up. Destroying evicted primary Vast instance {evicted_id}...")
                        requests.delete(f"https://console.vast.ai/api/v0/instances/{evicted_id}/", headers=self.headers, timeout=15)
                        
                        if self.resume_cmd:
                            self.execute_resume_command(new_host, new_port)
                        return
                except Exception as rp_err:
                    print(f"[-] RunPod failover fallback failed: {rp_err}")
            return

        try:
            offer_id = matched_offer['id']
            gpu_name = matched_offer['gpu_name']
            price = matched_offer['dph_total']
            print(f"[+] Found Alternative Offer {offer_id}: {gpu_name} at ${price:.3f}/hr on Host {matched_offer.get('host_id')}")

            # Rent the replacement on Vast.ai
            print(f"[*] Renting replacement GPU instance (Offer: {offer_id})...")
            rent_url = f"https://console.vast.ai/api/v0/asks/{offer_id}/"
            payload = {
                "template_hash_id": TEMPLATE_HASH_ID,
                "disk": 20,
                "runtype": "jupyter_ssl",
                "label": "gpu-action-failover-replacement"
            }
            rent_r = requests.put(rent_url, json=payload, headers=self.headers, timeout=15)
            if rent_r.status_code != 200:
                print(f"[-] Replacement rental failed: {rent_r.text}")
                return

            new_id = rent_r.json().get('new_contract') or rent_r.json().get('id')
            print(f"[+] Successfully rented replacement! New Instance ID: {new_id}")

            # Wait for replacement to boot
            print("[*] Waiting for replacement instance {} to run...".format(new_id))
            start_time = time.time()
            replacement_running = False
            replacement_inst = None

            while time.time() - start_time < 300:
                time.sleep(15)
                r_check = requests.get('https://console.vast.ai/api/v1/instances/', headers=self.headers, timeout=15)
                if r_check.status_code == 200:
                    instances = r_check.json().get('instances', [])
                    replacement_inst = next((i for i in instances if i['id'] == new_id), None)
                    if replacement_inst:
                        status = replacement_inst.get('actual_status')
                        cur_state = replacement_inst.get('cur_state')
                        status_msg = replacement_inst.get('status_msg') or ""
                        print(f"  - Status: {status} ({cur_state}) - Msg: {status_msg[:80]}")
                        if status == "running" and cur_state == "running" and "jupyter" in status_msg.lower():
                            replacement_running = True
                            break
                    else:
                        print("  - Instance not listed yet...")
                else:
                    print(f"  - Status check error: {r_check.status_code}")

            if not replacement_running:
                print("[-] Timeout waiting for replacement to boot.")
                return

            new_host = replacement_inst.get("ssh_host")
            new_port = replacement_inst.get("ssh_port")
            token = replacement_inst.get("jupyter_token")
            ports_map = replacement_inst.get("ports", {})
            jupyter_port_list = ports_map.get("8080/tcp", [])
            if not jupyter_port_list:
                print("[-] No mapped Jupyter port found in ports metadata.")
                return

            jupyter_host_port = jupyter_port_list[0].get("HostPort")
            print(f"[+] Replacement is running! Host: {new_host}, Jupyter Port: {jupyter_host_port}")

            # Step 1: Migrate files to new container BEFORE checking connection
            self.restore_backup(evicted_id, new_id, new_host, new_port)

            # Step 2: Connection verification
            base_path = ""
            match = re.search(r'ssh(\d+)\.vast\.ai', new_host)
            if match:
                ssh_idx = match.group(1)
                base_path = f"/jm/{ssh_idx}/{new_port}"

            jupyter_url = f"http://{new_host}:{jupyter_host_port}{base_path}/api/contents"
            print(f"[*] Verifying connection to {jupyter_url}...")

            connection_success = False
            for attempt in range(1, 13):
                try:
                    r_api = requests.get(jupyter_url, headers={"Authorization": f"token {token}"}, verify=False, timeout=5)
                    if r_api.status_code == 200:
                        print(f"[+] SUCCESS: Failover complete! Connected on attempt {attempt}.")
                        connection_success = True
                        break
                except Exception:
                    pass
                time.sleep(5)

            if not connection_success:
                print("[-] Port verification failed after 12 attempts.")

            # Step 3: Start backup loop for the new replacement instance
            self.start_backup_sync(new_id, new_host, new_port)

            # Clean up the evicted instance
            print(f"[*] Cleaning up. Destroying evicted primary instance {evicted_id}...")
            r_del = requests.delete(f"https://console.vast.ai/api/v0/instances/{evicted_id}/", headers=self.headers, timeout=15)
            print(f"  - Primary destruction response status: {r_del.status_code}")

            # Step 4: Execute stateful resume command if provided
            if self.resume_cmd:
                self.execute_resume_command(new_host, new_port)

        except Exception as e:
            print(f"[-] Failover handler error: {e}")

    def start_reporting_loop(self):
        """Starts a background thread to periodically report daemon status to the central server."""
        self.reporting_stop_event = threading.Event()
        self.total_failovers = getattr(self, 'total_failovers', 0)
        self.saved_dollars = 0.0
        self.saved_percentage = 70
        
        def report_worker():
            # Estimate savings incremental per tick (30s)
            # Spot instance average: $0.22/hr. Equivalent Dedicated instance: $0.90/hr.
            # Saved = $0.68/hr per active instance.
            # 30 seconds is 1/120 of an hour.
            # Saved per instance per tick = 0.68 / 120 = 0.00567
            tick_seconds = 30
            
            while not self.reporting_stop_event.is_set():
                try:
                    active_count = len(self.tracked_instances)
                    if active_count > 0:
                        savings_per_tick = (0.68 / (3600 / tick_seconds)) * active_count
                        self.saved_dollars += savings_per_tick
                        
                    payload = {
                        "license_key": self.license_key,
                        "active_instances_count": active_count,
                        "total_failovers": self.total_failovers,
                        "saved_dollars": round(self.saved_dollars, 2),
                        "saved_percentage": self.saved_percentage
                    }
                    requests.post(
                        f"{CENTRAL_SERVER}/api/v1/update_status",
                        json=payload,
                        headers={"User-Agent": "SpotWarp-Guard/3.0"},
                        timeout=5
                    )
                except Exception:
                    pass
                
                for _ in range(tick_seconds):
                    if self.reporting_stop_event.is_set():
                        break
                    time.sleep(1)
                    
        self.reporting_thread = threading.Thread(target=report_worker, daemon=True)
        self.reporting_thread.start()

    def run_guard_loop(self):
        """Main Failover Guard loop: Monitored 24/7 on client machine."""
        print("==================================================")
        print("⚡ SpotWarp: Spot-Instance Failover Guard v3.0")
        print("==================================================")
        print("Security Guarantee: Your API keys stay 100% local.")
        print("==================================================")
        
        if self.use_rsync:
            print("[SpotWarp Guard] High-speed delta 'rsync' ENABLED (Delta sync ready).")
        else:
            print("[SpotWarp Guard] Local 'rsync' not detected. Defaulting to 'scp' fallback.")
        print("==================================================")
        
        if not self.verify_license():
            print("❌ Invalid license. Please subscribe or start a 14-day trial at https://spotwarp.com")
            sys.exit(1)

        print("[SpotWarp Guard] Failover Guard is now ACTIVE. Monitoring Spot instances...")
        
        # Start background reporting loop
        self.start_reporting_loop()
        
        res = self.check_vast_status()
        if res.get("status") == "ok":
            for inst in res.get("instances", []):
                inst_id = inst['id']
                host = inst.get('ssh_host')
                port = inst.get('ssh_port')
                host_id = inst.get('host_id')
                self.tracked_instances[inst_id] = (host, port, host_id)
                print(f"[Tracked] Monitoring active instance: {inst_id} (Host {host_id})")
                self.start_backup_sync(inst_id, host, port)

        try:
            while True:
                time.sleep(10)
                res = self.check_vast_status()
                if res.get("status") == "ok":
                    current_instances = res.get("instances", [])
                    
                    for tracked_id, (host, port, host_id) in list(self.tracked_instances.items()):
                        matching_inst = next((i for i in current_instances if i['id'] == tracked_id), None)
                        if not matching_inst or matching_inst.get('actual_status') != 'running':
                            gpu_name = matching_inst.get('gpu_name', 'Unknown') if matching_inst else 'Unknown'
                            self.handle_failover(tracked_id, host_id, gpu_name)
                            del self.tracked_instances[tracked_id]

                    for inst in current_instances:
                        inst_id = inst['id']
                        if inst_id not in self.tracked_instances and inst.get('actual_status') == 'running':
                            host = inst.get('ssh_host')
                            port = inst.get('ssh_port')
                            self.tracked_instances[inst_id] = (host, port, inst.get('host_id'))
                            print(f"\n[Tracked] Found new active instance: {inst_id} (Host {inst.get('host_id')})")
                            self.start_backup_sync(inst_id, host, port)

                    print(f"[{time.strftime('%H:%M:%S')}] Guard Status: Healthy. Monitoring {len(self.tracked_instances)} instances.", end="\r")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Warning: {res.get('message')}", end="\r")

        except KeyboardInterrupt:
            print("\n[SpotWarp Guard] Stopping all sync worker threads...")
            if hasattr(self, 'reporting_stop_event'):
                self.reporting_stop_event.set()
            for inst_id in list(self.stop_events.keys()):
                self.stop_backup_sync(inst_id)
            if hasattr(self, 'reporting_thread') and self.reporting_thread:
                self.reporting_thread.join(timeout=3)
            print("[SpotWarp Guard] Guard daemon stopped gracefully.")

def main():
    parser = argparse.ArgumentParser(description="SpotWarp: Spot-Instance Failover Guard Agent")
    parser.add_argument("command", choices=["start"], help="Action to perform (e.g. start)")
    parser.add_argument("--license-key", default=os.getenv("SPOTWARP_LICENSE", "TRIAL_LOCAL_PASS"), help="Your SpotWarp license key")
    parser.add_argument("--vast-api-key", default=os.getenv("VAST_API_KEY", ""), help="Your Vast.ai API key")
    parser.add_argument("--runpod-api-key", default=os.getenv("RUNPOD_API_KEY", ""), help="Your RunPod API key")
    parser.add_argument("--resume-cmd", default=None, help="The training command to execute inside the replacement container upon failover")
    
    args = parser.parse_args()
    
    if args.command == "start":
        guard = GpuActionGuard(
            license_key=args.license_key, 
            vast_api_key=args.vast_api_key,
            runpod_api_key=args.runpod_api_key,
            resume_cmd=args.resume_cmd
        )
        guard.run_guard_loop()

if __name__ == "__main__":
    main()
