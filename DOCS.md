# 小天tokens监控

一个 Windows 桌面小工具：**直接抓本机所有 AI 调用的 token 用量**，实时显示生成速度，并按模型 / 厂商统计。深色界面、跳动曲线，双击即用。

## 核心：网络直采（不依赖任何软件的日志）

程序内置一个本地代理，把本机所有程序发往 AI 服务的请求接管过来，**从 API 返回值里直接读出真实 token 用量**。所以不管是命令行工具、IDE 插件、聊天客户端还是自己写的小脚本，只要走 API 就会被统计到——不需要它支持导出、也不用改任何软件。

- **自动识别厂商与模型**：Claude / GPT / Gemini / DeepSeek / GLM / Kimi / Qwen / 豆包 / Grok / 文心 / 混元 / 阶跃 / MiniMax / MiMo / 百川 / 零一万物 / Cohere / Mistral / Meta 等，以及各类 OpenAI 兼容中转站。
- **支持三种取数口径**：OpenAI（`prompt_tokens` 含缓存，自动拆出 `cached_tokens`）、Anthropic（`input_tokens` 与缓存分列）、Gemini（`usageMetadata`）。
- **流式与非流式都支持**：SSE 边转发边统计，实时速度就是真实生成速度；拿不到 usage 时按字符估算（中文≈1.5 字/token），界面标「估算」，拿到真实值后自动替换。
- **只解密 AI 域名**：其它网站的 HTTPS 原样隧道转发，不解密、不解析、无感通过，也不会有证书问题。
- **可完整还原**：程序退出时自动还原系统代理与环境变量；万一异常退出导致上不了网，双击 `%LOCALAPPDATA%\TokenMon\restore_system_proxy.bat` 即可修复。

### 一键开启会做什么

点工具栏上的「直采」按钮 →「一键开启直采」，程序会：

