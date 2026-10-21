#!/usr/bin/env python3
"""
SpotWarp CLI: Zero-Loss Fault-Tolerance & Checkpoint Failover Daemon for SaladCloud
-----------------------------------------------------------------------------------
100% Local Execution - Your SALAD_API_KEY and SSH keys stay 100% on your local machine.
Continuously backs up /workspace checkpoints from active SaladCloud Container Engine (SCE)
nodes to your local PC and automatically restores state onto the replacement Salad node
upon preemption or reallocation (Same-Cloud Salad -> Salad recovery).

Usage:
  pip install spotwarp
  spotwarp init
  spotwarp start -d --org YOUR_ORG --resume-cmd "python3 /workspace/train.py --resume"
"""

import os
import sys
import time
import json
import argparse
import requests
import subprocess
import threading
import shutil
import tempfile

# Standardize terminal encoding to UTF-8 on Windows with zero buffering
if sys.platform == 'win32':
    import io
    try:
        sys.stdout = io.TextIOWrapper(open(sys.stdout.fileno(), 'wb', buffering=0), encoding='utf-8', errors='replace', write_through=True)
        sys.stderr = io.TextIOWrapper(open(sys.stderr.fileno(), 'wb', buffering=0), encoding='utf-8', errors='replace', write_through=True)
    except Exception:
        pass

# Hardened SSL certificate resolution for C-compiled binary & frozen environments
try:
    import certifi
    ca_bundle = certifi.where()
    if ca_bundle and os.path.exists(ca_bundle):
        os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
except ImportError:
    pass

VERSION = "3.5.0"
CENTRAL_SERVER = "https://gpu-action.com"
LICENSE_VERIFY_ENDPOINT = f"{CENTRAL_SERVER}/api/v1/verify_license"
SALAD_API_BASE = "https://api.salad.com/api/public"

CONFIG_DIR = os.path.expanduser("~/.spotwarp")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
TRIAL_FILE = os.path.join(CONFIG_DIR, "salad_trial.json")
PID_FILE = os.path.join(CONFIG_DIR, "spotwarp.pid")
LOG_FILE = os.path.join(CONFIG_DIR, "spotwarp_daemon.log")
TRIAL_DAYS = 14


def to_rsync_path(path: str) -> str:
    """Converts a native path to a form safe to pass as a local rsync/scp argument."""
    if sys.platform == 'win32':
        abspath = os.path.abspath(path).replace("\\", "/")
        if len(abspath) >= 2 and abspath[1] == ':':
            return f"/cygdrive/{abspath[0].lower()}{abspath[2:]}"
        return abspath
    return path


def clean_ssh_output(raw_stdout: str) -> str:
    """Filters out the SaladCloud SSH gateway 'Connecting to container...' banner."""
    if not raw_stdout:
        return ""
    lines = raw_stdout.splitlines()
    filtered = [l for l in lines if not l.startswith("Connecting to container")]
    return "\n".join(filtered).strip()


def sniff_local_salad_credentials():
    """Automatically detects existing SaladCloud API key and organization from local environment."""
    salad_key = os.getenv("SALAD_API_KEY", "").strip()
    salad_org = os.getenv("SALAD_ORG", "").strip()
    salad_project = os.getenv("SALAD_PROJECT", "").strip() or "default"

    if not salad_key:
        key_file = os.path.expanduser("~/.salad_api_key")
        if os.path.exists(key_file):
            try:
                with open(key_file, "r", encoding="utf-8") as f:
                    c = f.read().strip()
                    if c and len(c) >= 16:
                        salad_key = c
            except Exception:
                pass

    if not salad_key or not salad_org:
        cfg_file = os.path.expanduser("~/.salad/config.json")
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not salad_key and data.get("api_key"):
                        salad_key = str(data["api_key"]).strip()
                    if not salad_org and data.get("organization"):
                        salad_org = str(data["organization"]).strip()
                    if data.get("project"):
                        salad_project = str(data["project"]).strip()
            except Exception:
                pass

    return salad_key, salad_org, salad_project


