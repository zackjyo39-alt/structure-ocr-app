# OpenClaw 免费安全部署全攻略：从零打造你的本地 AI 堡垒

如果你最近在找 **OpenClaw 安装教程**，大概率已经看到一些“打包教程收费”的帖子了。  
但说实话，这套部署并不神秘，只要步骤清晰，每个人都可以自己搭好一个**安全、隔离、可长期运行的 AI 本地环境**。

这篇就是一份**完整可复现 SOP（标准流程）**，从环境搭建到开机自启，不省略任何关键步骤。

目标只有一个：  
👉 让 OpenClaw 运行在一个与你 Mac 主系统**物理隔离**的 Linux 环境里，安全又稳定。

---

## 🏗️ 第一阶段：堡垒建设（创建隔离环境）

我们先给 AI 划一块“独立领土”。

### 1️⃣ 安装 Multipass（虚拟机管理工具）

```bash
brew install --cask multipass
```
安装完成后，它可以让你在 macOS 上快速创建 Ubuntu 虚拟机。
---

### 2️⃣ 创建专用虚拟机    

```bash
multipass launch --name openclaw-sandbox --cpus 2 --memory 4G --disk 20G
```

含义说明：

| 参数            | 作用          |
| ------------- | ----------- |
| `--cpus 2`    | 分配 2 核 CPU  |
| `--memory 4G` | 分配 4GB 内存   |
| `--disk 20G`  | 20GB 独立硬盘空间 |

这台虚拟机就是你的 **AI 沙盒堡垒**。

---

### 3️⃣ 注入 SSH 公钥（免密登录）

```bash
multipass exec openclaw-sandbox -- bash -c "mkdir -p ~/.ssh && echo '$(cat ~/.ssh/id_rsa.pub)' >> ~/.ssh/authorized_keys"
```

这样你之后从 Mac 连进去就不用输密码了。

---

## 🧱 第二阶段：内部装修（安装 OpenClaw）

进入虚拟机内部开始部署。

### 1️⃣ 进入 Ubuntu 虚拟机

```bash
multipass shell openclaw-sandbox
```

你现在已经进入一个完全独立的 Linux 系统。

---

### 2️⃣ 安装基础依赖

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git curl
sudo corepack enable
```

---

### 3️⃣ 下载并安装 OpenClaw

```bash
git clone https://github.com/OpenClaw/OpenClaw.git ~/openclaw
cd ~/openclaw
pnpm install
```

---

### 4️⃣ 初始化配置

```bash
~/.local/bin/openclaw setup
```

到这里，OpenClaw 已经安装完成。

---

## 🔥 第三阶段：点火启动（手动运行）

### 1️⃣ 在虚拟机中启动服务端

```bash
~/.local/bin/openclaw gateway --allow-unconfigured --token 你的密码 --force
```

记住你设置的 token，浏览器登录要用。

---

### 2️⃣ 在 Mac 本机建立 SSH 加密隧道

新开一个 Mac 终端窗口：

```bash
VM_IP=$(multipass info openclaw-sandbox | grep IPv4 | awk '{print $2}')
ssh -N -L 18789:127.0.0.1:18789 ubuntu@$VM_IP
```

---

### 3️⃣ 浏览器访问控制台

```
http://localhost:18789/?token=你的密码
```

成功的话，你已经连上自己的 AI 控制台。

---

## 🔐 这套架构为什么安全？

| 层级       | 作用                                 |
| -------- | ---------------------------------- |
| 系统隔离     | OpenClaw 运行在 Linux VM，不接触 macOS 文件 |
| 网络隔离     | 服务只监听 127.0.0.1                    |
| 加密隧道     | 所有通信走 SSH 加密                       |
| Token 认证 | 即使进隧道，没有口令也无法控制                    |

这不是“本地装个软件”，而是**搭了一座 AI 专用安全堡垒**。

---

## 🚀 一键启动（懒人模式）

把下面这行加入你的 `~/.zshrc`：

```bash
alias claw='VM_IP=$(multipass info openclaw-sandbox | grep IPv4 | awk "{print \$2}") && open "http://localhost:18789/?token=你的密码" && ssh -N -L 18789:127.0.0.1:18789 ubuntu@$VM_IP'
```

以后只要输入：

```bash
claw
```

浏览器自动打开 + 隧道自动建立。

---

## 🛠️ 第四阶段：进阶 —— 设置开机自启（systemd）

让 OpenClaw 在虚拟机里自动后台运行。

### 1️⃣ 创建服务文件

```bash
sudo nano /etc/systemd/system/openclaw.service
```

粘贴：

```ini
[Unit]
Description=OpenClaw Gateway Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/openclaw
ExecStart=/home/ubuntu/.local/bin/openclaw gateway --allow-unconfigured --token YOUR_TOKEN
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

### 2️⃣ 启动并设置开机运行

```bash
sudo systemctl daemon-reload
sudo systemctl enable openclaw
sudo systemctl start openclaw
sudo systemctl status openclaw
```

看到 `active (running)` 就成功了。

---

### 3️⃣ 查看后台日志

```bash
journalctl -u openclaw -f
```

---

## 🧠 现在你拥有的是什么？

你得到的不是一个普通 AI 工具，而是：

✅ 独立系统
✅ 加密通道
✅ 本地控制
✅ 自动运行
✅ 不依赖第三方平台稳定性

很多人在外面卖的“AI 本地部署教程”，本质也就是这套流程。

你现在已经完全掌握。

---

## 🌍 最后一个现实问题：网络稳定性

当你开始接入各种模型 API、浏览网页、调用外部服务时，一个稳定干净的网络环境非常重要。

我自己长期使用的是 **Just My Socks**，优点很实在：

* 老牌服务，稳定多年
* 专线质量好，不容易抽风
* 适合开发者长期使用
* 不用担心小机场突然跑路

需要的话可以看看：
👉 [https://justmysocks.net/members/aff.php?aff=30530](https://justmysocks.net/members/aff.php?aff=30530)

网络稳，AI 才能真正稳。

---

如果后续你想给 OpenClaw 接入更多模型、扩展技能库，或者做自动化任务编排，这套“AI 堡垒”架构都可以长期复用。





Google Gemini (API key)
Provider: google
Auth: GEMINI_API_KEY
Example model: google/gemini-3-pro-preview
CLI: openclaw onboard --auth-choice gemini-api-key





alias claw='VM_IP=$(multipass info openclaw-sandbox | grep IPv4 | awk "{print \$2}") && open "http://localhost:18789/?token=9eLpeXUq.@7kbusTu6KP" && ssh -N -L 18789:127.0.0.1:18789 ubuntu@$VM_IP'






systemctl --user restart openclaw-gateway.service && journalctl --user -u openclaw-gateway.service -n 20











openclaw models add gemini-3-flash-preview \
  --api-key AIzaSyDjVIOaQmCSQGOkMb2nJSBSTny1A4aIxOk \
  --model gemini-3-flash-preview \
  --base-url https://generativelanguage.googleapis.com/v1beta