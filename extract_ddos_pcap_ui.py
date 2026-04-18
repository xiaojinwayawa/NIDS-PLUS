import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess

class PCAPExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CIC-IDS2017 周五 DDoS 流量提取工具 (毕设专用)")
        self.root.geometry("650x350")
        self.root.resizable(False, False)
        
        # 默认路径配置
        self.default_input_pcap = r"C:\SpaceB\nids-system\data\pcaps\Friday-WorkingHours.pcap" # 假设原文件在这里
        self.default_output_pcap = r"C:\SpaceB\nids-system\data\pcaps\pure_ddos_test.pcap"
        
        # 界面变量
        self.input_var = tk.StringVar(value=self.default_input_pcap)
        self.output_var = tk.StringVar(value=self.default_output_pcap)
        self.target_ip_var = tk.StringVar(value="192.168.10.50") # CIC-IDS2017 中常见的受害者IP
        
        self.create_widgets()
        
    def create_widgets(self):
        # 标题说明
        ttk.Label(self.root, text="本工具利用 tshark (Wireshark 命令行) 从巨大的原始 PCAP 中", font=("微软雅黑", 10)).pack(pady=(15, 0))
        ttk.Label(self.root, text="提取出纯净的 DDoS 攻击流量，用于 NIDS 演示时快速触发告警。", font=("微软雅黑", 10)).pack(pady=(0, 15))
        
        # 输入文件
        frame_in = ttk.Frame(self.root)
        frame_in.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame_in, text="原始 PCAP 文件:", width=15).pack(side=tk.LEFT)
        ttk.Entry(frame_in, textvariable=self.input_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(frame_in, text="浏览", command=self.browse_input).pack(side=tk.LEFT)
        
        # 输出文件
        frame_out = ttk.Frame(self.root)
        frame_out.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame_out, text="保存提取结果:", width=15).pack(side=tk.LEFT)
        ttk.Entry(frame_out, textvariable=self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(frame_out, text="浏览", command=self.browse_output).pack(side=tk.LEFT)
        
        # 目标IP过滤
        frame_ip = ttk.Frame(self.root)
        frame_ip.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame_ip, text="受害者目标 IP:", width=15).pack(side=tk.LEFT)
        ttk.Entry(frame_ip, textvariable=self.target_ip_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(frame_ip, text="(CIC-IDS2017 周五下午受害者通常是 192.168.10.50)", foreground="gray").pack(side=tk.LEFT)

        # 进度条与状态
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=20, pady=(20, 5))
        
        self.status_var = tk.StringVar(value="准备就绪。请确保电脑已安装 Wireshark 且 tshark 在环境变量中。")
        ttk.Label(self.root, textvariable=self.status_var, font=("微软雅黑", 9)).pack(pady=5)
        
        # 按钮
        self.btn_start = ttk.Button(self.root, text="🚀 开始提取纯攻击流量", command=self.start_extraction, width=25)
        self.btn_start.pack(pady=10)

    def browse_input(self):
        filename = filedialog.askopenfilename(
            title="选择原始 PCAP 文件",
            filetypes=[("PCAP Files", "*.pcap *.pcapng"), ("All Files", "*.*")]
        )
        if filename:
            self.input_var.set(filename)

    def browse_output(self):
        filename = filedialog.asksaveasfilename(
            title="保存提取的 PCAP",
            defaultextension=".pcap",
            filetypes=[("PCAP Files", "*.pcap"), ("All Files", "*.*")]
        )
        if filename:
            self.output_var.set(filename)

    def start_extraction(self):
        in_file = self.input_var.get()
        out_file = self.output_var.get()
        target_ip = self.target_ip_var.get()
        
        if not os.path.exists(in_file):
            messagebox.showerror("错误", f"找不到原始文件:\n{in_file}")
            return
            
        self.btn_start.config(state=tk.DISABLED)
        self.progress_bar.config(mode='indeterminate')
        self.progress_bar.start(15)
        self.status_var.set("正在调用 tshark 过滤庞大的 PCAP，请耐心等待 (可能需要几分钟)...")
        
        # 使用线程避免阻塞 UI
        threading.Thread(target=self.run_tshark, args=(in_file, out_file, target_ip), daemon=True).start()

    def run_tshark(self, in_file, out_file, target_ip):
        try:
            # 过滤规则：目标IP是受害者，且是HTTP流量（LOIC攻击特征），或者只过滤特定时间段
            # 简化版：提取发往受害者的所有高频 TCP 流量
            filter_str = f"ip.dst == {target_ip} and tcp.port == 80"
            
            # 构建 tshark 命令
            cmd = [
                "tshark",
                "-r", in_file,
                "-Y", filter_str,
                "-w", out_file
            ]
            
            # 执行命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            _, stderr_data = process.communicate()
            
            if process.returncode == 0:
                out_size = os.path.getsize(out_file) / (1024 * 1024)
                self.root.after(0, self.extraction_complete, True, f"提取成功！\n文件已保存至: {out_file}\n大小: {out_size:.2f} MB")
            else:
                err_msg = stderr_data.decode('utf-8', errors='ignore')
                if "not recognized as an internal or external command" in err_msg or "找不到" in err_msg:
                    err_msg = "未找到 tshark。请确保电脑已安装 Wireshark，并将其安装目录添加到了系统环境变量 PATH 中。"
                self.root.after(0, self.extraction_complete, False, f"提取失败:\n{err_msg}")
                
        except Exception as e:
            self.root.after(0, self.extraction_complete, False, f"发生异常:\n{str(e)}")

    def extraction_complete(self, success, message):
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate')
        self.progress_var.set(100 if success else 0)
        self.btn_start.config(state=tk.NORMAL)
        self.status_var.set("完成" if success else "失败")
        
        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("错误", message)

if __name__ == "__main__":
    root = tk.Tk()
    # 设置一个简单的样式
    style = ttk.Style()
    style.theme_use('clam')
    app = PCAPExtractorApp(root)
    root.mainloop()