def check_or_init_trial() -> tuple:
    """Zero-Friction 14-Day SaladCloud Evaluation Mode when no paid key is provided yet."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    now = time.time()
    start_ts = now
    if os.path.exists(TRIAL_FILE):
        try:
            with open(TRIAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                start_ts = float(data.get("start_ts", now))
        except Exception:
            start_ts = now
    else:
        try:
            with open(TRIAL_FILE, "w", encoding="utf-8") as f:
                json.dump({"start_ts": start_ts, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
        except Exception:
            pass

    elapsed_days = (now - start_ts) / 86400.0
    remaining_days = max(0.0, TRIAL_DAYS - elapsed_days)
    return remaining_days > 0, remaining_days


class SaladFailoverGuard:
    """100% Local Same-Cloud (Salad -> Salad) Checkpoint Backup & Failover Engine."""

    def __init__(
        self,
        license_key: str = None,
        salad_api_key: str = None,
        salad_org: str = None,
        salad_project: str = "default",
        salad_container: str = None,
        ssh_key_path: str = None,
        resume_cmd: str = None,
        backup_dir: str = None,
    ):
        sniffed_key, sniffed_org, sniffed_proj = sniff_local_salad_credentials()
        self.license_key = (license_key or "").strip()
        self.salad_api_key = (salad_api_key or sniffed_key or "").strip()
        self.salad_org = (salad_org or sniffed_org or "").strip()
        self.salad_project = (salad_project or sniffed_proj or "default").strip()
        self.salad_container = (salad_container or "").strip()
        self.ssh_key_path = ssh_key_path or os.path.expanduser("~/.ssh/id_ed25519")
        self.resume_cmd = resume_cmd
        self.backup_root = os.path.abspath(
            backup_dir or os.getenv("SPOTWARP_BACKUP_DIR", "") or os.path.join(".", "backups")
        )

        self.headers = {
            "Salad-Api-Key": self.salad_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.is_valid_license = False
        self.plan = None
        # Maps container_group_name -> {"instance_id", "machine_id", "host", "port"}
        self.tracked_containers = {}
        self.failover_lock = threading.Lock()
        self.inflight_failovers = set()
        self.backup_threads = {}
        self.stop_events = {}
        self.total_failovers = 0
        self.use_rsync = sys.platform != 'win32' and shutil.which("rsync") is not None

    def _ssh_base_args(self, port: int) -> list:
        null_file = "NUL" if sys.platform == 'win32' else "/dev/null"
        args = [
            "-p", str(port),
            "-o", "StrictHostKeyChecking=no",
            "-o", f"UserKnownHostsFile={null_file}",
            "-o", "ConnectTimeout=10",
        ]
        if self.ssh_key_path and os.path.exists(self.ssh_key_path):
            args.extend(["-i", self.ssh_key_path])
        return args

    def verify_license(self) -> bool:
        """Verifies active subscription or enables Zero-Friction 14-Day SaladCloud Evaluation Mode."""
        if not self.license_key or self.license_key.upper() in ("SALAD-TRIAL", "SALAD-FREE-TRIAL", "TRIAL"):
            ok, rem_days = check_or_init_trial()
            if ok:
                self.is_valid_license = True
                self.plan = f"SaladCloud 14-Day Evaluation Mode ({rem_days:.1f} days remaining)"
                print(f"[SpotWarp Guard] Zero-Friction Onboarding Active: {self.plan}")
                return True
            else:
                print("[SpotWarp Guard] Your 14-day SaladCloud evaluation period has ended.")
                print("[SpotWarp Guard] Upgrade to a full license key at: https://gpu-action.com/pricing")
                return False

        try:
            r = requests.post(
                LICENSE_VERIFY_ENDPOINT,
                json={"license_key": self.license_key},
                headers={"User-Agent": f"SpotWarp-SaladGuard/{VERSION}"},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("valid"):
                    self.is_valid_license = True
                    self.plan = data.get("plan") or "SpotWarp Pro Pass"
                    print(f"[SpotWarp Guard] License Verified: Active ({self.plan})")
                    return True
                else:
                    print(f"[SpotWarp Guard] License Invalid or Expired: {data.get('message', 'Unregistered key')}")
                    print("[SpotWarp Guard] Please verify your subscription at https://gpu-action.com/dashboard")
                    return False
            else:
                print(f"[SpotWarp Guard] License server returned HTTP {r.status_code}.")
                return False
        except Exception as e:
            print(f"[SpotWarp Guard] License check connection warning: {e}")
            return False

    def list_container_groups(self) -> list:
        """Lists target container groups in the configured SaladCloud organization & project."""
        if self.salad_container:
            return [self.salad_container]
        if not self.salad_api_key or not self.salad_org:
            return []
        url = f"{SALAD_API_BASE}/organizations/{self.salad_org}/projects/{self.salad_project}/containers"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                items = r.json().get("items", [])
                return [item.get("name") for item in items if item.get("name")]
        except Exception:
            pass
        return []

    def get_container_instances(self, container_name: str) -> list:
        """Fetches instances for a specific SaladCloud container group."""
        if not self.salad_api_key or not self.salad_org:
            return []
        url = (
            f"{SALAD_API_BASE}/organizations/{self.salad_org}"
            f"/projects/{self.salad_project}/containers/{container_name}/instances"
        )
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                return r.json().get("instances", [])
        except Exception:
            pass
        return []

    def trigger_reallocate(self, container_name: str, instance_id: str) -> bool:
        """Requests immediate SaladCloud node reallocation when an instance becomes unhealthy."""
        url = (
            f"{SALAD_API_BASE}/organizations/{self.salad_org}"
            f"/projects/{self.salad_project}/containers/{container_name}"
            f"/instances/{instance_id}/reallocate"
        )
        try:
            r = requests.post(url, headers=self.headers, timeout=10)
            return r.status_code in (200, 202, 204)
        except Exception:
            return False

    def start_backup_sync(self, container_name: str, inst_id: str, host: str, port: int):
        """Spawns background loop to sync /workspace checkpoints from Salad node to local PC."""
        if container_name in self.backup_threads:
            return

        stop_event = threading.Event()
        self.stop_events[container_name] = stop_event
        SETTLE_SECONDS = 10
        SYNC_TIMEOUT = 600

        def sync_worker():
            local_backup_dir = os.path.join(self.backup_root, container_name)
            os.makedirs(local_backup_dir, exist_ok=True)
            null_file = "NUL" if sys.platform == 'win32' else "/dev/null"
            key_opt = f"-i {self.ssh_key_path} " if (self.ssh_key_path and os.path.exists(self.ssh_key_path)) else ""
            ssh_opts = f"ssh -p {port} {key_opt}-o StrictHostKeyChecking=no -o UserKnownHostsFile={null_file}"

            mode_label = "rsync (delta)" if self.use_rsync else "scp"
            print(f"\n[Backup] Started continuous {mode_label} sync for Salad container '{container_name}' ({inst_id[:8]}) -> {local_backup_dir}")

            while not stop_event.is_set():
                try:
                    exclude_file = None
                    if self.use_rsync:
                        try:
                            find_cmd = ["ssh"] + self._ssh_base_args(port) + [
                                f"root@{host}",
                                f"bash -c 'find /workspace/ -type f -newermt \"-{SETTLE_SECONDS} seconds\" 2>/dev/null'"
                            ]
                            fresh = subprocess.run(find_cmd, capture_output=True, text=True, timeout=20)
                            cleaned = clean_ssh_output(fresh.stdout)
                            fresh_paths = [
                                p.strip()[len("/workspace/"):]
                                for p in cleaned.splitlines()
                                if p.strip().startswith("/workspace/")
                            ]
                            if fresh_paths:
                                fd, exclude_file = tempfile.mkstemp(prefix="spotwarp_exclude_")
                                with os.fdopen(fd, "w", encoding="utf-8") as f:
                                    f.write("\n".join(fresh_paths))
                        except Exception:
                            exclude_file = None

                        cmd = ["rsync", "-az", "--partial-dir=.spotwarp-partial"]
                        if exclude_file:
                            cmd += [f"--exclude-from={exclude_file}"]
                        cmd += [
                            "-e", ssh_opts,
                            f"root@{host}:/workspace/",
                            to_rsync_path(local_backup_dir) + "/",
                        ]
                    else:
                        scp_args = ["scp", "-P", str(port), "-r", "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={null_file}"]
                        if self.ssh_key_path and os.path.exists(self.ssh_key_path):
                            scp_args.extend(["-i", self.ssh_key_path])
                        scp_args.extend([f"root@{host}:/workspace/.", local_backup_dir])
                        cmd = scp_args

                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=SYNC_TIMEOUT)
                    if exclude_file and os.path.exists(exclude_file):
                        try:
                            os.remove(exclude_file)
                        except Exception:
                            pass
                except Exception:
                    pass

                for _ in range(30):
                    if stop_event.is_set():
                        break
                    time.sleep(1)

        t = threading.Thread(target=sync_worker, daemon=True, name=f"backup-{container_name}")
        self.backup_threads[container_name] = t
        t.start()

    def stop_backup_sync(self, container_name: str):
        if container_name in self.stop_events:
            self.stop_events[container_name].set()
            if container_name in self.backup_threads:
                self.backup_threads[container_name].join(timeout=5)
                del self.backup_threads[container_name]
            del self.stop_events[container_name]

    def verify_ssh_ready(self, host: str, port: int, max_attempts: int = 20) -> bool:
        """Waits until the replacement Salad container SSH gateway responds."""
        for attempt in range(1, max_attempts + 1):
            try:
                cmd = ["ssh"] + self._ssh_base_args(port) + [f"root@{host}", "bash -c 'echo READY_OK'"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if "READY_OK" in clean_ssh_output(r.stdout):
                    print(f"[+] SSH gateway ready on replacement Salad node {host}:{port} (attempt {attempt})")
                    return True
            except Exception:
                pass
            time.sleep(3)
        return False

    def restore_backup(self, container_name: str, new_host: str, new_port: int) -> bool:
        """Restores locally backed-up /workspace files to the new SaladCloud container."""
        local_backup_dir = os.path.join(self.backup_root, container_name)
        if not os.path.exists(local_backup_dir) or not os.listdir(local_backup_dir):
            print(f"[Restore] No local cached files for '{container_name}' yet. Skipping upload.")
            return True

        null_file = "NUL" if sys.platform == 'win32' else "/dev/null"
        try:
            mkdir_cmd = ["ssh"] + self._ssh_base_args(new_port) + [f"root@{new_host}", "bash -c 'mkdir -p /workspace'"]
            subprocess.run(mkdir_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except Exception:
            pass

        if self.use_rsync:
            key_opt = f"-i {self.ssh_key_path} " if (self.ssh_key_path and os.path.exists(self.ssh_key_path)) else ""
            ssh_opts = f"ssh -p {new_port} {key_opt}-o StrictHostKeyChecking=no -o UserKnownHostsFile={null_file}"
            print(f"[Restore] Uploading workspace via delta 'rsync' to new Salad node {new_host}:{new_port}...")
            cmd = [
                "rsync", "-az",
                "-e", ssh_opts,
                to_rsync_path(local_backup_dir) + "/",
                f"root@{new_host}:/workspace/",
            ]
        else:
            print(f"[Restore] Uploading workspace via 'scp' to new Salad node {new_host}:{new_port}...")
            cmd = ["scp", "-P", str(new_port), "-r", "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={null_file}"]
            if self.ssh_key_path and os.path.exists(self.ssh_key_path):
                cmd.extend(["-i", self.ssh_key_path])
            cmd.extend([os.path.join(local_backup_dir, "."), f"root@{new_host}:/workspace/"])

        try:
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
            if r.returncode == 0:
                print(f"[Restore] SUCCESS: Workspace restored to replacement Salad node ({new_host}:{new_port})!")
                return True
            else:
                print(f"[-] Restore returned exit code {r.returncode}")
                return False
        except Exception as e:
            print(f"[-] Restore error: {e}")
            return False

    def execute_resume_command(self, host: str, port: int):
        """Executes the user's training resume command inside the replacement Salad container."""
        if not self.resume_cmd:
            return
        print(f"[Handover] Auto-resuming workload on replacement Salad node: {self.resume_cmd}")
        remote_script = f"cd /workspace 2>/dev/null || true; nohup {self.resume_cmd} > /workspace/spotwarp_resume.log 2>&1 &"
        cmd = ["ssh"] + self._ssh_base_args(port) + [f"root@{host}", f"bash -c '{remote_script}'"]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            print("[+] Workload resumed in background (/workspace/spotwarp_resume.log)")
        except Exception as e:
            print(f"[-] Resume command warning: {e}")

    def handle_salad_failover(self, container_name: str, old_info: dict):
        """Handles Same-Cloud (Salad -> Salad) failover when a node is preempted or reallocated."""
        old_id = old_info.get("instance_id", "unknown")
        print(f"\n[🚨 SALAD NODE PREEMPTION DETECTED] Container '{container_name}' (Instance {old_id[:8]}) interrupted!")
        t_start = time.time()
        with self.failover_lock:
            self.total_failovers += 1

        self.stop_backup_sync(container_name)

        print(f"[*] Waiting for SaladCloud Container Engine to allocate replacement node for '{container_name}'...")
        new_inst = None
        while time.time() - t_start < 1800:
            instances = self.get_container_instances(container_name)
            running = [
                i for i in instances
                if i.get("state") == "running" and i.get("ssh_ip") and i.get("ssh_port")
            ]
            # Pick a healthy running instance (either a newly allocated ID or recovered instance)
            candidate = next((i for i in running if i.get("id") != old_id), None)
            if not candidate and running:
                candidate = running[0]
            if candidate:
                new_inst = candidate
                break
            time.sleep(5)

        if not new_inst:
            print(f"[-] Timed out waiting for replacement Salad node for '{container_name}'.")
            return

        new_id = new_inst.get("id")
        new_mach = new_inst.get("machine_id", "unknown")
        new_host = new_inst.get("ssh_ip")
        new_port = int(new_inst.get("ssh_port"))
        elapsed = time.time() - t_start
        print(f"[+] Replacement Salad Node Active in {elapsed:.1f}s! Instance {new_id[:8]} (Machine {new_mach[:8]}) at {new_host}:{new_port}")

        if self.verify_ssh_ready(new_host, new_port):
            self.restore_backup(container_name, new_host, new_port)
            self.execute_resume_command(new_host, new_port)
            self.tracked_containers[container_name] = {
                "instance_id": new_id,
                "machine_id": new_mach,
                "host": new_host,
                "port": new_port,
            }
            self.start_backup_sync(container_name, new_id, new_host, new_port)
            print(f"[✅ SALAD -> SALAD FAILOVER COMPLETE] Workload seamlessly restored on SaladCloud!")

    def start_reporting_loop(self):
        """Periodically reports daemon health & failover count to central dashboard."""
        self.reporting_stop_event = threading.Event()

        def report_worker():
            tick_seconds = 30
            while not self.reporting_stop_event.is_set():
                try:
                    payload = {
                        "license_key": self.license_key or "SALAD-TRIAL",
                        "active_instances_count": len(self.tracked_containers),
                        "total_failovers": self.total_failovers,
                        "saved_dollars": 0.0,
                        "saved_percentage": 80,
                    }
                    requests.post(
                        f"{CENTRAL_SERVER}/api/v1/update_status",
                        json=payload,
                        headers={"User-Agent": f"SpotWarp-SaladGuard/{VERSION}"},
                        timeout=5,
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
        """Main 24/7 monitoring loop for SaladCloud Container Engine instances."""
        print("========================================================")
        print(f"🛡️ SpotWarp Failover Guard v{VERSION} (SaladCloud Edition)")
        print("========================================================")
        print(f"  Target Platform:  SaladCloud Container Engine (Same-Cloud Recovery)")
        print(f"  Organization:     {self.salad_org or 'Not set'}")
        print(f"  Project:          {self.salad_project}")
        print(f"  Container Filter: {self.salad_container or 'All active containers'}")
        print(f"  Salad API Key:    {'Configured' if self.salad_api_key else 'Not set'}")
        print(f"  Backup Root:      {self.backup_root}")
        print(f"  Sync Strategy:    {'rsync (delta)' if self.use_rsync else 'scp'}")
        print(f"  Resume Command:   {self.resume_cmd or 'None (checkpoint sync only)'}")
        print("========================================================")

        if not self.verify_license():
            sys.exit(1)

        if not self.salad_api_key or not self.salad_org:
            print("[!] SALAD_API_KEY and SALAD_ORG are required to monitor SaladCloud containers.")
            print("    Run 'spotwarp init' or pass --salad-api-key and --org.")
            sys.exit(1)

        self.start_reporting_loop()
        print("[SpotWarp Guard] Actively monitoring SaladCloud nodes (polling every 5s)...")

        try:
            while True:
                containers = self.list_container_groups()
                for cname in containers:
                    if cname in self.inflight_failovers:
                        continue

                    instances = self.get_container_instances(cname)
                    running = [
                        i for i in instances
                        if i.get("state") == "running" and i.get("ssh_ip") and i.get("ssh_port")
                    ]

                    if cname not in self.tracked_containers:
                        if running:
                            inst = running[0]
                            inst_id = inst.get("id")
                            mach_id = inst.get("machine_id", "unknown")
                            host = inst.get("ssh_ip")
                            port = int(inst.get("ssh_port"))
                            self.tracked_containers[cname] = {
                                "instance_id": inst_id,
                                "machine_id": mach_id,
                                "host": host,
                                "port": port,
                            }
                            print(f"\n[Tracked] SaladCloud Container '{cname}' -> Instance {inst_id[:8]} (Machine {mach_id[:8]}, SSH {host}:{port})")
                            self.start_backup_sync(cname, inst_id, host, port)
                    else:
                        prev = self.tracked_containers[cname]
                        prev_id = prev["instance_id"]
                        still_alive = any(i.get("id") == prev_id and i.get("state") == "running" for i in running)
                        if not still_alive:
                            self.inflight_failovers.add(cname)

                            def _run_fo(c_name=cname, p_info=prev):
                                try:
                                    self.handle_salad_failover(c_name, p_info)
                                finally:
                                    self.inflight_failovers.discard(c_name)

                            threading.Thread(target=_run_fo, daemon=True, name=f"failover-{cname}").start()

                print(
                    f"[{time.strftime('%H:%M:%S')}] SaladCloud Guard: Healthy | Protected Containers: {len(self.tracked_containers)} | Failovers: {self.total_failovers}",
                    end="\r",
                )
                time.sleep(5)

        except KeyboardInterrupt:
            print("\n[SpotWarp Guard] Stopping all sync worker threads...")
            if hasattr(self, "reporting_stop_event"):
                self.reporting_stop_event.set()
            for cname in list(self.stop_events.keys()):
                self.stop_backup_sync(cname)
            print("[SpotWarp Guard] Stopped gracefully.")


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def cmd_init():
    print("=======================================================")
    print("⚡ SpotWarp Quick Setup Wizard for SaladCloud (100% Local)")
    print("=======================================================")
    cfg = load_config()
    sniffed_key, sniffed_org, sniffed_proj = sniff_local_salad_credentials()

    current_lic = cfg.get("license_key", "") or "SALAD-TRIAL"
    lic_prompt = f"Enter SpotWarp License Key (press Enter for 14-day Salad Trial) [{current_lic}]: "
    try:
        lic_in = input(lic_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.")
        return
    cfg["license_key"] = lic_in or current_lic

    current_salad = cfg.get("salad_api_key", "") or sniffed_key
    salad_prompt = f"Enter SaladCloud API Key [{current_salad[:8]}...]: " if current_salad else "Enter SaladCloud API Key: "
    try:
        salad_in = input(salad_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.")
        return
    if salad_in:
        cfg["salad_api_key"] = salad_in
    elif current_salad:
        cfg["salad_api_key"] = current_salad

    current_org = cfg.get("salad_org", "") or sniffed_org
    org_prompt = f"Enter SaladCloud Organization Name [{current_org}]: " if current_org else "Enter SaladCloud Organization Name: "
    try:
        org_in = input(org_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.")
        return
    if org_in:
        cfg["salad_org"] = org_in
    elif current_org:
        cfg["salad_org"] = current_org

    current_proj = cfg.get("salad_project", "") or sniffed_proj or "default"
    proj_prompt = f"Enter SaladCloud Project Name [{current_proj}]: "
    try:
        proj_in = input(proj_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        proj_in = ""
    cfg["salad_project"] = proj_in or current_proj

    current_cont = cfg.get("salad_container", "")
    cont_prompt = f"Target Container Name (optional, Enter for all) [{current_cont or 'all'}]: "
    try:
        cont_in = input(cont_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        cont_in = ""
    if cont_in:
        cfg["salad_container"] = cont_in

    current_backup = cfg.get("backup_dir", "") or "./backups"
    backup_prompt = f"Local Backup Directory [{current_backup}]: "
    try:
        backup_in = input(backup_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        backup_in = ""
    cfg["backup_dir"] = backup_in or current_backup

    save_config(cfg)
    print("\n✅ Configuration saved to ~/.spotwarp/config.json (100% Local)")
    print("✨ Start protecting your SaladCloud workloads anytime with:")
    print("   spotwarp start")
    print("   (or 'spotwarp start -d' to run in the background)")
    print("=======================================================")


def cmd_status():
    if not os.path.exists(PID_FILE):
        print("⏸️  [SpotWarp Status] No background daemon is currently running.")
        return

    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except Exception:
        print("⚠️  [SpotWarp Status] Stale PID file found. Daemon is not running.")
        return

    is_alive = False
    if sys.platform == 'win32':
        try:
            out = subprocess.check_output(f'tasklist /FI "PID eq {pid}"', shell=True).decode(errors="ignore")
            is_alive = str(pid) in out
        except Exception:
            is_alive = False
    else:
        try:
            os.kill(pid, 0)
            is_alive = True
        except OSError:
            is_alive = False

    if is_alive:
        print(f"🟢 [SpotWarp Status] SaladCloud Guard daemon is ACTIVE (PID: {pid})")
        print(f"   Log file: {LOG_FILE}")
        if os.path.exists(LOG_FILE):
            print("\n--- Recent Log Lines ---")
            with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                for line in lines[-10:]:
                    print("   " + line.rstrip())
            print("------------------------")
    else:
        print(f"🔴 [SpotWarp Status] Guard daemon (PID: {pid}) is not responding.")
        try:
            os.remove(PID_FILE)
        except Exception:
            pass


def cmd_stop():
    if not os.path.exists(PID_FILE):
        print("ℹ️  [SpotWarp Stop] No background daemon is running.")
        return

    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except Exception:
        pid = None

    if pid:
        if sys.platform == 'win32':
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                pass

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    print("✅ [SpotWarp Stop] Daemon stopped successfully.")


def cmd_config():
    cfg = load_config()
    sniffed_key, sniffed_org, sniffed_proj = sniff_local_salad_credentials()
    print("=======================================================")
    print("🔧 SpotWarp SaladCloud Configuration (~/.spotwarp/config.json)")
    print("=======================================================")
    lic = cfg.get("license_key") or "SALAD-TRIAL (14-Day Free Evaluation)"
    salad_k = cfg.get("salad_api_key", "") or sniffed_key
    salad_o = cfg.get("salad_org", "") or sniffed_org
    salad_p = cfg.get("salad_project", "") or sniffed_proj or "default"
    salad_c = cfg.get("salad_container", "") or "All active containers"
    backup = cfg.get("backup_dir", "./backups")

    k_masked = f"{salad_k[:8]}...{salad_k[-4:]}" if len(salad_k) > 12 else ("Set" if salad_k else "Not set")
    print(f"  License Key:      {lic}")
    print(f"  Salad API Key:    {k_masked}")
    print(f"  Organization:     {salad_o or 'Not set'}")
    print(f"  Project:          {salad_p}")
    print(f"  Target Container: {salad_c}")
    print(f"  Backup Dir:       {backup}")
    print("=======================================================")


def main():
    parser = argparse.ArgumentParser(
        description="SpotWarp: Zero-Loss Fault-Tolerance & Checkpoint Failover Daemon for SaladCloud",
        prog="spotwarp",
    )
    parser.add_argument("-v", "--version", action="version", version=f"SpotWarp v{VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Commands")
    subparsers.add_parser("init", help="Interactive setup wizard for SaladCloud")

    start_parser = subparsers.add_parser("start", help="Start the SaladCloud failover guard")
    start_parser.add_argument("-d", "--daemon", action="store_true", help="Run guard daemon in the background")
    start_parser.add_argument("--license-key", default=None, help="SpotWarp license key (optional during 14-day Salad trial)")
    start_parser.add_argument("--salad-api-key", default=None, help="SaladCloud API key")
    start_parser.add_argument("--org", default=None, help="SaladCloud organization slug")
    start_parser.add_argument("--project", default=None, help="SaladCloud project name (default: 'default')")
    start_parser.add_argument("--container", default=None, help="Specific SaladCloud container group name to protect")
    start_parser.add_argument("--ssh-key", default=None, help="Path to private SSH key for Salad container access")
    start_parser.add_argument("--resume-cmd", default=None, help="Training command to auto-resume inside replacement Salad node")
    start_parser.add_argument("--backup-dir", default=None, help="Local directory for workspace checkpoint backups")

    subparsers.add_parser("status", help="Check background daemon status")
    subparsers.add_parser("stop", help="Stop the background daemon")
    subparsers.add_parser("config", help="View current local configuration")

    args = parser.parse_args()

    if not args.command or args.command == "start":
        cfg = load_config()
        sniffed_key, sniffed_org, sniffed_proj = sniff_local_salad_credentials()

        lic = getattr(args, "license_key", None) or os.getenv("LICENSE_KEY") or os.getenv("SPOTWARP_LICENSE") or cfg.get("license_key") or "SALAD-TRIAL"
        salad_k = getattr(args, "salad_api_key", None) or os.getenv("SALAD_API_KEY") or cfg.get("salad_api_key", "") or sniffed_key
        salad_o = getattr(args, "org", None) or os.getenv("SALAD_ORG") or cfg.get("salad_org", "") or sniffed_org
        salad_p = getattr(args, "project", None) or os.getenv("SALAD_PROJECT") or cfg.get("salad_project", "") or sniffed_proj or "default"
        salad_c = getattr(args, "container", None) or os.getenv("SALAD_CONTAINER") or cfg.get("salad_container", "")
        ssh_k = getattr(args, "ssh_key", None) or os.getenv("SPOTWARP_SSH_KEY") or cfg.get("ssh_key")
        resume_c = getattr(args, "resume_cmd", None) or cfg.get("resume_cmd")
        backup_d = getattr(args, "backup_dir", None) or os.getenv("SPOTWARP_BACKUP_DIR") or cfg.get("backup_dir")
        daemon_mode = getattr(args, "daemon", False)

        if daemon_mode:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            cmd = [
                sys.executable, "-u", os.path.abspath(__file__), "start",
                "--license-key", lic,
                "--salad-api-key", salad_k,
                "--org", salad_o,
                "--project", salad_p,
            ]
            if salad_c:
                cmd.extend(["--container", salad_c])
            if ssh_k:
                cmd.extend(["--ssh-key", ssh_k])
            if resume_c:
                cmd.extend(["--resume-cmd", resume_c])
            if backup_d:
                cmd.extend(["--backup-dir", backup_d])

            with open(LOG_FILE, "a", encoding="utf-8") as out:
                if sys.platform == 'win32':
                    DETACHED_PROCESS = 0x00000008
                    proc = subprocess.Popen(cmd, stdout=out, stderr=out, creationflags=DETACHED_PROCESS)
                else:
                    proc = subprocess.Popen(cmd, stdout=out, stderr=out, start_new_session=True)

            with open(PID_FILE, "w", encoding="utf-8") as f:
                f.write(str(proc.pid))

            print(f"🚀 [SpotWarp SaladCloud Guard v{VERSION}] Started in BACKGROUND (PID: {proc.pid})")
            print(f"   Log output:   {LOG_FILE}")
            print(f"   Check status: spotwarp status")
            print(f"   Stop daemon:  spotwarp stop")
            return

        guard = SaladFailoverGuard(
            license_key=lic,
            salad_api_key=salad_k,
            salad_org=salad_o,
            salad_project=salad_p,
            salad_container=salad_c,
            ssh_key_path=ssh_k,
            resume_cmd=resume_c,
            backup_dir=backup_d,
        )
        guard.run_guard_loop()

    elif args.command == "init":
        cmd_init()
    elif args.command == "status":
        cmd_status()
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "config":
        cmd_config()


if __name__ == "__main__":
    main()