1. 生成一张本地根证书（`%LOCALAPPDATA%\TokenMon\ca\`）；
2. 把根证书加入**当前用户**的「受信任的根证书颁发机构」（无需管理员权限）；
3. 把 Windows 系统代理指向 `127.0.0.1:8898`（启用期间会临时移除 PAC 自动配置脚本，退出时还原）；
4. 写入用户环境变量 `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY` / `NODE_EXTRA_CA_CERTS` / `NODE_USE_ENV_PROXY`，让命令行程序也能走代理。

> 第 2 步 Windows 会弹出安全警告，点「是」即可。命令行程序需**重启**才会读到新的环境变量；浏览器 / Electron 类程序装完证书即可，必要时重启。

## 界面功能

- **实时速度**：大字显示当前 tokens/秒，生成中每 0.2 秒跳动刷新，数字带缓动动画
- **实时曲线**：近 5 分钟生成速度曲线，渐变发光填充、峰值虚线、末端脉冲光点
- **今日 / 累计 Tokens**：输入+输出合计，"本分钟 +N" 实时累加
- **模型活动**：当前正在生成的请求数、模型名、已持续秒数
- **按模型统计表**：模型、厂商、请求数、输入、输出、缓存读、缓存写、缓存率、总计、平均 tok/s、最后活动时间；同一模型来自多个工具时合并成一行；正在活动的模型绿色高亮；输入前带 `≈` 表示其中有估算成分（见下）；可切换 今日 / 累计 视图
- **导出数据**（CSV，三种）：
  - ① **每日使用汇总**——按天 × 模型：日期、请求数、输入/输出/缓存 tokens、总计、生成耗时、平均速度
  - ② **明细记录**——每一次模型调用一行：精确到秒的时间、日期、模型、来源、各类 tokens、耗时、速度
  - ③ **模型统计**——当前表格视图（今日/累计）
- **直采控制台**：工具栏「直采」按钮打开——代理状态、根证书状态、系统代理状态、环境变量状态、抓取计数、最近 80 条调用明细（模型 / 厂商 / 输入 / 输出 / 耗时 / 精确或估算）
- **双风格切换**：右下"简洁风格 / 科幻风格"按钮一键切换 HUD 科幻面板与简洁面板，选择会记住
- **极小模式**：点击"极小"按钮收缩为置顶悬浮小窗，支持拖拽自由缩放，"还原完整界面"一键恢复

## 数据来源

| 来源 | 位置 / 方式 | 口径说明 |
|---|---|---|
| **网络直采** | 本地代理截获所有程序发往 AI 服务的请求/响应，直读 API 返回的 usage | 各厂商字段自动归一，缓存读一律从输入里拆出 |
| ZCode | `~/.zcode/cli/rollout/model-io-*.jsonl` | `inputTokens` **已含** `cacheReadTokens`，会减掉 |
| Claude Code | `~/.claude/projects/**/*.jsonl` | 按 `message.id` 归并（同一次调用会被写多条），`output=0` 的半截记录丢弃 |
| WorkBuddy | `~/.workbuddy/projects/**/*.jsonl` | `input_tokens` **已含** `cache_read_input_tokens`，会减掉 |
| Codex | `~/.codex/sessions/**`、`archived_sessions/**` 的 `rollout-*.jsonl` | 只认 `token_usage_record`，按 `response_id` 去重；`input_tokens` **已含**缓存，输出含 `reasoning_output_tokens` |
| OpenCode | `~/.local/share/opencode/opencode.db`（SQLite） | `tokens.total = input + output + reasoning + cache.read`，所以 input **不含**缓存读，不减 |
| 额外目录 | 工具栏「监控目录…」手动添加 | 按 Claude Code 格式解析 |

### 各客户端是怎么覆盖的

| 客户端 | 走哪条路 | 说明 |
|---|---|---|
| Claude Code | 日志 | `~/.claude/projects` |
| WorkBuddy | 日志 | 内置 CLI 直连 `copilot.tencent.com`，Node 不读系统代理 |
| Codex（含 CC Switch 中转） | 日志 | 它把请求发到本机 `127.0.0.1:xxxx` 的中转，属回环流量，代理管不到 |
| OpenCode | SQLite | 会话存库，20 秒轮询一次增量 |
| Cursor / Trae CN / Kimi / CodeBuddy / 各类中转站 | 网络直采 | 这些客户端不落 usage 日志；它们走系统代理时由直采抓 usage |

**不落 usage 日志、又不走系统代理的程序抓不到**（例如自己设了直连的 Node CLI）。这类可以在直采控制台的「额外域名」里补上它的域名，并给它注入环境变量（`注入环境变量` 按钮会给新开的命令行程序设 `HTTPS_PROXY` + `NODE_EXTRA_CA_CERTS`）。

### 自动识别未知中转

内置域名名单之外，勾选 **「自动识别未知中转」**（默认开）后，代理会对「名字像 AI 服务的陌生域名」或「IP + 非标准端口」**先解密看一眼请求路径**：

- 路径像 `/v1/chat/completions`、`/messages`、`:generateContent` 这类 → 判定为中转，正常记录，之后一直解密
- 不像 → 记下来，以后这个域名直接隧道转发，不再打扰

代价是每个陌生域名第一次访问时会多一次解密（政务 / 教育 / 银行域名和白名单域名已排除）。凭据极其敏感的环境可以关掉它。

### 为什么 WorkBuddy 走日志而不是抓流量

WorkBuddy 的 AI 请求由它内置的 **CodeBuddy CLI（Node 进程）直连 `copilot.tencent.com`**。Node 程序既不读 Windows 系统代理、也不读系统根证书，所以代理那条路对它无效。好在它每个项目、每个会话都会在 `~/.workbuddy/projects/` 下落一份 jsonl 转录，每条模型调用都带 `message.usage`（`input_tokens` / `output_tokens` / `cache_read_input_tokens`），因此直接读转录取数——既不依赖代理，也不会和代理统计重复。

> 所以**同时开启直采和日志扫描不会重复计数**：同一个模型不会既被代理记一遍、又被日志记一遍（WorkBuddy 的域名不在解密名单里，走直采时是原样隧道转发）。其余来源按请求指纹去重。

### 输入口径

表格里的「输入」一律是**不含缓存读的新增输入**，「缓存读」单列，「缓存率」= 缓存读 ÷（输入 + 缓存读）。想让「输入」等于厂商后台那种含缓存的 prompt 总量，把两列相加即可。

## 使用

直接双击 **`小天tokens监控.exe`** 即可。首次启动会扫描全部历史记录（几秒钟），之后增量更新；统计数据持久化在 `%LOCALAPPDATA%\TokenMon\state.json`，重启不丢。

命令行方式：

```
小天tokens监控.exe                 # 图形界面
小天tokens监控.exe --proxy         # 启动界面并立即开启网络直采
小天tokens监控.exe --proxy-only    # 只启动本地代理，不接管系统设置
小天tokens监控.exe --no-logs       # 只用网络直采，不扫本地日志
小天tokens监控.exe --port 8899     # 指定直采监听端口
小天tokens监控.exe --restore       # 还原系统代理设置后退出
python tokenmon.py --selftest      # 命令行自检（扫描历史并打印统计）
python tokenmon.py --demo          # 演示模式（合成数据，不读真实文件、不落盘）
python tokenmon.py --fresh         # 忽略已保存的状态，重新全量扫描
```

### 说明

- **实时速度口径**：正在生成中的请求按该模型近期的平均速度临时估算，真实记录落地后自动替换，因此曲线在生成过程中是连续跳动的。
- **带 `≈` 的输入是估算值**：有些程序走第三方中转时，上游不把输入用量回传给它（日志里 `input_tokens` 恒为 0，例如 Claude Code 配 `gpt-5.6-sol`）。这时用「该会话到这一轮为止已出现的对话文本」按字符估算输入，比记 0 更接近真实（实测约为真值的 0.72 倍，偏保守，因为系统提示词不在日志里）。导出明细里这类记录带 `"est": true`。
- **抓不到数据？** 在控制台里看三件事：代理是否「运行中」、根证书是否「已加入系统信任区」、额外域名里是否需要补充你用的中转站域名（回车生效）。命令行程序记得重启。底栏 `ZCODE / LOG / CLAUDE / WB / CX / OC` 后面的数字是各自扫到的文件数（OC 是 OpenCode 的库，为 1 表示已连上），为 0 说明对应目录不存在。
- **清零统计**只清空数字，文件读取进度会保留，历史不会重复计入。**如果换了取数口径（例如升级版本修正了某来源的算法），历史累计仍是旧值**，需要点一次「清零统计」让它按新口径重算。
- **开机自启**：直采控制台右下角勾「开机自启」，会往 `HKCU\...\Run` 注册一条（不需要管理员权限），取消勾选即删除。也可以自己把快捷方式放进 `shell:startup`。
- **状态/配置文件位置**：`%LOCALAPPDATA%\TokenMon\`（`state.json` 统计与读取进度、`config.json` 界面风格与直采设置、`records.jsonl` 全部请求的明细日志、`ca\` 根证书与站点证书、`restore_system_proxy.bat` 一键还原脚本）。

## 从源码打包

需要 Python 3.10+（本机 3.14 已验证）：

```
pip install pyinstaller cryptography
build.bat
```

产物在 `dist\小天tokens监控.exe`（单文件，无需安装 Python）。

> `cryptography` 只在 HTTPS 解密时使用；若运行环境缺失该库，程序仍可正常启动，只是网络直采不可用（控制台会提示），本地日志扫描不受影响。

## 回归测试

`tests\` 下四个脚本，都是独立可执行的冒烟测试（不是 pytest），跑完自动清理临时目录：

| 脚本 | 覆盖内容 |
|---|---|
| `_workbuddy_test.py` | WorkBuddy 转录解析、ZCode 缓存口径、Claude Code 归并去重、输入估算、明细日志不重复 |
| `_proxy_e2e_test.py` | 本地假 AI 服务 + 真证书 + 真代理：GPT / Claude / Gemini / chunked 解析与直通 |
| `_ui_smoke_test.py` | 厂商识别、usage 提取、表格管线、代理启停、直采面板渲染 |
| `_registry_test.py` | 系统代理 / 环境变量接管与**完整还原**校验（含 PAC） |
| `_screenshot.py` | 截图；加 `--real` 则扫描本机真实日志后再截 |

改动直采或口径相关代码后请全部跑一遍。

## 已知边界

- 只统计**经过本机网络**的 AI 调用；如果某个程序用的是私有协议、或自己设置了不经过系统代理的直连（Node 程序、部分 Electron 应用），需要在那个程序里手动配置代理，或改用其本地日志（WorkBuddy 就走后者）。
- 只对内置识别的 AI 域名解密。用自建 / 小众中转站时，把域名加到「额外域名」里（或勾选「解密所有 HTTPS」）。
- 少数做了证书固定的程序无法解密，代理会跳过它（控制台「解密失败」计数 +1），不影响它正常使用。
- 账面上不可能和厂商后台完全一致：厂商后台通常把缓存读也算进"输入"，且会有重试、失败请求、被中断的流等情况；本工具按「实际拿到 2xx 响应的调用」计数。
