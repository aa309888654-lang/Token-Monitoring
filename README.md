<p align="center">
  <a href="https://github.com/aa309888654-lang/Token-Monitoring"><img src="https://raw.githubusercontent.com/aa309888654-lang/Token-Monitoring/main/LOGO222.png" width="120" alt="小天 tokens 监控"></a>
</p>

<h1 align="center">小天 tokens 监控</h1>

<p align="center">
  一个 Windows 桌面小工具 —— <b>直接抓本机所有 AI 调用的 token 用量</b>，实时显示生成速度，按模型 / 厂商统计。<br>
  暗色 HUD 界面、跳动曲线，双击即用。
</p>

<p align="center">
  <b>个人 / 企业均可免费使用</b>
</p>

<p align="center">
  <a href="https://github.com/aa309888654-lang/Token-Monitoring/blob/main/shot_main.png"><img src="https://raw.githubusercontent.com/aa309888654-lang/Token-Monitoring/main/shot_main.png" width="800" alt="主界面"></a>
</p>

---

## 它做什么

直接看本机每一条发往 AI 服务的请求，**从 API 返回值里读出真实的 token 用量**。不管是命令行工具、IDE 插件、聊天客户端还是自己写的小脚本，只要走 API 就会被统计到 —— 不需要对方软件支持导出，也不用改任何软件。

- **覆盖 Claude / GPT / Gemini / DeepSeek / GLM / Kimi / Qwen / 豆包 / Grok / 文心 / 混元 / 阶跃 / MiniMax / MiMo / 百川 / 零一万物 / Cohere / Mistral / Meta** 等主流厂商，以及各类 OpenAI 兼容中转站
- 支持 OpenAI（`prompt_tokens` 含缓存，自动拆出 `cached_tokens`）、Anthropic（`input_tokens` 与缓存分列）、Gemini（`usageMetadata`）三种取数口径
- 流式与非流式都支持；拿不到 usage 时按字符估算（中文 ≈ 1.5 字/token），拿到真实值后自动替换
- 只解密 AI 域名；其它网站 HTTPS 原样隧道转发，无感通过
- 退出时自动还原系统代理与环境变量；万一异常退出导致上不了网，双击 `%LOCALAPPDATA%\TokenMon\restore_system_proxy.bat` 即可修复

## 界面

- **实时速度**：大字显示当前 tokens/秒，生成中每 0.2 秒跳动刷新
- **近 5 分钟曲线**：渐变发光填充、峰值虚线、末端脉冲光点
- **今日 / 累计 Tokens**：实时累加
- **按模型统计表**：模型、厂商、请求数、输入、输出、缓存读、缓存写、缓存率、总计、平均 tok/s、最后活动时间；同一模型多工具自动合并
- **三种 CSV 导出**：每日汇总 / 每次调用明细 / 当前模型表
- **直采控制台**：代理状态、根证书状态、调用明细
- **极小模式**：收缩为置顶悬浮小窗，可拖拽缩放

## 使用

### 直接使用（推荐）

1. 在 [Releases](../../releases) 下载 `小天tokens监控.exe`
2. 双击运行

### 命令行

```bash
小天tokens监控.exe                 # 图形界面
小天tokens监控.exe --proxy         # 启动界面并立即开启网络直采
小天tokens监控.exe --proxy-only    # 只启动本地代理，不接管系统设置
小天tokens监控.exe --no-logs       # 只用网络直采，不扫本地日志
小天tokens监控.exe --port 8899     # 指定直采监听端口
小天tokens监控.exe --restore       # 还原系统代理设置后退出
```

### 从源码运行 / 打包

```bash
pip install pyinstaller cryptography
python tokenmon.py            # 直接运行
build.bat                     # 打包为单文件 exe
```

需要 Python 3.10+（本项目在 3.14 验证）。

## 详细文档

完整功能介绍、各客户端覆盖情况、缓存口径说明、回归测试清单、已知边界等，详见 **[完整文档（DOCS.md）](DOCS.md)**。

## 许可

个人与企业均可免费使用。
