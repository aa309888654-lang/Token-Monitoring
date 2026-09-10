#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小天tokens监控 — 实时监视本机 AI token 用量、生成速度，并按模型 / 厂商统计。

数据来源:
  A. 网络直采(推荐) : 内置本地代理，直接截获本机所有程序发往 AI 服务的 HTTPS
                      请求/响应，从 API 返回值里读取真实 token 用量。不依赖任何
                      软件自己的日志，Claude / GPT / Gemini / DeepSeek / GLM /
                      Kimi / Qwen / 豆包 / Grok … 只要走 API 就会被统计。
  B. 本地日志(可选) : ZCode / Claude Code / 手动添加目录的 .jsonl 记录文件。

用法:
  python tokenmon.py            # 启动图形界面
  python tokenmon.py --proxy    # 启动界面并立即开启网络直采
  python tokenmon.py --selftest # 命令行自检，扫描历史并打印统计
  python tokenmon.py --demo     # 演示模式（合成假数据，验证界面）
"""

import argparse
import csv
import ipaddress
import json
import sqlite3
import math
import os
import queue
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from collections import deque
from datetime import datetime, timedelta
from tkinter import filedialog, font as tkfont, messagebox, simpledialog, ttk

try:
    import winreg
except ImportError:          # 非 Windows 平台仅退化为日志模式
    winreg = None

APP_NAME = "小天tokens监控"
OFFICIAL_SITE = "https://aicgxt.com"
OFFICIAL_CHAT_URL = "https://aicgxt.com/chat"
APP_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAPQklEQVR42u1aa5BcxXX+zum+987MzuyuJCQhg5eHgUokUzYI"
    "sCgCKxkD4hFwILO2oUgCBorguGxsgzEPjwaQDY7BBAoSK6acQGE7Oy7b4Sk7qogF8wivYLDEI2BsMBLWY7Xa3dm5c7v7nPyY"
    "XawFrSQkOamk5qvqmqma6dvd5/GdR1+gjTbaaKONNtpoo4022mijjTb+/0CVoEr/GytTpaJcLvebSkUZ+J/ehBJUeSsC4T+4"
    "QHSKw+quCEGVUFF+e2zrEP39ZuKreeat4+wvBj8DVcJKtVNNsbtT8gTS3t6KXdD1+YM9dzDHmT4//NAqWk7NliWQ7tCjKsq9"
    "AA9UEUCkAH4/rzqu5QoM5tUUfX3h7d/6+gKeHZllQ9ojWfP9KBUOH5/vzS83/Dl796L78JxfoqKMKgkA7BaTqKDCqCzBpod/"
    "N7PY0X0f2WR+gIIswZF/PtORU6bNnfZbAKiOL7zV51SUq0ug45sGAOx98evTY9s1Az7kNDHNZufIxjWX771xkmkDwINDnSav"
    "R4GyFFF8AUJaQ7HrUEj2BDLn0JH8qTbcY/KhPf4ZqgZEYbdZwLzyEuqrUrjs5JGrO/PJ/KGm98pkQtCQL9iDs0buhmqVyuWy"
    "mqmeUS6rqVYpoArMv2jzR1xsz/Bsj3HMByihW3NsghEhKQzN/lbzV64kA0iyHw4SPQ4A8c/emIl8qRzU3aESG6gY8j5TY/4Y"
    "CTcIPAjS8M51d9kCKhXlahX6+WN/t1+xMGOVMkVCwkpMnlWFKZABj4VNR/x9bY9nymVwrUZhMmmCqlWSo87bvCDkc0uCiU6Q"
    "hJAB8AoEVggpvAVCjuE7gTAd8LHAFfxPHafV9MSux6BK9om182HsSSTZyyh1HuXqg1+DC2K6p10G7x4OB8/+0W61gHmrQQBJ"
    "Eo1cmcQ21/DeEzEpAQQihZC1EbMWqwCdsqU7txgbqBLJonPrVY2TK9kY9j6oFw1qiMBKE4auAFQCaVMhoyRaVEPT4xMo4eOj"
    "x+vXOqKvetVnQPQUP7n20+QlwWH7rgWA8PKGCsL6tKX23yuAdof2Lzlhw0FJ3P2cElslISUiZSAw4EkRAOGEuZHV/+Tb/Z2P"
    "lMtqajVIpQJavbqPRgp33Eml3KcaLkiTVb2ByUjFW1KJrJEICBYtCzCAj13wJSVXAoeSBikShb1j9vWxfr/pibOwcKHg6TXT"
    "ARQw/31voKUL2e1RYEL7luuVfGzjMe89QFYB6AR3EwEkSsRQttcCWNQSXsvsTzmzfme+kPvU6JhzamCJiFURTBIZiQCXuRER"
    "vO4zqWsOHRJRDzrjEsUAhWYghQEUWJ863rvQZ/Xw4InOBLBhciRW2pJcd9kCJrT4pcWbDu6ISs8EECkrKwhCgEKDGBjPhACF"
    "ZwROrGlkm0+8/QfdywHgtLNGL08KHUvrzrvMIMpY1UUMzRtqhOyxDOHW4OorX7p15pqJdWdU1r/PFHKLpNN+RvfMHelshlAQ"
    "DR1EIRGnM/ORvLnpK/KR6ddB1YLIb+scu8gBpBZj1cha45wLUAYIIKhGkTUNCVBVoCUQqALKuWt7e1euGBhYGAhjcxVQQEkV"
    "yoZhIkiaNS599pbCje9KiIh0Y3XmGgB3Abir686Rz2OP3DfVEKt4JYXVoWagUuEa/MfaewCshipPZf4AwDuvfQ6XHr/hiFwc"
    "n5a6ICAy4wdVw5bqzZHvhSAZgVUVAMg470OcJPP32uuQPoDU6chXm5lPldiQYYGBSDpWfvKWwo2VinJvRe3bmd+E+aoSKist"
    "VHnz2aWb3NjQ6TDkyRgPgicfPBUS4rh4NYgUtW1bOe9K4ms4f7VlQwJRtLg6xNbCSbb6xrs7z1IK98YRk8h4/FWlEKBMSaVc"
    "fjR/3/f2/FVwze9Ya8haY8JY/cuPfLvzx3MrGlerJANV8u/yWyJFdZEHkaBf48YZM+/2YyNfwuw4Qmc+wrRCQgzDc4qn26c2"
    "LEAfhS1T5F12gf6ymr4ahS8fN3hMPs6fkHovRGS0FdTADIJPLwOARqhfRc6ezMyRqCqY2XsXknzuoAwfPAfAbbCD1zuXu9B7"
    "/8JD3+26obeidqAKt0Ob6SOHfjXZCXRz9OjmmdqV9GhwAoKiK8dk2U6Y7G4TwKq5rUBuTf5awwQEVSWCQkMSRabRbP779Xd3"
    "3VMpa1yt0eoLTxu9tdjR8QXnvVdRKwQKmShxcnm5/OpdtTt63jz+L4aXsZEXtuSWKSu9dwkBAlVyRFdNTVW7iQP6W+mqXHH8"
    "xsUdSe7ohgtBiczEKi4EcTJyGQBgHaRSUXaNwaVjTbeeDbNABUQcgpcoifcKudl/AwCSW3+FuF//EwAMVLfF2qRbHUQ6Xu5O"
    "HjsA+961rxRxes3EfpQIQupzsbX1ZvqDG+6d+eS4m/gK1N4+0DN4/sdHrs6b4i2phjBeN3JwIjDJFxafs2bZ8mXvW79jmddK"
    "e8BgY7I/HwC8AgA3PzD5vwe2MjVUq9luEUCld6WtVslfdfymMwpx92Gj3gclGIUowJw63/QYvgpQmnCT6gBCpaK89t6nv13f"
    "/4MX2jiZ69QHgEyQEKJCNN02Oy8HcHHL97em/fEyulw2+9ePWOFnxPv5SMQXwaFD4buAYknhSgLJA62UWQGG0gEfU5x6cdnP"
    "735qqnC44y6wcKFUeldai3xVAAUpFEAAQi427LX5j9+6Z/Yr/WVwq+RtbXz1atCypw9zWWheKgCJAqE1TJoGgYkvPPmcof0H"
    "qi1hTbV877q5BLIHcGR7yMb7ko17ECc9Gic9yOV6OFfo4aTQ+ix09FCS3wfFaF9VzNhW0sc7pn211SoJ7KFnFpNkXtM7AZFR"
    "UrXGcOrcZvj6UoXSqlrLTSaIrFajUC6rufNHXfePNcdWWGuNqAYFkYgK2yiXUXTthLC2nXZhVD0yDT5V5zPJXKbOZdpsOm00"
    "hcZSQZoK0oYgSwXDToO4QbQ2srMkqISFkM8ufjlJTO6rQaGgtzcqSczsNLvxm/fPfqtWBlcBBUjPPn3dJxYv1mTLrNtRdknm"
    "QxA2EIUKYJupF0TJJ485f+jwCWFNtRNRncl5xJyzOS7YmDuimApRzMUkImVGIGYhJgERRwyXjSEMvz4eCneuGKr0wlSr5K9d"
    "OPTpYkf8gc3eBTVkRFWMNVxPs7VZtuamSkW5thool8HJ0LO5CJ03zclvehHQ59ate5DKZTG1Gj378TPGvht15M8LXnxQsgGi"
    "qpadxNcD+OjWmR8YGIDse6i/zo+YmT7yKgAphCAgcsFS0V6EyEYaAoigyEUk9eZLOPID66YqhHagGFKqAITeVYWCOfAFTuxe"
    "TQR1TOygIc5FZqQ58pkb7u28rVLWeEkNjkB61ikj15c6i5cONdJ7fvDj/KkAcMEFGs2Zg/DIf27YM0m6X1DLRUdC3hI5RpCC"
    "MU0/fMrTy7rum5oQt47krjdPsPvMvl/Iq8QwasVjj7wNG4a/Hg7puhwr1WLR1p9H2/X9AfJfP2bki6VC8ZvD4oI3ZDKIcBTT"
    "mGSvNP1vDr55+YEZtTTFZ584fAXHpatTeEeJjdKQ3pHW3/js8uUHDU9ww7F/NnxVVCxdnfrgvYUVoxISJkfh1eGRX89/5a6D"
    "hudf8FT09LLD3DuapbYXwHqs4uF588xv+6hRWvbbg7DXrMe1wN2BnUqOWGMSiUj9po0fwtFzVm2rIKLttbiv/9ivOm3Y+yWO"
    "7KwmBc3GtR8lkdmcbT7zxvu7v3/uqS+U4uaMT0jUdaVG8T7DmQvesnEkwRQik5IbTZF+w2Vv/cOxcw/c+OCDqwqYfdBqjcze"
    "TkUlIg6sokXLmTYfDI11Z6y+vWdwy0MPbEEFEx3dad/ZfKR05pejGHUGSX0osNVEvM7M2bC5frc/vHga+tWgj8KUxLo97V9/"
    "9NCV3R1d1wyL945gM9LAcWTGQvOZ5LDk8FZHFvxWcf1+QUuLGzCXhDh6fz1kolHEjkM9GP+tEIUfiln/En69rx8YIL+gPNJn"
    "k+K/NH1wYjUSSxCLoB3GZOpeUU6/Uhx7+V/fZQUAuq9Zs4+dMe2iYPFXWpD7tGDPku44Dj5V6eAgBeIsHT0EC6Y9j1qNJ7XO"
    "d0QAE9pfsuCNadNys1/myE5PEeCZKCMEjq0ZdcMnfeOBrgcmiqOJuad87M2eKL/HimDt/k2WegiNk1f8pPPn7y6nKRx6RuP7"
    "UUfuk6nzDhFFYgGxCMgbozGQiXtR1D8sKq8G1kxjnu1z5hDN85GYE5Wykfrrmy4q7lO6c/MCnZZbKjEdJXtGids4vDQs6rpy"
    "e9qfMgwu6YUhkJbstIuLSTzDaQgAkaqGxFiTNtOBbzzQ9UB50uGVymWN712x1+tj2ehfcsTGZdkVK37S+fPFizXZ8kan1Q9U"
    "9sMvnddMm09wbCMf1Im0qmx1XqTpxZjoj2whf74tdlwXFYs32mLhyzaXHE9qSjoKDyjjkp+URs7uetw/+fw5GplE147dHxZ1"
    "XQVVgz7I9giUt3bJsWQAYelHXp0dmfizqRcBiAFVIlJRAWl2+dbCVa1GWQXKP/3pjMdGx0Z/bNLh/kpFeflyZJPDEGm1Cjz3"
    "bx+uZ7ruRJdlD3NiI1GEIBpEmUHMmnmRhveStkYY814aLqiEAIVlpYC//Xi9867hvzYLPvRfSP29zRcHTkdFCYDsyE0Ub+2S"
    "g0Caj2Z9sSOOu4KKb/U64AuRtY2sec/Sn3U92j9uxu+cXwUpoMTmrc91dz+8sZUWb20jJKgor671DKabfnOcT5u3gY3hyBqI"
    "ioj6VicJhkAWIAslCwWTAuq8V0TTu26vv4hppdu07m5rnJicis+d3MQ7bpe2mV1O1r5yFSTXHfVmT8Hu8VpiY3YAhABhoKH+"
    "5Y31wZM6Hp312vhhBbuMCgNVAYADPjl0nC3mr0QSH4Pc+LoAhARCqsGCJGFogSAlwEeAt9kTvln/0ugF0x9+V/vsvQpgIk7/"
    "3REbOrPIHCrk1APwAJIoces3vvaLG577cH3HLjrfw2UolFAGY9yiDjx38Bgq5E4XY49WxgeEuUutgeeAEIVRzelrPi8PeaT9"
    "QxdPf6jVrNg+4e1EJrj1CEHYcQm/t26rGtQm++7+F66dlQGzENs8TC5N8xs3bPha67bn7SbpdkLdzgiA+suTS9PaOHvjD3X4"
    "dwiidy5ooMp+8lXa5KwQ86A7o/X/e6+6VJRR7jdbvCBBaKONNtpoo4022mijjTbaaKONncZ/A2PbeY2VVI2eAAAAAElFTkSu"
    "QmCC"
)
APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "TokenMon")
STATE_FILE = os.path.join(APP_DIR, "state.json")
LOG_FILE = os.path.join(APP_DIR, "records.jsonl")   # 每次请求的明细日志
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

# ---- 网络直采（本地代理，直读 API 返回的 token 用量）----
PROXY_PORT_DEFAULT = 8898
PROXY_HOST = "127.0.0.1"
CA_DIR = os.path.join(APP_DIR, "ca")
CA_CERT_FILE = os.path.join(CA_DIR, "tokenmon-ca.pem")
CA_KEY_FILE = os.path.join(CA_DIR, "tokenmon-ca.key")
LEAF_DIR = os.path.join(CA_DIR, "leaf")
PROXY_BACKUP_FILE = os.path.join(APP_DIR, "proxy_backup.json")
RESTORE_BAT = os.path.join(APP_DIR, "restore_system_proxy.bat")
SNIFF_MAX_BYTES = 32 * 1024 * 1024   # 单个响应最多缓存多少字节用于解析 usage
RELAY_CHUNK = 65536

# 需要解密的 AI 服务主机（域名包含即命中）；用户还可以在界面里追加
AI_HOST_KEYS = (
    "openai.com", "chatgpt.com", "oaiusercontent", "anthropic.com", "claude.ai",
    "generativelanguage.googleapis.com", "aiplatform.googleapis.com",
    "makersuite.google.com", "deepseek.com", "bigmodel.cn", "zhipuai.cn",
    "dashscope.aliyuncs.com", "aliyuncs.com", "moonshot.cn", "moonshot.ai",
    "volces.com", "volcengineapi.com", "api.x.ai", "mistral.ai", "groq.com",
    "together.xyz", "siliconflow.cn", "minimax.chat", "minimaxi.com",
    "stepfun.com", "baichuan-ai.com", "lingyiwanwu.com", "01.ai",
    "perplexity.ai", "cohere.ai", "cohere.com", "openrouter.ai",
    "baidubce.com", "xf-yun.com", "tencentcloudapi.com", "hunyuan.cloud.tencent.com",
    "modelscope.cn", "codeqwen.ai", "portal.qwen.ai", "chat.qwen.ai",
    "novita.ai", "fireworks.ai", "hyperbolic.xyz", "aimlapi.com", "aihorde.net",
    "302.ai", "gptsapi.net", "ofox.ai", "cometapi.com", "dmxapi.com",
    "apiyi.com", "ohmygpt.com", "ablai.top", "ppio.com", "sophnet.com",
    "inflyai.com", "ikuncode.cc", "yescode.org", "v3.codes", "aihubmix.com",
    "oneapi.top", "api.gemai.cc", "klingai.com", "vidu.com", "vidu.cn",
    "jimeng.jianying.com", "doubao.com", "api.tbox.cn", "api.xty.app",
    "edgefn.net", "gptgod.online", "chatanywhere.tech", "zhihu.com",
    "sensenova.cn", "shanghai-ai.com", "minimax.io", "api.intern-ai.org.cn",
    # ---- 国内 IDE / 客户端自己的 AI 服务（Trae CN、Cursor、CodeBuddy、Kimi、MiniMax…）
    "trae.ai", "trae.com.cn", "trae.cn", "trae-by", "traeapi",
    "cursor.sh", "cursor.com", "cursorapi.com", "anysphere.co",
    # 注意：copilot.tencent.com **故意不在**名单里 —— WorkBuddy 的用量已经从
    # 会话转录统计（更准），这里再加一次会让它的数字翻倍。
    "codebuddy.cn", "cloudstudio",
    "kimi.moonshot", "kimi.com", "moonshot.cn", "kimi-code",
    "minimaxi", "minimax.chat", "zai.chat", "lingyiwanwu",
    "qoder.com", "kiro.dev", "windsurf.com", "codeium.com",
    "lingma.aliyun.com", "comate.baidu.com", "antigravity",
    # ---- 常见 OpenAI 兼容中转 / 聚合站
    "api68", "apiyi", "sg.uiuiapi", "uiuiapi", "closeai", "openai-hk",
    "vip.apiyi", "api.chatanywhere", "api2d", "ohmygpt", "gptapi",
    "aiproxy", "newapi", "voapi", "4oapi", "duckai", "aihubmix",
    "siliconflow", "ppinfra", "sharedchat", "chatsgpt", "gptbest",
)
# 请求路径里出现这些片段也视为 AI 调用（配合“解密所有 HTTPS”选项使用）
AI_PATH_KEYS = ("/chat/completions", "/completions", "/messages", "/responses",
                "/v1/responses", ":generatecontent", ":streamgeneratecontent",
                "/api/chat", "/api/generate", "/embedding", "/v1/embeddings",
                "/chat/completion", "/v2/chat", "/openai/deployments")


def is_ai_host(host, extra=()):
    if not host:
        return False
    h = host.lower().split(":")[0]
    if h in ("localhost", "127.0.0.1", "::1"):
        return False
    for k in extra or ():
        if k and k.strip().lower() in h:
            return True
    return any(k in h for k in AI_HOST_KEYS)


def is_ai_path(path):
    if not path:
        return False
    p = path.lower()
    return any(k in p for k in AI_PATH_KEYS)


# 没在名单里、但"长得像中转"的域名特征：先解密看一眼路径，是 AI 才记，
# 不是就放行并记住，下次直接隧道转发。用来覆盖自建 / 小众中转站。
PROBE_HOST_KEYS = (
    "api", "ai", "gpt", "llm", "claude", "gemini", "openai", "chat",
    "model", "infer", "proxy", "relay", "gateway", "oneapi", "newapi",
    "bot", "agent", "copilot", "glm", "deepseek", "kimi", "qwen",
)

# 已经由别的来源准确统计的域名：别再去探测它，否则同一个请求会被记两次。
# copilot.tencent.com = WorkBuddy（用量取自会话转录，比抓包准）。
PROBE_EXCLUDE = ("copilot.tencent.com",)

_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def is_probe_host(host, port=443):
    """是否值得为它冒一次解密的代价去探测（未知中转）。"""
    if not host:
        return False
    h = host.lower().split(":")[0]
    if h in ("localhost", "127.0.0.1", "::1"):
        return False
    if any(h == e or h.endswith("." + e) for e in PROBE_EXCLUDE):
        return False
    if _IP_RE.match(h):
        # IP 直连：标准端口基本是普通网站，非标端口很可能是自建中转
        return port not in (443, 80)
    if h.startswith("www.") or h.count(".") < 1:
        return False
    # 政务 / 教育 / 银行类域名别去碰（解密失败会影响正常业务）
    if h.endswith((".gov", ".gov.cn", ".edu", ".edu.cn", ".mil", ".bank")):
        return False
    return any(k in h for k in PROBE_HOST_KEYS)


HOME = os.path.expanduser("~")
ZCODE_ROLLOUT_DIR = os.path.join(HOME, ".zcode", "cli", "rollout")
ZCODE_LOG_DIR = os.path.join(HOME, ".zcode", "cli", "log")
CLAUDE_PROJECTS_DIR = os.path.join(HOME, ".claude", "projects")
# WorkBuddy（内置 CodeBuddy CLI）的会话转录：每个项目一个目录，每会话一个 jsonl。
# 它的模型请求由 Node 进程直连 copilot.tencent.com，既不读系统代理也不读系统根证书，
# 所以抓流量那条路对它无效，只能读转录里的 message.usage（含真实用量）。
WORKBUDDY_PROJECTS_DIR = os.path.join(HOME, ".workbuddy", "projects")
# Codex（OpenAI 官方 CLI / Desktop + CC Switch 中转）：会话 rollout 日志。
# Codex 把请求发到本地中转（config.toml 的 base_url 通常是 127.0.0.1:xxxx），
# 属于回环流量，系统代理管不到，所以同样只能读日志 —— rollout 里的
# token_usage_record 每条带 response_id，就是一次 API 调用的真实用量。
CODEX_HOME_ENV = "CODEX_HOME"
# OpenCode：会话存在 SQLite 里（不是 jsonl），message.data 的 tokens 就是用量。
# 优先 XDG 路径，其次 Windows 的 LOCALAPPDATA。
OPENCODE_DBS = (
    os.path.join(HOME, ".local", "share", "opencode", "opencode.db"),
    os.path.join(os.environ.get("LOCALAPPDATA", HOME), "opencode",
                 "opencode.db"),
)

SPEED_WINDOW_S = 10.0     # 实时速度的统计窗口
CHART_WINDOW_S = 300.0    # 速度曲线的时间范围
SAMPLE_STEP_S = 0.5       # 流式时长上铺采样点的步长
STALE_INFLIGHT_S = 1800.0 # 进行中请求的失效时间

# ---- 性能档位（低配电脑也可流畅运行）----
TICK_MS = 200             # UI 主循环节奏
POLL_FAST_S = 1.0         # 有新数据/生成中时的扫描间隔
POLL_SLOW_S = 3.0         # 空闲时的扫描间隔
WALK_EVERY_S = 5.0        # 递归目录(Claude/额外)重建文件列表的间隔
SAVE_EVERY_S = 15.0       # 状态落盘最小间隔
CHART_MIN_DT_S = 0.5      # 图表两次重绘的最小间隔（活跃时）
CHART_IDLE_S = 1.2        # 无新数据时图表重绘间隔
TABLE_EVERY_S = 2.0       # 模型表格刷新间隔
RATE_EVERY_S = 2.0        # 总缓存率重算间隔


# ---------------------------------------------------------------- utilities

def parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def local_date(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def fmt_tokens(n):
    """紧凑的数字格式：最多 4 位有效数字，保证列宽放得下（「4954.24万」会被截断）。"""
    n = int(n)
    if n >= 1e8:
        return f"{n / 1e8:.2f}亿" if n < 1e10 else f"{n / 1e8:.0f}亿"
    if n >= 1e4:
        v = n / 1e4
        if v < 100:
            return f"{v:.2f}万"
        if v < 1000:
            return f"{v:.1f}万"
        return f"{v:.0f}万"
    return f"{n:,}"


def fmt_ago(ts):
    if not ts:
        return "-"
    d = time.time() - ts
    if d < 5:
        return "刚刚"
    if d < 60:
        return f"{int(d)}秒前"
    if d < 3600:
        return f"{int(d / 60)}分钟前"
    if d < 86400:
        return f"{int(d / 3600)}小时前"
    return f"{int(d / 86400)}天前"


def short_provider(pid):
    if not pid:
        return ""
    name = pid.split(":")[-1].split("/")[0]
    if len(name) > 12 and "-" in name:
        name = name.split("-")[0]
    return name


def now_s():
    return time.time()


def _decode_bytes(b):
    """命令输出解码：中文 Windows 下 certutil 等工具输出 GBK。"""
    if not b:
        return ""
    if isinstance(b, str):
        return b
    for enc in ("utf-8", "gbk", "cp936", "big5"):
        try:
            return b.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return b.decode("latin1", "replace")


def _int(v):
    """容错的整数转换（用量字段可能是 None / 字符串 / 浮点）。"""
    if isinstance(v, bool) or v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _as_dict(line):
    """解析器统一入口：既接受 json 字符串，也接受已经解析好的 dict。

    允许直接传 dict 是为了让扫描器「一次解析、多处复用」——
    WorkBuddy 的转录动辄几 MB，重复 json.loads 太浪费。
    """
    if isinstance(line, dict):
        return line
    try:
        return json.loads(line)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- records
# record = {ts, source, provider, model, inp, out, cache_r, cache_w, dur, key}

def parse_zcode_rollout(line):
    d = _as_dict(line)
    if d is None:
        return None
    resp = d.get("response") or {}
    usage = resp.get("usage") or {}
    model_info = d.get("model") or {}
    model = model_info.get("modelId") or resp.get("modelId")
    if not model and usage.get("totalTokens") is None:
        return None
    ts = parse_iso(d.get("completedAt")) or now_s()
    dur = (d.get("durationMs") or 0) / 1000.0
    inp = _int(usage.get("inputTokens"))
    cr = _int(usage.get("cacheReadTokens"))
    # ZCode 的 inputTokens **已包含** cacheReadTokens（totalTokens = input + output，
    # 且实测同一会话相邻调用「含缓存累积」吻合度 39:0），所以必须减掉缓存读，
    # 否则输入会被整份重复计入 —— 之前累计输入虚高到 8 亿就是这么来的。
    inp = max(inp - cr, 0)
    # outputTokens 已含 reasoningTokens（totalTokens 校验过），不要再加
    return {
        "ts": ts,
        "source": "zcode",
        "provider": short_provider(model_info.get("providerId")),
        "model": model or "unknown",
        "inp": inp,
        "out": _int(usage.get("outputTokens")),
        "cache_r": cr,
        "cache_w": _int(usage.get("cacheWriteTokens")),
        "dur": dur,
        "key": f"{d.get('requestId')}#{d.get('attempt')}",
        "session": d.get("sessionId"),
    }


def parse_claude(line):
    d = _as_dict(line)
    if d is None:
        return None
    if d.get("type") != "assistant":
        return None
    msg = d.get("message") or {}
    usage = msg.get("usage") or {}
    model = msg.get("model")
    if not model or model == "<synthetic>":
        return None
    inp = _int(usage.get("input_tokens"))
    out = _int(usage.get("output_tokens"))
    # Claude Code 会把**同一次** API 调用的结果分多次落盘：message.id 相同，
    # 先写一条半截的（output=0、input 偏小），随后补全，甚至重复写几条一模一样的。
    # 之前拿 requestId(为 None) + uuid 当去重键，等于每条写盘都算一次新请求
    # （实测 1002 条记录其实只有约 433 次真实调用，虚高 2.3 倍）。
    # 现在：用 message.id 做去重键，并直接丢掉 output<=0 的半截记录 ——
    # 补全的那条数值一定更大，留它才准。
    if out <= 0:
        return None
    mid = msg.get("id") or d.get("requestId")
    ts = parse_iso(d.get("timestamp")) or now_s()
    return {
        "ts": ts,
        "source": "claude-code",
        "provider": "anthropic",
        "model": model,
        "inp": inp,
        "out": out,
        "cache_r": _int(usage.get("cache_read_input_tokens")),
        "cache_w": _int(usage.get("cache_creation_input_tokens")),
        "dur": 0.0,
        "key": "claude:%s" % (mid or d.get("uuid") or ts),
        "session": d.get("sessionId"),
        "est": inp <= 0,      # 输入用量缺失（走第三方中转时上游不回传），待补估算
    }


def parse_workbuddy(line):
    """WorkBuddy（内置 CodeBuddy CLI）的会话转录。

    路径 ~/.workbuddy/projects/<项目>/<会话>.jsonl。WorkBuddy 的模型请求由 Node 进程
    直连 copilot.tencent.com，既不读 Windows 系统代理也不读系统根证书，抓流量那条路
    对它无效；但每条模型调用都会落一条带 message.usage 的记录。

    为什么不会重复计数：同一次调用的 reasoning / function_call_result 这些分片记录
    不带 usage，实测 439 个 parentId 分组每组都只有 1 条带 usage 的记录。

    口径：input_tokens **已包含** cache_read_input_tokens（实测同一会话相邻调用
    「含缓存累积」吻合度 57:2，且 cached ≈ 上一轮的 input），减掉才是新增输入。
    """
    d = _as_dict(line)
    if d is None:
        return None
    msg = d.get("message")
    if not isinstance(msg, dict):
        return None
    u = msg.get("usage")
    if not isinstance(u, dict):
        return None
    pd = d.get("providerData") if isinstance(d.get("providerData"), dict) else {}
    model = pd.get("model") or msg.get("model") or d.get("model")

    inp = _int(u.get("input_tokens")) or _int(u.get("inputTokens"))
    out = _int(u.get("output_tokens")) or _int(u.get("outputTokens"))
    cr = (_int(u.get("cache_read_input_tokens"))
          or _int(u.get("cache_read_tokens")) or _int(u.get("cached_tokens")))
    if not cr:
        det = u.get("inputTokensDetails")
        if isinstance(det, list) and det and isinstance(det[0], dict):
            cr = _int(det[0].get("cached_tokens"))
    cw = (_int(u.get("cache_creation_input_tokens"))
          or _int(u.get("cache_write_tokens")))
    if inp <= 0 and out <= 0:
        return None

    ts = d.get("timestamp")
    if not (isinstance(ts, (int, float)) and ts > 1e11):   # 毫秒时间戳
        ts = now_s()
    else:
        ts = ts / 1000.0
    return {
        "ts": ts,
        "source": "workbuddy",
        "provider": guess_provider(model or ""),
        "model": model or "unknown",
        "inp": max(inp - cr, 0),
        "out": out,
        "cache_r": cr,
        "cache_w": cw,
        "dur": 0.0,
        "key": "wb:%s" % (d.get("id") or ts),
        "session": d.get("sessionId"),
    }


def codex_home():
    """Codex 的数据目录：CODEX_HOME > ~/.codex（可能是符号链接）。

    CC Switch 之类的切换器会把 ~/.codex 指向别处，也会在 config.toml 里
    写死一个 CODEX_HOME，两种都认。
    """
    env = os.environ.get(CODEX_HOME_ENV)
    if env and os.path.isdir(env):
        return env
    default = os.path.join(HOME, ".codex")
    if os.path.isdir(default):
        return default
    try:
        with open(os.path.join(default, "config.toml"), "r",
                  encoding="utf-8", errors="replace") as f:
            m = re.search(r"""CODEX_HOME\s*=\s*['"]([^'"]+)['"]""", f.read())
        if m and os.path.isdir(m.group(1)):
            return m.group(1)
    except OSError:
        pass
    return default


def codex_session_dirs():
    """Codex 的 rollout 日志目录：sessions（活跃）+ archived_sessions（归档）。"""
    home = codex_home()
    return [os.path.join(home, d) for d in ("sessions", "archived_sessions")
            if os.path.isdir(os.path.join(home, d))]


def codex_model_of(d):
    """从任意一条 Codex 记录里取当前模型名（模型名不写在用量记录里）。"""
    p = d.get("payload")
    if isinstance(p, dict):
        for key in ("model",):
            v = p.get(key)
            if isinstance(v, str) and v:
                return v
        ts = p.get("thread_settings")
        if isinstance(ts, dict) and isinstance(ts.get("model"), str):
            return ts["model"]
        st = p.get("state")
        if isinstance(st, dict) and isinstance(st.get("model"), str):
            return st["model"]
        bi = p.get("base_instructions")
        if isinstance(bi, dict):
            prov = bi.get("provenance")
            if isinstance(prov, dict) and isinstance(prov.get("model"), str):
                return prov["model"]
    m = d.get("model")
    return m if isinstance(m, str) and m else None


def parse_codex(d, model=None):
    """Codex 的 rollout 日志（sessions/**/rollout-*.jsonl）。

    只认 type=token_usage_record：payload.usage 是**这一次响应**的用量，
    payload.response_id 每次 API 调用唯一，天然不会重复。
    （event_msg/token_count 里的 total/last 是会话累计口径，跨 fork 会算重，不用。）

    口径：input_tokens **已包含** cached_input_tokens，减掉才是新增输入；
    输出要带上 reasoning_output_tokens，否则推理型模型会少算一大截。
    """
    if d.get("type") != "token_usage_record":
        return None
    p = d.get("payload")
    if not isinstance(p, dict):
        return None
    u = p.get("usage")
    if not isinstance(u, dict):
        return None
    inp = _int(u.get("input_tokens"))
    cr = _int(u.get("cached_input_tokens"))
    out = _int(u.get("output_tokens")) + _int(u.get("reasoning_output_tokens"))
    cw = _int(u.get("cache_write_input_tokens"))
    rid = p.get("response_id")
    if inp <= 0 and out <= 0:
        return None
    ts = parse_iso(d.get("timestamp")) or now_s()
    return {
        "ts": ts,
        "source": "codex",
        "provider": guess_provider(model or ""),
        "model": model or "unknown",
        "inp": max(inp - cr, 0),
        "out": out,
        "cache_r": cr,
        "cache_w": cw,
        "dur": 0.0,
        "key": "codex:%s" % (rid or ts),
        "session": p.get("session_id") or p.get("thread_id"),
    }


def opencode_db():
    for p in OPENCODE_DBS:
        if os.path.isfile(p):
            return p
    return None


def parse_opencode(mid, sid, data):
    """OpenCode 的 message 行：data 是 JSON 字符串，assistant 角色带 tokens。

    口径（实测 total = input + output + reasoning + cache.read）：
    input **不含**缓存读，输出要把 reasoning 算进去，否则推理模型少算一大截。
    """
    if not isinstance(data, dict) or data.get("role") != "assistant":
        return None
    t = data.get("tokens")
    if not isinstance(t, dict) or not t:
        return None
    cache = t.get("cache") if isinstance(t.get("cache"), dict) else {}
    inp = _int(t.get("input"))
    out = _int(t.get("output")) + _int(t.get("reasoning"))
    cr = _int(cache.get("read"))
    cw = _int(cache.get("write"))
    if inp <= 0 and out <= 0:
        return None
    tm = data.get("time") if isinstance(data.get("time"), dict) else {}
    created = _int(tm.get("created"))
    done = _int(tm.get("completed")) or created
    ts = (done or now_s() * 1000) / 1000.0
    dur = max(done - created, 0) / 1000.0 if created else 0.0
    model = data.get("modelID")
    return {
        "ts": ts,
        "source": "opencode",
        "provider": guess_provider(model or ""),
        "model": model or "unknown",
        "inp": inp,
        "out": out,
        "cache_r": cr,
        "cache_w": cw,
        "dur": dur,
        "key": "oc:%s" % mid,
        "session": sid,
    }


def parse_zcode_log_event(line):
    """返回 ('started'|'finished', trace_id, session_id) 或 None。"""
    d = _as_dict(line)
    if d is None:
        return None
    ev = d.get("event", "")
    if ev == "model.request.started":
        return ("started", d.get("traceId"), d.get("sessionId"))
    if ev in ("model.request.completed", "model.request.failed"):
        return ("finished", d.get("traceId"), d.get("sessionId"))
    return None


def log_row(rec):
    """把一条记录转成明细日志的存档格式（含本地时间字符串）。"""
    row = {
        "ts": round(rec["ts"], 3),
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rec["ts"])),
        "source": rec["source"],
        "provider": rec["provider"],
        "model": rec["model"],
        "inp": rec["inp"],
        "out": rec["out"],
        "cache_r": rec["cache_r"],
        "cache_w": rec["cache_w"],
        "dur": round(rec.get("dur", 0.0), 3),
        "key": rec.get("key", ""),
    }
    if rec.get("est"):
        row["est"] = True     # 输入用量缺失，inp 是按对话文本估算出来的
    return row


def cache_rate_pct(inp, cache_r, source):
    """缓存命中率(%) = 缓存读 / 完整输入。各来源的 inp 都已拆成「不含缓存读」的口径，
    所以分母统一是 inp + cache_r（source 参数保留只为兼容旧调用）。"""
    denom = inp + cache_r
    return round(cache_r / denom * 100, 1) if denom > 0 else 0.0


# ------------------------------------------------------- 模型 / 厂商识别

_PROVIDER_RULES = (
    (re.compile(r"claude|sonnet|opus|haiku|anthropic"), "Anthropic"),
    (re.compile(r"^o[1-4]([-.]|$)|gpt|chatgpt|davinci|codex|sora|whisper|"
                r"text-embedding-|dall-e|gpt-image"), "OpenAI"),
    (re.compile(r"gemini|palm|bison|learnlm|imagen|veo-|gemma|antigravity"),
     "Google"),
    (re.compile(r"deepseek|deep-seek"), "DeepSeek"),
    (re.compile(r"glm|chatglm|codegeex|zhipu"), "智谱GLM"),
    (re.compile(r"qwen|qwq|qvq|tongyi|wanx|wan2|dashscope"), "阿里通义"),
    (re.compile(r"kimi|moonshot|k2-"), "月之暗面"),
    (re.compile(r"doubao|seed-|seedance|seedream|skylark|volc"), "字节豆包"),
    (re.compile(r"grok|xai-|^x-ai"), "xAI"),
    (re.compile(r"llama|meta-llama"), "Meta"),
    (re.compile(r"mistral|mixtral|codestral|magistral|devstral|pixtral"), "Mistral"),
    (re.compile(r"hunyuan|tencent-|turbos"), "腾讯混元"),
    (re.compile(r"ernie|wenxin|qianfan|baidu"), "百度文心"),
    (re.compile(r"step-[0-9]|stepfun|step3"), "阶跃星辰"),
    # 必须排在 AWS 的 nova- 规则前面，否则 sensenova-* 会被误判成 Amazon Nova
    (re.compile(r"sensenova|sensechat|sense-time"), "商汤日日新"),
    (re.compile(r"minimax|abab|hailuo|m1-|m2-"), "MiniMax"),
    (re.compile(r"mimo"), "小米"),
    (re.compile(r"vidu"), "生数Vidu"),
    (re.compile(r"kling|kolors"), "快手可灵"),
    (re.compile(r"jimeng|即梦"), "即梦"),
    (re.compile(r"spark-api|xf-yun|iflytek"), "讯飞星火"),
    (re.compile(r"baichuan"), "百川智能"),
    (re.compile(r"^yi-|yi-large|yi-vision|01-ai"), "零一万物"),
    (re.compile(r"command-|cohere|embed-english|rerank"), "Cohere"),
    (re.compile(r"nova-|titan|bedrock"), "AWS"),
    (re.compile(r"nvidia|nemotron"), "NVIDIA"),
    (re.compile(r"phi-[0-9]"), "Microsoft"),
    (re.compile(r"azure"), "Azure"),
    (re.compile(r"internlm|internlm2|internvl"), "上海AI Lab"),
    (re.compile(r"hunyuan|(^|[-_/])hy-?[0-9]"), "腾讯混元"),
    (re.compile(r"glm4|glm-4"), "智谱GLM"),
)


def guess_provider(model):
    """从模型名推断厂商（Claude / GPT / Gemini …）。"""
    if not model:
        return ""
    m = str(model).lower()
    for pat, name in _PROVIDER_RULES:
        if pat.search(m):
            return name
    return ""


# ------------------------------------------------------- 通用 usage 提取

_USAGE_ALIAS = {
    "input_tokens": "inp", "inputtokens": "inp", "prompt_tokens": "inp",
    "prompttokens": "inp", "prompttokencount": "inp", "inputtokencount": "inp",
    "input_token_count": "inp", "prompt_token_count": "inp",
    "n_input_tokens": "inp", "n_prompt_tokens": "inp",
    "output_tokens": "out", "outputtokens": "out", "completion_tokens": "out",
    "completiontokens": "out", "candidatestokencount": "out",
    "outputtokencount": "out", "output_token_count": "out",
    "completion_token_count": "out", "n_output_tokens": "out",
    "n_completion_tokens": "out",
    "cache_read_input_tokens": "cache_r", "cachereadinputtokens": "cache_r",
    "cachereadtokens": "cache_r", "cached_tokens": "cache_r",
    "cachedtokencount": "cache_r", "cache_read_tokens": "cache_r",
    "cachedcontenttokencount": "cache_r", "cache_creation_input_tokens": "cache_w",
    "cachewriteTokens".lower(): "cache_w", "cachecreationinputtokens": "cache_w",
    "cache_write_tokens": "cache_w", "cache_creation_tokens": "cache_w",
    "thoughtstokencount": "think", "reasoning_tokens": "think",
    "reasoningtokens": "think", "reasoning_token_count": "think",
    "total_tokens": "total", "totaltokens": "total", "totaltokencount": "total",
}
# 这些字段的口径里“输入”已经包含缓存读取，需要拆开
_INCLUSIVE_KEYS = ("prompt_tokens", "prompttokens", "prompttokencount",
                   "inputtokencount", "prompt_token_count", "n_prompt_tokens",
                   "inputtokens")


def extract_usage(node, _depth=0):
    """在任意 JSON 结构里寻找 token 用量对象，返回归一化前的字典或 None。"""
    if _depth > 8:
        return None
    if isinstance(node, dict):
        acc, seen, inc = {}, [], False
        for k, v in node.items():
            kl = k.lower() if isinstance(k, str) else ""
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                tgt = _USAGE_ALIAS.get(kl)
                if tgt:
                    acc[tgt] = max(acc.get(tgt, 0), int(v))
                    seen.append(kl)
            elif isinstance(v, dict) and ("detail" in kl or kl in (
                    "usage", "tokenusage", "token_usage", "usagemetadata",
                    "usagedetails", "usage_details", "billableusage")):
                sub = extract_usage(v, _depth + 1)
                if sub:
                    for kk, vv in sub.items():
                        if kk == "inclusive":
                            inc = inc or bool(vv)
                            continue
                        if kk not in acc or vv > acc[kk]:
                            acc[kk] = vv
        if acc:
            acc["inclusive"] = inc or any(s in _INCLUSIVE_KEYS for s in seen)
            return acc
        for v in node.values():
            if isinstance(v, (dict, list)):
                sub = extract_usage(v, _depth + 1)
                if sub:
                    return sub
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, (dict, list)):
                sub = extract_usage(v, _depth + 1)
                if sub:
                    return sub
    return None


def normalize_usage(u):
    """统一成 {inp(不含缓存), out, cache_r, cache_w}。"""
    if not u:
        return {"inp": 0, "out": 0, "cache_r": 0, "cache_w": 0}
    inp = int(u.get("inp", 0) or 0)
    out = int(u.get("out", 0) or 0) + int(u.get("think", 0) or 0)
    cr = int(u.get("cache_r", 0) or 0)
    cw = int(u.get("cache_w", 0) or 0)
    if u.get("inclusive") and cr and cr <= inp:
        inp -= cr
    return {"inp": max(inp, 0), "out": max(out, 0),
            "cache_r": max(cr, 0), "cache_w": max(cw, 0)}


_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff"
                     r"\uac00-\ud7af\U00020000-\U0002ffff]")


def estimate_tokens(text):
    """没有真实 usage 时按字符估算：中文≈1.5字/token，其余≈4字符/token。"""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    other = len(text) - cjk
    return int(cjk / 1.5 + other / 4.0) + 1


# 这些字段装的是快照/二进制，不属于发给模型的对话内容，估算时应跳过
_SKIP_TEXT_KEYS = ("snapshot", "signature", "thinkingsignature", "base64",
                   "thumbnailsource", "encrypted_content")


def text_weight(node, acc, _depth=0):
    """把 JSON 里出现的文本量累加进 acc = [CJK字符数, 其它字符数]。

    用途：某些 CLI 走第三方中转时，日志里的 input_tokens 恒为 0（上游不回传），
    此时用「同一会话到这一轮为止已经出现的对话文本」做字符估算，
    比直接记 0 更接近真实输入。
    """
    if _depth > 14:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.lower() in _SKIP_TEXT_KEYS:
                continue
            text_weight(v, acc, _depth + 1)
    elif isinstance(node, list):
        for v in node:
            text_weight(v, acc, _depth + 1)
    elif isinstance(node, str):
        n = len(node)
        if n < 12:          # role / type / uuid 之类的短字段不计
            return
        c = len(_CJK_RE.findall(node))
        acc[0] += c
        acc[1] += n - c


def weight_to_tokens(acc):
    """与 estimate_tokens 同一套比例。"""
    if not acc:
        return 0
    return int(acc[0] / 1.5 + acc[1] / 4.0) + 1


_ANTHROPIC_BLOCK_TEXT = ("text", "thinking", "partial_json", "input_json_delta")


def collect_output_text(d, out, _depth=0):
    """从一段响应 JSON（流式分片或完整响应）里抽取“模型输出文本”，累加到 out。"""
    if _depth > 6 or not isinstance(d, dict):
        return
    # OpenAI Chat Completions
    chs = d.get("choices")
    if isinstance(chs, list):
        for ch in chs:
            if not isinstance(ch, dict):
                continue
            for holder in ("delta", "message"):
                h = ch.get(holder)
                if not isinstance(h, dict):
                    continue
                for kk in ("content", "reasoning_content", "reasoning"):
                    t = h.get(kk)
                    if isinstance(t, str):
                        out.append(t)
                    elif isinstance(t, list):
                        for blk in t:
                            if isinstance(blk, dict) and \
                                    isinstance(blk.get("text"), str):
                                out.append(blk["text"])
                for tc in h.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        arg = (tc.get("function") or {}).get("arguments")
                        if isinstance(arg, str):
                            out.append(arg)
    # OpenAI Responses API（/v1/responses 流式增量）
    typ = d.get("type")
    if isinstance(typ, str) and isinstance(d.get("delta"), str) and \
            typ.startswith(("response.output_text", "response.function_call",
                            "response.reasoning", "response.refusal")):
        out.append(d["delta"])
    # Anthropic 流式
    if typ == "content_block_delta":
        dl = d.get("delta") or {}
        if isinstance(dl, dict):
            for kk in _ANTHROPIC_BLOCK_TEXT:
                if isinstance(dl.get(kk), str):
                    out.append(dl[kk])
    # Anthropic 完整响应
    if isinstance(d.get("content"), list):
        for blk in d["content"]:
            if isinstance(blk, dict):
                for kk in _ANTHROPIC_BLOCK_TEXT:
                    if isinstance(blk.get(kk), str):
                        out.append(blk[kk])
    # Gemini
    for cand in d.get("candidates") or []:
        if not isinstance(cand, dict):
            continue
        parts = (cand.get("content") or {}).get("parts") or []
        for part in parts:
            if isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    out.append(part["text"])
                elif isinstance(part.get("functionCall"), dict):
                    out.append(json.dumps(part["functionCall"],
                                          ensure_ascii=False))
    # 兜底
    if isinstance(d.get("output_text"), str):
        out.append(d["output_text"])
    # 下一层（某些网关会再包一层）
    for k in ("data", "result", "response", "body", "payload"):
        v = d.get(k)
        if isinstance(v, dict):
            collect_output_text(v, out, _depth + 1)


def collect_input_text(node, out, _depth=0):
    """从请求体里粗略抽取提示词文本，用于无 usage 时的输入估算。"""
    if _depth > 6:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            kl = k.lower()
            if kl in ("messages", "input", "contents", "prompt", "system",
                      "content", "text", "instructions", "reasoning",
                      "tool_calls", "function_call", "parts", "systeminstruction"):
                if isinstance(v, str):
                    out.append(v)
                elif isinstance(v, (dict, list)):
                    collect_input_text(v, out, _depth + 1)
            elif isinstance(v, (dict, list)) and kl not in (
                    "tools", "tool_choice", "metadata", "response_format",
                    "stream_options", "functions"):
                collect_input_text(v, out, _depth + 1)
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, (dict, list)):
                collect_input_text(v, out, _depth + 1)
            elif isinstance(v, str):
                out.append(v)


# ---------------------------------------------------------------- stats

class Stats:
    """线程安全：所有写操作来自 watcher 线程，GUI 只读快照。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.cumulative = {}   # model_key -> agg
        self.daily = {}        # date -> {model_key: agg}
        self.ema = {}          # model_key -> 平均生成速度 (tok/s) 指数滑动平均
        self.global_ema = 0.0
        self.dirty = False

    @staticmethod
    def _new_agg():
        return {"requests": 0, "inp": 0, "out": 0, "cache_r": 0, "cache_w": 0,
                "gen_s": 0.0, "last_ts": 0.0, "est_req": 0}

    @staticmethod
    def _add_into(agg, rec):
        agg["requests"] += 1
        agg["inp"] += rec["inp"]
        agg["out"] += rec["out"]
        agg["cache_r"] += rec["cache_r"]
        agg["cache_w"] += rec["cache_w"]
        agg["gen_s"] += rec["dur"]
        agg["last_ts"] = max(agg["last_ts"], rec["ts"])
        if rec.get("est"):
            # 这条记录的 inp 是估算出来的（上游没回传输入用量），界面用 ≈ 标注
            agg["est_req"] = agg.get("est_req", 0) + 1

    def add(self, rec):
        key = (rec["source"], rec["provider"], rec["model"])
        with self.lock:
            self._add_into(self.cumulative.setdefault(key, self._new_agg()), rec)
            self._add_into(self.daily.setdefault(local_date(rec["ts"]), {})
                           .setdefault(key, self._new_agg()), rec)
            # 只保留最近 30 天的按日统计
            if len(self.daily) > 40:
                for d in sorted(self.daily)[:-30]:
                    del self.daily[d]
            if rec["dur"] > 0.3 and rec["out"] > 0:
                cur = rec["out"] / rec["dur"]
                old = self.ema.get(key, cur)
                self.ema[key] = old * 0.6 + cur * 0.4
                self.global_ema = self.global_ema * 0.7 + cur * 0.3 if self.global_ema else cur
            self.dirty = True

    def snapshot_cumulative(self):
        with self.lock:
            return dict(self.cumulative)

    def snapshot_today(self):
        today = local_date(now_s())
        with self.lock:
            return dict(self.daily.get(today, {}))

    def totals(self):
        with self.lock:
            today = local_date(now_s())
            t_today = self.daily.get(today, {})
            return (
                sum(a["out"] + a["inp"] for a in self.cumulative.values()),
                sum(a["out"] + a["inp"] for a in t_today.values()),
            )

    def ema_for(self, model_key):
        with self.lock:
            v = self.ema.get(model_key) or self.global_ema
        return v or 40.0

    def reset(self):
        with self.lock:
            self.cumulative.clear()
            self.daily.clear()
            self.dirty = True

    def set_clean(self):
        self.dirty = False

    # ---------------- persistence

    def save(self, offsets):
        if not self.dirty:
            return
        with self.lock:
            data = {
                "version": 1,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "cumulative": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in self.cumulative.items()},
                "daily": {d: {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in m.items()}
                          for d, m in self.daily.items()},
                "ema": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in self.ema.items()},
                "global_ema": self.global_ema,
                "offsets": {p: [s, m] for p, (s, m) in offsets.items()},
            }
            self.dirty = False
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, STATE_FILE)
        except OSError as e:
            sys.stderr.write(f"保存状态失败: {e}\n")

    def load(self):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        def pk(s):
            p = s.split("|")
            return (p[0], p[1], "|".join(p[2:])) if len(p) >= 3 else s
        with self.lock:
            self.cumulative = {pk(k): v for k, v in data.get("cumulative", {}).items()}
            self.daily = {d: {pk(k): v for k, v in m.items()}
                          for d, m in data.get("daily", {}).items()}
            self.ema = {pk(k): v for k, v in data.get("ema", {}).items()}
            self.global_ema = data.get("global_ema", 0.0)
        return data.get("offsets", {})


# ---------------------------------------------------------------- speed meter

class SpeedMeter:
    """实时速度：把每条已完成的请求在其真实流式时长上铺开成采样点；
    生成中的请求按该模型近期平均速度做临时估算，真实记录到达后替换。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.samples = deque()   # (ts, tokens, key)
        self.inflight = {}       # trace_id -> {start, model_key, last, rate}

    def note_started(self, trace_id, model_key):
        with self.lock:
            self.inflight[trace_id] = {
                "start": now_s(), "model_key": model_key,
                "last": now_s(), "rate": None,
            }

    def note_finished(self, trace_id):
        with self.lock:
            self.inflight.pop(trace_id, None)

    def set_rate(self, trace_id, rate):
        with self.lock:
            if trace_id in self.inflight:
                self.inflight[trace_id]["rate"] = rate

    def add_record(self, rec, model_key):
        with self.lock:
            self.inflight.pop(rec["key"], None)
            drop = {rec["key"], f"live:{rec['key']}"}
            if any(k in drop for _, _, k in self.samples):
                self.samples = deque(s for s in self.samples if s[2] not in drop)
            self._spread(rec["ts"], rec["out"], rec["dur"], rec["key"])

    def _spread(self, end_ts, tokens, dur, key):
        if tokens <= 0:
            return
        dur = min(max(dur, 0.0), 600.0)
        n = max(1, int(dur / SAMPLE_STEP_S))
        step = dur / n
        for i in range(n):
            self.samples.append((end_ts - dur + step * (i + 1), tokens / n, key))

    def tick(self, stats):
        """GUI 定时调用：为生成中的请求追加临时估算样本。"""
        now = now_s()
        with self.lock:
            for tid, info in list(self.inflight.items()):
                if now - info["start"] > STALE_INFLIGHT_S:
                    del self.inflight[tid]
                    continue
                rate = info["rate"] or stats.ema_for(info["model_key"])
                dt = now - info["last"]
                if dt >= 0.5:   # 低配友好：采样密度减半，10s 窗口平滑度不受影响
                    self.samples.append((now, rate * dt, f"live:{tid}"))
                    info["last"] = now
            cutoff = now - (CHART_WINDOW_S + 30)   # 图表只用 300s，多留 30s 余量
            while self.samples and self.samples[0][0] < cutoff:
                self.samples.popleft()

    def speed(self):
        now = now_s()
        with self.lock:
            window = min(SPEED_WINDOW_S, max(now - self.samples[0][0], 0.5)) \
                if self.samples else SPEED_WINDOW_S
            total = sum(t for ts, t, _ in self.samples if ts > now - SPEED_WINDOW_S)
        return total / SPEED_WINDOW_S, total / window if window else 0.0

    def speed_and_minute(self):
        """一次加锁同时算出实时速度和本分钟 tokens（UI 每 tick 调用，省一遍扫描）。"""
        now = now_s()
        with self.lock:
            total = minute = 0.0
            for ts, t, _ in self.samples:
                if ts > now - SPEED_WINDOW_S:
                    total += t
                if ts > now - 60:
                    minute += t
        return total / SPEED_WINDOW_S, minute

    def minute_tokens(self):
        now = now_s()
        with self.lock:
            return sum(t for ts, t, _ in self.samples if ts > now - 60)

    def history(self, span=CHART_WINDOW_S):
        now = now_s()
        with self.lock:
            return [(ts, t) for ts, t, _ in self.samples if ts > now - span]

    def clear(self):
        with self.lock:
            self.samples.clear()
            self.inflight.clear()


# ------------------------------------------------- 网络直采：系统代理与环境变量

_ENV_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy",
              "NODE_EXTRA_CA_CERTS", "NODE_USE_ENV_PROXY")


class Autostart:
    """开机自启：往 HKCU\\...\\Run 里注册一条，注销即删除。

    只写当前用户，不需要管理员权限；卸载时（或取消勾选）整条删掉，
    不留残值。脚本运行时注册的是 pythonw + 脚本路径，打包后是 exe 本身。
    """

    KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    NAME = "TokenMon"

    @staticmethod
    def cmd():
        if getattr(sys, "frozen", False):
            return '"%s"' % sys.executable
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.isfile(pyw):
            pyw = sys.executable
        return '"%s" "%s"' % (pyw, os.path.abspath(__file__))

    @staticmethod
    def enabled():
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, Autostart.KEY) as k:
                val, _ = winreg.QueryValueEx(k, Autostart.NAME)
        except OSError:
            return False
        return bool(val)

    @staticmethod
    def set_on(on):
        if winreg is None:
            return False, "仅 Windows 支持开机自启"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, Autostart.KEY, 0,
                                winreg.KEY_READ | winreg.KEY_WRITE) as k:
                if on:
                    winreg.SetValueEx(k, Autostart.NAME, 0, winreg.REG_SZ,
                                      Autostart.cmd())
                else:
                    try:
                        winreg.DeleteValue(k, Autostart.NAME)
                    except OSError:
                        pass
            return True, ("已设置开机自启" if on else "已取消开机自启")
        except OSError as e:
            return False, f"写入注册表失败: {e}"


class SystemProxy:
    """通过注册表接管 Windows 系统代理 / 用户环境变量，并可完整还原。"""

    KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

    @staticmethod
    def _key(path, write=False):
        return winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                              winreg.KEY_READ | (winreg.KEY_WRITE if write else 0))

    # ---- 系统代理（Chrome / Edge / Electron 类程序都读这里）
    @staticmethod
    def read():
        out = {}
        if winreg is None:
            return out
        try:
            with SystemProxy._key(SystemProxy.KEY) as k:
                for n in ("ProxyEnable", "ProxyServer", "ProxyOverride",
                          "AutoConfigURL"):
                    try:
                        out[n] = winreg.QueryValueEx(k, n)[0]
                    except OSError:
                        out[n] = None
        except OSError:
            pass
        return out

    @staticmethod
    def apply(server):
        prev = SystemProxy.read()
        with SystemProxy._key(SystemProxy.KEY, True) as k:
            winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ, server)
            winreg.SetValueEx(k, "ProxyOverride", 0, winreg.REG_SZ,
                              "<local>;localhost;127.0.0.1;*.local")
            # PAC 自动配置脚本优先级高于固定代理，启用期间必须临时移除，
            # 否则浏览器会绕过直采。（原值已存进备份，退出时还原）
            try:
                winreg.DeleteValue(k, "AutoConfigURL")
            except OSError:
                pass
        SystemProxy.refresh()
        return prev

    @staticmethod
    def restore(prev):
        if winreg is None or not prev:
            return
        try:
            with SystemProxy._key(SystemProxy.KEY, True) as k:
                for n, v in prev.items():
                    try:
                        if v is None:
                            winreg.DeleteValue(k, n)
                        elif n == "ProxyEnable":
                            winreg.SetValueEx(k, n, 0, winreg.REG_DWORD, int(v))
                        else:
                            winreg.SetValueEx(k, n, 0, winreg.REG_SZ, str(v))
                    except OSError:
                        pass
        except OSError:
            pass
        SystemProxy.refresh()

    @staticmethod
    def refresh():
        try:
            import ctypes
            for opt in (39, 37):     # SETTINGS_CHANGED / REFRESH
                ctypes.windll.wininet.InternetSetOptionW(0, opt, 0, 0)
        except Exception:
            pass

    # ---- 用户环境变量（Node / Python / Rust 等命令行程序靠这个走代理）
    @staticmethod
    def read_env():
        out = {}
        if winreg is None:
            return out
        try:
            with SystemProxy._key("Environment") as k:
                for n in _ENV_NAMES:
                    try:
                        out[n] = winreg.QueryValueEx(k, n)[0]
                    except OSError:
                        out[n] = None
        except OSError:
            pass
        return out

    @staticmethod
    def apply_env(pairs):
        prev = SystemProxy.read_env()
        with SystemProxy._key("Environment", True) as k:
            for n, v in pairs.items():
                winreg.SetValueEx(k, n, 0, winreg.REG_SZ, str(v))
        SystemProxy._broadcast()
        return prev

    @staticmethod
    def restore_env(prev):
        if winreg is None or not prev:
            return
        try:
            with SystemProxy._key("Environment", True) as k:
                for n, v in prev.items():
                    try:
                        if v is None:
                            winreg.DeleteValue(k, n)
                        else:
                            winreg.SetValueEx(k, n, 0, winreg.REG_SZ, str(v))
                    except OSError:
                        pass
        except OSError:
            pass
        SystemProxy._broadcast()

    @staticmethod
    def _broadcast():
        try:
            import ctypes
            res = ctypes.c_long()
            ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF, 0x1A, 0, ctypes.c_wchar_p("Environment"),
                0x0002, 3000, ctypes.byref(res))
        except Exception:
            pass


def save_proxy_backup(data):
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(PROXY_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def load_proxy_backup():
    try:
        with open(PROXY_BACKUP_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and d.get("active") else None
    except (OSError, ValueError):
        return None


def clear_proxy_backup():
    try:
        os.remove(PROXY_BACKUP_FILE)
    except OSError:
        pass


def write_restore_bat():
    """生成一键还原脚本：程序异常退出导致上不了网时双击即可修复。"""
    body = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "echo Restoring system proxy settings...\r\n"
        "reg add \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\"
        "Internet Settings\" /v ProxyEnable /t REG_DWORD /d 0 /f >nul\r\n"
        "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\"
        "Internet Settings\" /v ProxyServer /f >nul 2>nul\r\n"
        "for %%V in (HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy "
        "NODE_EXTRA_CA_CERTS NODE_USE_ENV_PROXY) do "
        "reg delete \"HKCU\\Environment\" /v %%V /f >nul 2>nul\r\n"
        "echo Done.  System proxy disabled, proxy env vars removed.\r\n"
        "pause\r\n"
    )
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(RESTORE_BAT, "w", encoding="ascii", newline="") as f:
            f.write(body)
    except OSError:
        pass


# ------------------------------------------------- 网络直采：根证书

class CertAuthority:
    """本地根证书：生成 / 加载 / 安装到系统信任区 / 按域名即时签发证书。"""

    def __init__(self, ca_dir=CA_DIR):
        self.dir = ca_dir
        self.cert_path = CA_CERT_FILE
        self.key_path = CA_KEY_FILE
        self.leaf_dir = LEAF_DIR
        self.error = ""
        self._mod = None
        self._ca_cert = None
        self._ca_key = None
        self._leaf_key = None
        self._leafs = {}
        self._lock = threading.Lock()
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
            self._mod = (x509, hashes, serialization, rsa, NameOID)
        except Exception as e:      # 未安装 cryptography 时退化为不支持直采
            self.error = f"缺少 cryptography 库: {e}"

    @property
    def supported(self):
        return self._mod is not None

    @property
    def available(self):
        return self._mod is not None and self._ca_cert is not None

    @property
    def thumbprint(self):
        if self._ca_cert is None:
            return ""
        return self._ca_cert.fingerprint(self._mod[1].SHA1()).hex()

    def ensure(self):
        if self._mod is None:
            return False
        if self._ca_cert is not None:
            return True
        x509, hashes, serialization, rsa, NameOID = self._mod
        try:
            os.makedirs(self.dir, exist_ok=True)
            if os.path.exists(self.cert_path) and os.path.exists(self.key_path):
                with open(self.cert_path, "rb") as f:
                    self._ca_cert = x509.load_pem_x509_certificate(f.read())
                with open(self.key_path, "rb") as f:
                    self._ca_key = serialization.load_pem_private_key(
                        f.read(), password=None)
                return True
            self._ca_key = rsa.generate_private_key(public_exponent=65537,
                                                    key_size=2048)
            name = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, "TokenMon Local Root CA"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TokenMon"),
            ])
            now = datetime.now()
            cert = (x509.CertificateBuilder()
                    .subject_name(name).issuer_name(name)
                    .public_key(self._ca_key.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(days=1))
                    .not_valid_after(now + timedelta(days=3650))
                    .add_extension(x509.BasicConstraints(ca=True, path_length=0),
                                   critical=True)
                    .add_extension(x509.KeyUsage(
                        digital_signature=True, content_commitment=False,
                        key_encipherment=False, data_encipherment=False,
                        key_agreement=False, key_cert_sign=True, crl_sign=True,
                        encipher_only=False, decipher_only=False), critical=True)
                    .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                        self._ca_key.public_key()), critical=False)
                    .sign(self._ca_key, hashes.SHA256()))
            with open(self.cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            with open(self.key_path, "wb") as f:
                f.write(self._ca_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption()))
            self._ca_cert = cert
            return True
        except Exception as e:
            self.error = f"生成根证书失败: {e}"
            return False

    def leaf_for(self, host):
        """返回 (cert_path, key_path)；同一域名只签发一次。"""
        with self._lock:
            hit = self._leafs.get(host)
        if hit:
            return hit
        x509, hashes, serialization, rsa, NameOID = self._mod
        os.makedirs(self.leaf_dir, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", host)[:100] or "unknown"
        cert_p = os.path.join(self.leaf_dir, safe + ".pem")
        key_p = os.path.join(self.leaf_dir, safe + ".key")
        try:
            if not (os.path.exists(cert_p) and os.path.exists(key_p)):
                if self._leaf_key is None:
                    self._leaf_key = rsa.generate_private_key(
                        public_exponent=65537, key_size=2048)
                key = self._leaf_key
                now = datetime.now()
                if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
                    san = [x509.IPAddress(ipaddress.ip_address(host))]
                else:
                    san = [x509.DNSName(host)]
                cert = (x509.CertificateBuilder()
                        .subject_name(x509.Name([x509.NameAttribute(
                            NameOID.COMMON_NAME, host)]))
                        .issuer_name(self._ca_cert.subject)
                        .public_key(key.public_key())
                        .serial_number(x509.random_serial_number())
                        .not_valid_before(now - timedelta(days=1))
                        .not_valid_after(now + timedelta(days=825))
                        .add_extension(x509.BasicConstraints(
                            ca=False, path_length=None), critical=True)
                        .add_extension(x509.KeyUsage(
                            digital_signature=True, content_commitment=False,
                            key_encipherment=True, data_encipherment=False,
                            key_agreement=False, key_cert_sign=False,
                            crl_sign=False, encipher_only=False,
                            decipher_only=False), critical=True)
                        .add_extension(x509.ExtendedKeyUsage([
                            x509.ObjectIdentifier("1.3.6.1.5.5.7.3.1")]),
                            critical=False)
                        .add_extension(x509.SubjectAlternativeName(san),
                                       critical=False)
                        .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                            key.public_key()), critical=False)
                        .add_extension(
                            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                                self._ca_key.public_key()), critical=False)
                        .sign(self._ca_key, hashes.SHA256()))
                with open(cert_p, "wb") as f:
                    f.write(cert.public_bytes(serialization.Encoding.PEM))
                with open(key_p, "wb") as f:
                    f.write(key.private_bytes(
                        serialization.Encoding.PEM,
                        serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption()))
        except Exception as e:
            self.error = f"签发站点证书失败({host}): {e}"
            return None
        with self._lock:
            self._leafs[host] = (cert_p, key_p)
        return cert_p, key_p

    # ---- 证书导入系统信任区（当前用户，无需管理员、不弹确认框）
    @staticmethod
    def _certutil(*args):
        """返回 (returncode, 文本输出)。certutil 在中文系统输出 GBK，需容错解码。"""
        flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
        r = subprocess.run(["certutil", *args], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, creationflags=flags)
        return r.returncode, _decode_bytes(r.stdout) + _decode_bytes(r.stderr)

    def _win_store(self, der, remove=False):
        """通过 CryptoAPI 直接操作当前用户的 ROOT 证书库（静默，无弹窗）。"""
        import ctypes
        from ctypes import wintypes
        X509_ASN_ENCODING = 0x00000001
        PKCS_7_ASN_ENCODING = 0x00010000
        enc = X509_ASN_ENCODING | PKCS_7_ASN_ENCODING
        try:
            c32 = ctypes.WinDLL("crypt32", use_last_error=True)
        except OSError as e:
            return False, f"加载 crypt32 失败: {e}"
        c32.CertCreateCertificateContext.restype = ctypes.c_void_p
        c32.CertCreateCertificateContext.argtypes = [
            wintypes.DWORD, ctypes.c_char_p, wintypes.DWORD]
        ctx = c32.CertCreateCertificateContext(enc, der, len(der))
        if not ctx:
            return False, "创建证书上下文失败"
        c32.CertOpenStore.restype = ctypes.c_void_p
        c32.CertOpenStore.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD,
                                      ctypes.c_wchar_p]
        CERT_STORE_PROV_SYSTEM_W = ctypes.c_void_p(10)
        CERT_SYSTEM_STORE_CURRENT_USER = 0x00010000
        store = c32.CertOpenStore(CERT_STORE_PROV_SYSTEM_W, 0, None,
                                  CERT_SYSTEM_STORE_CURRENT_USER, "ROOT")
        if not store:
            c32.CertFreeCertificateContext(ctx)
            return False, "打开证书库失败"
        ok = False
        note = ""
        try:
            if remove:
                c32.CertFindCertificateInStore.restype = ctypes.c_void_p
                c32.CertFindCertificateInStore.argtypes = [
                    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                    wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
                CERT_FIND_EXISTING = 0x000d0000
                c32.CertDeleteCertificateFromStore.restype = wintypes.BOOL
                c32.CertDeleteCertificateFromStore.argtypes = [ctypes.c_void_p]
                for _ in range(100):
                    found = c32.CertFindCertificateInStore(
                        store, enc, 0, CERT_FIND_EXISTING, ctx, None)
                    if not found:
                        break
                    if not c32.CertDeleteCertificateFromStore(found):
                        note = "删除证书失败"
                        break
                    ok = True
                if not ok and not note:
                    ok = True          # 本来就不在库里，也算成功
            else:
                c32.CertAddCertificateContextToStore.restype = wintypes.BOOL
                c32.CertAddCertificateContextToStore.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                    ctypes.c_void_p]
                CERT_STORE_ADD_REPLACE_EXISTING = 3
                ok = bool(c32.CertAddCertificateContextToStore(
                    store, ctx, CERT_STORE_ADD_REPLACE_EXISTING, None))
                if not ok:
                    note = f"写入证书库失败(err={ctypes.get_last_error()})"
        finally:
            c32.CertFreeCertificateContext(ctx)
            c32.CertCloseStore(store, 0)
        return ok, note

    def _der(self):
        return self._ca_cert.public_bytes(self._mod[2].Encoding.DER)

    def is_installed(self):
        if not self._ca_cert or os.name != "nt":
            return False
        try:
            rc, _ = self._certutil("-user", "-verifystore", "Root",
                                   self.thumbprint)
            return rc == 0
        except (OSError, IndexError):
            return False

    def install(self):
        if self._ca_cert is None:
            return False, "根证书尚未生成"
        note = ""
        if os.name == "nt":
            try:
                ok, note = self._win_store(self._der(), remove=False)
                if ok:
                    return True, ""
            except Exception as e:
                note = f"CryptoAPI 写入失败: {e}"
        try:                       # 退路：certutil
            rc, txt = self._certutil("-user", "-addstore", "-f", "Root",
                                     self.cert_path)
        except OSError as e:
            return False, f"调用 certutil 失败: {e}"
        if rc == 0:
            return True, ""
        blob = (note + " " + txt)
        if "取消" in blob or "cancel" in blob.lower():
            return False, "已取消 —— 需要在 Windows 安全警告弹窗中点『是』"
        last = txt.strip().splitlines()[-1][:160] if txt.strip() else ""
        return False, (note or last or "安装失败")

    def uninstall(self):
        if not self.thumbprint:
            return False, "根证书尚未生成"
        if os.name == "nt":
            try:
                ok, note = self._win_store(self._der(), remove=True)
                if ok:
                    return True, ""
            except Exception:
                pass
        try:
            rc, _ = self._certutil("-user", "-delstore", "Root",
                                   self.thumbprint)
        except OSError as e:
            return False, f"调用 certutil 失败: {e}"
        return rc == 0, ""


# ------------------------------------------------- 网络直采：代理服务器

class BufReader:
    """带缓冲的 socket 读取器（HTTP 报文分帧用）。"""

    __slots__ = ("sock", "buf")

    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def read_until(self, sep, limit=262144):
        while sep not in self.buf:
            if len(self.buf) > limit:
                raise ValueError("报文头过大")
            d = self.sock.recv(RELAY_CHUNK)
            if not d:
                raise EOFError
            self.buf += d
        i = self.buf.index(sep) + len(sep)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def read_some(self, n=RELAY_CHUNK):
        if self.buf:
            out, self.buf = self.buf[:n], self.buf[n:]
            return out
        d = self.sock.recv(n)
        if not d:
            raise EOFError
        return d

    def read_exact(self, n):
        while len(self.buf) < n:
            d = self.sock.recv(max(RELAY_CHUNK, n - len(self.buf)))
            if not d:
                raise EOFError
            self.buf += d
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def read_chunked(self):
        """读取 chunked 正文，返回解出的原始字节（同时可转发原始分块）。"""
        body = bytearray()
        while True:
            line = self.read_until(b"\r\n")
            try:
                n = int(line.split(b";")[0].strip() or b"0", 16)
            except ValueError:
                raise ValueError("chunk 长度非法")
            if n == 0:
                while True:
                    l = self.read_until(b"\r\n")
                    if l in (b"\r\n", b"\n"):
                        break
                break
            body += self.read_exact(n)
            self.read_exact(2)
        return bytes(body)


def model_from_path(path):
    """有些接口把模型写在 URL 里（Gemini / Azure / 部分中转站）。"""
    if not path:
        return ""
    p = path.split("?")[0]
    m = re.search(r"/models/([^/:?]+)", p)
    if m:
        return m.group(1)
    m = re.search(r"/deployments/([^/:?]+)", p)
    if m:
        return m.group(1)
    m = re.search(r"[?&]model=([^&]+)", path)
    if m:
        return m.group(1)
    m = re.search(r"/model/([^/:?]+)", p)
    if m:
        return m.group(1)
    return ""


def _parse_headers(raw_lines):
    out = {}
    for ln in raw_lines:
        if b":" not in ln:
            continue
        k, _, v = ln.partition(b":")
        out[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
    return out


def _rebuild_head(method, path, version, headers, drop):
    lines = [f"{method} {path} {version or 'HTTP/1.1'}"]
    for k, v in headers.items():
        if k.lower() in drop:
            continue
        lines.append(f"{k}: {v}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin1")


_UPSTREAM_CTX = None


def _upstream_ctx():
    global _UPSTREAM_CTX
    if _UPSTREAM_CTX is None:
        c = ssl.create_default_context()
        c.check_hostname = True
        c.verify_mode = ssl.CERT_REQUIRED
        _UPSTREAM_CTX = c
    return _UPSTREAM_CTX


class MitmProxy(threading.Thread):
    """本地 HTTP(S) 代理：解密发往 AI 服务的请求/响应，直读 token 用量。

    - 只对白名单内的 AI 域名做 TLS 解密；其它域名原样隧道转发，不装证书也能用。
    - 从响应里读取真实 usage；流式响应边转发边统计，实时速度就是生成速度。
    """

    def __init__(self, emit, ui_queue, ca, meter=None, port=PROXY_PORT_DEFAULT,
                 host=PROXY_HOST, extra_hosts=None, mitm_all=False,
                 auto_probe=True):
        super().__init__(daemon=True, name="mitm-proxy")
        self.emit = emit
        self.q = ui_queue
        self.ca = ca
        self.meter = meter
        self.port = int(port)
        self.addr = f"{host}:{int(port)}"
        self.host = host
        self.extra_hosts = list(extra_hosts or [])
        self.mitm_all = bool(mitm_all)
        self.auto_probe = bool(auto_probe)
        self.probe_cache = {}                  # host -> True(是AI)/False(不是)
        self.probe_hits = []                   # 自动识别出来的中转域名
        self.stop_flag = threading.Event()
        self.running = False
        self.error = ""
        self._srv = None
        self._lock = threading.Lock()
        self._seq = 0
        self.active = {}                       # tid -> {start, model_key}
        self.recent = deque(maxlen=200)        # 最近抓到的请求（界面展示）
        self.sniffed = 0                       # 已解密的 AI 请求数
        self.passthru = 0                      # 直通（未解密）连接数
        self.failed = 0

    # ------------- 生命周期

    def run(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen(128)
            srv.settimeout(0.6)
        except OSError as e:
            self.error = f"代理启动失败（{self.addr}）：{e}"
            self.q.put(("proxy", self.error))
            self.running = False
            return
        self._srv = srv
        self.running = True
        self.q.put(("proxy", f"网络直采运行中 · {self.addr}"))
        while not self.stop_flag.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,),
                             daemon=True).start()
        self.running = False
        try:
            srv.close()
        except OSError:
            pass
        self.q.put(("proxy", "网络直采已停止"))

    def stop(self):
        self.stop_flag.set()
        try:
            if self._srv is not None:
                self._srv.close()
        except OSError:
            pass

    def set_port(self, port):
        self.port = int(port)
        self.addr = f"{self.host}:{int(port)}"

    # ------------- 连接处理

    def _handle(self, conn):
        try:
            conn.settimeout(300)
            br = BufReader(conn)
            head = br.read_until(b"\r\n\r\n")
            lines = head[:-4].split(b"\r\n")
            parts = lines[0].split()
            if len(parts) < 2:
                return
            method = parts[0].decode("latin1").upper()
            target = parts[1].decode("latin1")
            version = parts[2].decode("latin1") if len(parts) > 2 else "HTTP/1.1"
            headers = _parse_headers(lines[1:])
            if method == "CONNECT":
                self._do_connect(conn, br, target)
            else:
                self._do_http(conn, br, method, target, headers, version)
        except (OSError, EOFError, ValueError):
            pass
        except Exception as e:
            self.error = f"代理异常: {e}"
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _should_mitm(self, host, port=443):
        if not self.ca.available:
            return False
        if is_ai_host(host, self.extra_hosts):
            return True
        if self.mitm_all:
            return True
        if self.auto_probe:
            c = self.probe_cache.get(host)
            if c is True:            # 上次探测确认是中转
                return True
            if c is False:           # 上次探测确认不是，别再打扰它
                return False
            return is_probe_host(host, port)
        return False

    def _do_connect(self, conn, br, target):
        host, _, port_s = target.partition(":")
        try:
            port = int(port_s or 443)
        except ValueError:
            port = 443
        conn.sendall(b"HTTP/1.1 200 Connection Established\r\n"
                     b"Proxy-Agent: TokenMon\r\n\r\n")
        if not self._should_mitm(host, port):
            with self._lock:
                self.passthru += 1
            self._tunnel(conn, br, host, port)
            return
        pair = self.ca.leaf_for(host)
        if not pair:
            self._tunnel(conn, br, host, port)
            return
        cert_p, key_p = pair
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert_p, key_p)
            ctx.set_alpn_protocols(["http/1.1"])
            ctx.options |= ssl.OP_NO_COMPRESSION
            tls = ctx.wrap_socket(conn, server_side=True)
        except (ssl.SSLError, OSError):
            # 客户端不信任本证书，或客户端要求 HTTP/2 —— 无法解密
            with self._lock:
                self.failed += 1
            return
        try:
            tbr = BufReader(tls)
            while not self.stop_flag.is_set():
                try:
                    head = tbr.read_until(b"\r\n\r\n")
                except (EOFError, OSError, ssl.SSLError, ValueError):
                    break
                lines = head[:-4].split(b"\r\n")
                parts = lines[0].split()
                if len(parts) < 2:
                    break
                method = parts[0].decode("latin1").upper()
                path = parts[1].decode("latin1")
                version = parts[2].decode("latin1") if len(parts) > 2 \
                    else "HTTP/1.1"
                headers = _parse_headers(lines[1:])
                keep = self._proxy_one(tls, tbr, method, path, version,
                                       headers, host, port, True)
                if not keep:
                    break
        except Exception:
            pass
        finally:
            try:
                tls.close()
            except OSError:
                pass

    def _do_http(self, conn, br, method, target, headers, version):
        """明文 HTTP：形如 GET http://host/path HTTP/1.1"""
        m = re.match(r"^https?://([^/]+)(/.*)?$", target or "")
        if not m:
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n"
                         b"\r\n")
            return
        hostport, path = m.group(1), m.group(2) or "/"
        host, _, port_s = hostport.partition(":")
        port = int(port_s or 80)
        self._proxy_one(conn, br, method, path, version, headers, host, port,
                        False)

    def _proxy_one(self, csock, br, method, path, version, headers, host, port,
                   secure):
        """转发单个请求并回传响应；返回是否保持客户端连接。"""
        body = b""
        try:
            if "chunked" in headers.get("transfer-encoding", "").lower():
                body = br.read_chunked()
            elif headers.get("content-length"):
                body = br.read_exact(int(headers["content-length"]))
        except (EOFError, OSError, ValueError):
            return False

        known = is_ai_host(host, self.extra_hosts)
        sniff = known or is_ai_path(path)
        if not known and not self.mitm_all:
            # 探测结论落到缓存：是中转就一直解密，不是就再也不碰
            self.probe_cache[host] = sniff
            if sniff and host not in self.probe_hits:
                self.probe_hits.append(host)
        state = None
        t0 = now_s()
        if sniff:
            state = self._new_state(headers, body, t0, host, path)

        # ---- 建立到真实服务器的连接（每请求一条，简单可靠）
        try:
            raw = socket.create_connection((host, port), timeout=30)
        except OSError as e:
            self._send_err(csock, 502, f"无法连接上游 {host}:{port} — {e}")
            with self._lock:
                self.failed += 1
            return False
        up = None
        try:
            if secure:
                try:
                    up = _upstream_ctx().wrap_socket(raw, server_hostname=host)
                except (ssl.SSLError, OSError) as e:
                    self._send_err(csock, 502,
                                   f"上游 TLS 握手失败 {host} — {e}")
                    with self._lock:
                        self.failed += 1
                    return False
            else:
                up = raw
            up.settimeout(600)

            drop = {"proxy-connection", "connection", "keep-alive",
                    "proxy-authorization"}
            clean = {k: v for k, v in headers.items() if k.lower() not in drop}
            clean["Connection"] = "close"
            up.sendall(_rebuild_head(method, path, version, clean, set()))
            if body:
                up.sendall(body)

            ubr = BufReader(up)
            return self._relay_response(csock, ubr, method, state, headers)
        except (OSError, ssl.SSLError, EOFError, ValueError):
            return False
        finally:
            try:
                if up is not None:
                    up.close()
            except OSError:
                pass
            if state is not None:
                self._finish(state)

    @staticmethod
    def _send_err(csock, code, text):
        """把上游故障翻译成明确的 HTTP 错误，避免客户端只看到连接被重置。"""
        try:
            body = f"TokenMon 直采代理: {text}".encode("utf-8")
            csock.sendall(f"HTTP/1.1 {code} Bad Gateway\r\n"
                          f"Content-Type: text/plain; charset=utf-8\r\n"
                          f"Content-Length: {len(body)}\r\n"
                          f"Connection: close\r\n\r\n".encode("latin1") + body)
        except OSError:
            pass

    def _relay_response(self, csock, ubr, method, state, req_headers):
        head = ubr.read_until(b"\r\n\r\n")
        lines = head[:-4].split(b"\r\n")
        status = 0
        m = re.match(r"HTTP/[\d.]+\s+(\d+)", lines[0].decode("latin1"))
        if m:
            status = int(m.group(1))
        hdr = _parse_headers(lines[1:])
        ctype = hdr.get("content-type", "").lower()
        if state is not None:
            state["status"] = status
            state["mode"] = "sse" if "event-stream" in ctype else "json"

        csock.sendall(head)
        no_body = (method == "HEAD" or status in (204, 304) or
                   100 <= status < 200)
        if no_body:
            return False

        te = hdr.get("transfer-encoding", "").lower()
        cl = hdr.get("content-length")
        if state is None:
            def feed(_b):
                return
        else:
            def feed(b, _s=state):
                self._safe_feed(_s, b)

        try:
            if "chunked" in te:
                while True:
                    line = ubr.read_until(b"\r\n")
                    csock.sendall(line)
                    try:
                        n = int(line.split(b";")[0].strip() or b"0", 16)
                    except ValueError:
                        return False
                    if n == 0:
                        while True:
                            l = ubr.read_until(b"\r\n")
                            csock.sendall(l)
                            if l in (b"\r\n", b"\n"):
                                break
                        break
                    data = ubr.read_exact(n + 2)
                    csock.sendall(data)
                    feed(data[:-2])
            elif cl:
                left = int(cl)
                while left > 0:
                    data = ubr.read_exact(min(left, RELAY_CHUNK))
                    left -= len(data)
                    csock.sendall(data)
                    feed(data)
            else:
                while True:
                    try:
                        data = ubr.read_some(RELAY_CHUNK)
                    except EOFError:
                        break
                    csock.sendall(data)
                    feed(data)
        except (OSError, EOFError, ssl.SSLError, ValueError):
            return False
        conn_hdr = hdr.get("connection", "").lower()
        return "close" not in conn_hdr and "close" not in \
            req_headers.get("connection", "").lower()

    def _tunnel(self, c, br, host, port):
        """非 AI 域名：原样双向转发，不解密、不解析。"""
        try:
            up = socket.create_connection((host, port), timeout=20)
        except OSError:
            return
        up.settimeout(None)
        try:
            if br.buf:
                up.sendall(br.buf)
                br.buf = b""
        except OSError:
            pass

        def pipe(src, dst):
            try:
                while not self.stop_flag.is_set():
                    d = src.recv(RELAY_CHUNK)
                    if not d:
                        break
                    dst.sendall(d)
            except OSError:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        t1 = threading.Thread(target=pipe, args=(c, up), daemon=True)
        t2 = threading.Thread(target=pipe, args=(up, c), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        try:
            up.close()
        except OSError:
            pass

    # ------------- 流量解析

    def _new_state(self, headers, body, t0, host, path):
        with self._lock:
            self._seq += 1
            tid = f"proxy:{self._seq}"
            self.sniffed += 1
        model = ""
        stream = False
        req_text = ""
        if body:
            try:
                d = json.loads(body.decode("utf-8", "replace"))
            except ValueError:
                d = None
            if isinstance(d, dict):
                for k in ("model", "modelId", "model_id", "model_name"):
                    v = d.get(k)
                    if isinstance(v, str) and v:
                        model = v
                        break
                stream = bool(d.get("stream"))
                acc = []
                collect_input_text(d, acc)
                req_text = "".join(acc)
                if not model:
                    for k in ("model", "modelId"):
                        v = (d.get("metadata") or {}).get(k) \
                            if isinstance(d.get("metadata"), dict) else None
                        if isinstance(v, str) and v:
                            model = v
                            break
        if not model:
            model = model_from_path(path)
        model = self._clean_model(model)
        state = {
            "tid": tid, "model": model, "resp_model": "",
            "provider": guess_provider(model) or "未知",
            "usage": None, "chars": 0, "tok_est": 0, "raw": bytearray(),
            "buf": "", "mode": "json", "probe_done": False, "stream": stream,
            "req_text": req_text,
            "t_start": t0, "t_end": 0.0, "status": 0, "path": path, "host": host,
            "model_key": ("proxy", guess_provider(model) or "未知",
                          model or "unknown"),
        }
        if self.meter:
            try:
                self.meter.note_started(tid, state["model_key"])
            except Exception:
                pass
        with self._lock:
            self.active[tid] = {"start": t0, "model_key": state["model_key"]}
        return state

    @staticmethod
    def _clean_model(model):
        if not model:
            return ""
        m = str(model).strip()
        m = re.sub(r"[-_](\d{8}|\d{4}-\d{2}-\d{2})$", "", m)   # 去掉日期后缀
        m = re.sub(r"[-_]v\d+(\.\d+)*$", "", m)
        return m or str(model).strip()

    def _safe_feed(self, state, data):
        """解析异常绝不能影响正常转发 —— 代理的第一职责是让流量通。"""
        try:
            self._feed(state, data)
        except Exception:
            pass

    def _feed(self, state, data):
        if not data:
            return
        raw = state["raw"]
        if len(raw) < SNIFF_MAX_BYTES:
            raw.extend(data[:SNIFF_MAX_BYTES - len(raw)])
        if state["mode"] == "sse":
            self._feed_sse(state, data)
        else:
            self._feed_json_probe(state, data)

    def _feed_json_probe(self, state, data):
        """非 SSE 声明的响应：先探一下是否其实是事件流，否则按整体 JSON 解析。"""
        if state["probe_done"]:
            return
        head = bytes(state["raw"][:24]).lstrip().lower()
        if head.startswith(b"data:") or head.startswith(b"event:") or \
                head.startswith(b"id:"):
            state["mode"] = "sse"
            state["buf"] = ""
            state["probe_done"] = True
            self._feed_sse(state, bytes(state["raw"]))
            return
        if len(state["raw"]) > 4096:
            state["probe_done"] = True

    def _feed_sse(self, state, data):
        text = data.decode("utf-8", "replace")
        state["buf"] += text
        *lines, state["buf"] = state["buf"].split("\n")
        if len(state["buf"]) > 1 << 20:      # 异常长的半行，丢弃防止内存膨胀
            state["buf"] = state["buf"][-4096:]
        for ln in lines:
            ln = ln.strip()
            if not ln or ln.startswith(":"):
                continue
            if ln.startswith(("data:", "data :")):
                payload = ln.split(":", 1)[1].strip()
            elif ln.startswith("{"):
                payload = ln
            else:
                continue
            if not payload or payload == "[DONE]":
                continue
            try:
                d = json.loads(payload)
            except ValueError:
                continue
            self._absorb(state, d)

    def _absorb(self, state, d):
        if not isinstance(d, dict):
            return
        if not state["resp_model"]:
            for k in ("model", "modelId", "model_name", "modelVersion",
                      "model_version", "modelName"):
                v = d.get(k)
                if isinstance(v, str) and v:
                    state["resp_model"] = self._clean_model(v)
                    break
        for key in ("usage", "usageMetadata", "token_usage", "tokenUsage",
                    "usage_metadata"):
            v = d.get(key)
            if isinstance(v, dict):
                u = extract_usage(v)
                if u:
                    prev = state["usage"] or {}
                    merged = dict(prev)
                    for k, vv in u.items():
                        if k == "inclusive":
                            merged[k] = vv
                        else:
                            merged[k] = max(merged.get(k, 0), vv)
                    state["usage"] = merged
        msg = d.get("message")
        if isinstance(msg, dict):
            u = extract_usage(msg.get("usage") or {})
            if u:
                prev = state["usage"] or {}
                merged = dict(prev)
                for k, vv in u.items():
                    if k == "inclusive":
                        merged[k] = vv
                    else:
                        merged[k] = max(merged.get(k, 0), vv)
                state["usage"] = merged
        out = []
        collect_output_text(d, out)
        if out:
            add = "".join(out)
            state["chars"] += len(add)
            state["tok_est"] += estimate_tokens(add)
            self._bump_rate(state)

    def _bump_rate(self, state):
        if not self.meter or not state["tok_est"]:
            return
        try:
            el = max(now_s() - state["t_start"], 0.05)
            self.meter.set_rate(state["tid"], state["tok_est"] / el)
        except Exception:
            pass

    def _finish(self, state):
        """请求结束：产出统计记录。"""
        t1 = now_s()
        state["t_end"] = t1
        if self.meter:
            try:
                self.meter.note_finished(state["tid"])
            except Exception:
                pass
        with self._lock:
            self.active.pop(state["tid"], None)

        # 非流式响应：整体解析一次（拿模型名与 usage）
        if state["mode"] != "sse" and state["raw"]:
            try:
                d = json.loads(bytes(state["raw"]).decode("utf-8", "replace"))
            except ValueError:
                d = None
            if isinstance(d, dict):
                self._absorb(state, d)
                if state["usage"] is None:
                    u = extract_usage(d)
                    if u:
                        state["usage"] = u

        model = state["model"] or state["resp_model"] or "unknown"
        provider = guess_provider(model) or "未知"
        norm = normalize_usage(state["usage"])
        # 只有真正拿到 2xx 响应才允许用估算补数，避免把失败的调用也计入 tokens
        ok = 200 <= state["status"] < 300
        est = False
        if norm["out"] == 0 and ok and state["tok_est"]:
            norm["out"] = state["tok_est"]
            est = True
        if norm["inp"] == 0 and ok and state["req_text"]:
            norm["inp"] = estimate_tokens(state["req_text"])
            est = True
        if not (norm["inp"] or norm["out"] or norm["cache_r"] or norm["cache_w"]):
            return
        dur = max(t1 - state["t_start"], 0.0)
        rec = {
            "ts": t1, "source": "proxy", "provider": provider, "model": model,
            "inp": norm["inp"], "out": norm["out"], "cache_r": norm["cache_r"],
            "cache_w": norm["cache_w"], "dur": dur, "key": state["tid"],
            "session": None,
        }
        entry = {"ts": t1, "model": model, "provider": provider,
                 "inp": norm["inp"], "out": norm["out"], "dur": dur,
                 "est": est, "status": state["status"],
                 "host": state["host"]}
        with self._lock:
            self.recent.appendleft(entry)
        try:
            self.emit(rec)
        except Exception:
            pass
        self.q.put(("proxy_rec", entry))

    def active_snapshot(self):
        now = now_s()
        with self._lock:
            return [(t, v["start"], v["model_key"]) for t, v in
                    self.active.items() if now - v["start"] < STALE_INFLIGHT_S]

    def status(self):
        with self._lock:
            return {
                "running": self.running, "addr": self.addr,
                "sniffed": self.sniffed, "passthru": self.passthru,
                "failed": self.failed, "active": len(self.active),
                "error": self.error,
            }


# ---------------------------------------------------------------- watcher

class Watcher(threading.Thread):
    def __init__(self, stats, meter, ui_queue, extra_dirs=None, demo=False):
        super().__init__(daemon=True, name="watcher")
        self.stats = stats
        self.meter = meter
        self.q = ui_queue
        self.extra_dirs = extra_dirs or []
        self.demo = demo
        self.scan_logs = True     # 是否扫描本地日志（关掉后只统计网络直采数据）
        self.stop_flag = threading.Event()
        self.offsets = {}        # path -> (size, mtime_ns)
        self.partials = {}       # path -> 未成行的尾部字节
        self.seen_keys = set()   # 近期记录去重
        self.logged_keys = set() # 已写进 records.jsonl 的键（防止回填/重扫造成重复落盘）
        self.ctx_chars = {}      # path -> [CJK字符数, 其它字符数]，用于缺输入用量时估算
        self.active = {}         # trace_id -> (start_ts, session_id)
        self.session_model = {}  # session_id -> model_key
        self.file_stats = {"zcode": 0, "zlog": 0, "claude": 0, "workbuddy": 0,
                           "codex": 0, "opencode": 0, "extra": 0}
        self.last_save = 0.0
        self.log_fh = None
        self._claude_files = []   # 递归目录的文件列表缓存（避免每秒 os.walk）
        self._wb_files = []
        self._codex_files = []
        self._extra_files = []
        self._codex_model = {}    # rollout 文件 -> 当前模型名（Codex 用量行不带模型）
        self._oc_db = None        # OpenCode 的 SQLite（非文件源，单独轮询）
        self._oc_last = 0         # 已处理到的 time_updated
        self._last_oc_poll = 0.0
        self._last_walk = 0.0

    # ------------- file scanning

    def _files(self, walk=True):
        out = {"zcode": [], "zlog": [], "claude": [], "workbuddy": [],
               "codex": [], "extra": []}
        if not self.scan_logs:
            return out
        if os.path.isdir(ZCODE_ROLLOUT_DIR):
            out["zcode"] = [os.path.join(ZCODE_ROLLOUT_DIR, f)
                            for f in os.listdir(ZCODE_ROLLOUT_DIR)
                            if f.startswith("model-io-") and f.endswith(".jsonl")]
        if os.path.isdir(ZCODE_LOG_DIR):
            out["zlog"] = [os.path.join(ZCODE_LOG_DIR, f)
                           for f in os.listdir(ZCODE_LOG_DIR)
                           if f.startswith("zcode-") and f.endswith(".jsonl")]
        if walk:
            found = []
            if os.path.isdir(CLAUDE_PROJECTS_DIR):
                for root, _dirs, files in os.walk(CLAUDE_PROJECTS_DIR):
                    found.extend(os.path.join(root, f) for f in files if f.endswith(".jsonl"))
            self._claude_files = found
            # WorkBuddy 会话转录（注意排除 *.file-rollback.ndjson / *.meta.json）
            wb = []
            if os.path.isdir(WORKBUDDY_PROJECTS_DIR):
                for root, _dirs, files in os.walk(WORKBUDDY_PROJECTS_DIR):
                    wb.extend(os.path.join(root, f) for f in files
                              if f.endswith(".jsonl"))
            self._wb_files = wb
            # Codex 会话 rollout（含 archived_sessions，归档也算历史用量）
            cx = []
            for d in codex_session_dirs():
                for root, _dirs, files in os.walk(d):
                    cx.extend(os.path.join(root, f) for f in files
                              if f.startswith("rollout-") and f.endswith(".jsonl"))
            self._codex_files = cx
            extra = []
            for d in self.extra_dirs:
                if os.path.isdir(d):
                    for root, _dirs, files in os.walk(d):
                        extra.extend(os.path.join(root, f) for f in files if f.endswith(".jsonl"))
            self._extra_files = extra
        out["claude"] = self._claude_files
        out["workbuddy"] = self._wb_files
        out["codex"] = self._codex_files
        out["extra"] = self._extra_files
        return out

    def _read_new(self, path):
        """增量读取文件新增内容，返回完整的行列表。"""
        try:
            st = os.stat(path)
        except OSError:
            self.offsets.pop(path, None)
            self.partials.pop(path, None)
            return None
        size, mtime = st.st_size, st.st_mtime_ns
        prev = self.offsets.get(path)
        if prev and size < prev[0]:
            prev = None  # 文件被截断/重建
        if prev and prev[0] == size and prev[1] == mtime:
            return []
        start = prev[0] if prev else 0
        lines = []
        try:
            with open(path, "rb") as f:
                f.seek(start)
                chunk = f.read()
        except OSError:
            return None
        buf = self.partials.pop(path, b"") + chunk
        *complete, tail = buf.split(b"\n")
        lines = complete
        if tail:
            self.partials[path] = tail  # 不足一行，留待下次
        self.offsets[path] = (size, mtime)
        return [ln for ln in (l.strip() for l in lines) if ln]

    # ------------- record handling

    def _emit(self, rec):
        if rec["key"] and rec["key"] in self.seen_keys:
            return
        if rec["key"]:
            self.seen_keys.add(rec["key"])
            if len(self.seen_keys) > 50000:
                self.seen_keys = set(list(self.seen_keys)[-20000:])
        model_key = (rec["source"], rec["provider"], rec["model"])
        self.stats.add(rec)
        self.meter.add_record(rec, model_key)
        if rec.get("session"):
            self.session_model[rec["session"]] = model_key
        if not self.demo:
            self._log_record(rec)
        self.q.put(("record", rec))

    def _parse_line(self, kind, line, path=None):
        """按来源分派到对应的解析器。"""
        if kind == "zcode":
            return parse_zcode_rollout(line)
        if kind == "workbuddy":
            return parse_workbuddy(line)
        if kind == "codex":
            d = _as_dict(line)
            if d is None:
                return None
            # 模型名不写在用量行里，靠同文件的其它行记住最近一次设置
            m = codex_model_of(d)
            if m:
                self._codex_model[path] = m
            return parse_codex(d, self._codex_model.get(path))
        return parse_claude(line)        # claude / extra 都是 Claude Code 格式

    def _log_record(self, rec):
        """明细日志：每条请求追加写入 records.jsonl（同一 key 只写一次）。

        回填历史时会先把键登记进 logged_keys，避免紧接着的首次全量扫描
        把同一批记录又写一遍 —— 那正是「导出数据条数翻倍」的原因。
        """
        key = rec.get("key")
        if key and key in self.logged_keys:
            return
        if key:
            self.logged_keys.add(key)
        try:
            if self.log_fh is None:
                os.makedirs(APP_DIR, exist_ok=True)
                self.log_fh = open(LOG_FILE, "a", encoding="utf-8")
            self.log_fh.write(json.dumps(log_row(rec), ensure_ascii=False) + "\n")
            self.log_fh.flush()
        except OSError:
            pass

    def _apply_est(self, rec, path, ctx=None):
        """输入用量缺失时（第三方中转不回传 prompt_tokens），
        用本会话到这一轮为止已出现的对话文本量做字符估算。"""
        if not rec.get("est") or rec["out"] <= 0:
            return
        acc = (self.ctx_chars if ctx is None else ctx).get(path)
        guess = weight_to_tokens(acc)
        if guess > rec["cache_r"]:
            rec["inp"] = guess - rec["cache_r"]

    def _backfill_log(self):
        """首次使用时把全部历史记录一次性补写进明细日志（不影响统计数字）。"""
        try:
            if os.path.exists(LOG_FILE):
                return
            os.makedirs(APP_DIR, exist_ok=True)
            n = 0
            # 用局部的 ctx 计数做估算，别写进 self.ctx_chars ——
            # 紧接着的首次全量扫描还会再累计一遍，共用会翻倍。
            ctx = {}
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                for kind, paths in self._files().items():
                    if kind not in ("zcode", "claude", "workbuddy", "codex",
                                    "extra"):
                        continue
                    track = kind in ("claude", "extra", "workbuddy")
                    for p in paths:
                        try:
                            with open(p, "rb") as fh:
                                raw = fh.read().decode("utf-8", errors="replace")
                        except OSError:
                            continue
                        for line in raw.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            d = _as_dict(line)
                            if d is None:
                                continue
                            rec = self._parse_line(kind, d, p)
                            if rec:
                                if track:
                                    self._apply_est(rec, p, ctx)
                                key = rec.get("key")
                                if key and key in self.logged_keys:
                                    continue      # 同一调用被写多条（Claude Code 常见）
                                if key:
                                    self.logged_keys.add(key)
                                f.write(json.dumps(log_row(rec),
                                                   ensure_ascii=False) + "\n")
                                n += 1
                            if track:
                                text_weight(d, ctx.setdefault(p, [0, 0]))
                # OpenCode 是 SQLite，不走文件那套
                n += self._backfill_opencode(f)
            self.q.put(("status", f"已回填 {n} 条历史记录"))
        except Exception as e:  # 回填失败不影响监控
            self.q.put(("error", f"回填历史明细失败: {e}"))

    def _backfill_opencode(self, f):
        """把 OpenCode 的历史用量补写进明细日志，返回写入条数。"""
        path = opencode_db()
        if not path:
            return 0
        n = 0
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"),
                                   uri=True, timeout=5.0)
            rows = conn.execute(
                "select id, session_id, data from message "
                "order by time_updated").fetchall()
            conn.close()
        except sqlite3.Error:
            return 0
        for mid, sid, raw in rows:
            try:
                d = json.loads(raw)
            except (ValueError, TypeError):
                continue
            rec = parse_opencode(mid, sid, d)
            if not rec:
                continue
            key = rec.get("key")
            if key and key in self.logged_keys:
                continue
            if key:
                self.logged_keys.add(key)
            f.write(json.dumps(log_row(rec), ensure_ascii=False) + "\n")
            n += 1
        return n

    def _handle_lines(self, kind, path, lines):
        # 这几类是按「对话轮次」增长的日志，需要顺带累计文本量，供输入缺失时估算
        track_ctx = kind in ("claude", "extra", "workbuddy")
        for line in lines:
            try:
                if kind == "zlog":
                    ev = parse_zcode_log_event(line)
                    if not ev:
                        continue
                    typ, tid, sid = ev
                    if typ == "started":
                        self.active[tid] = (now_s(), sid)
                        mk = self.session_model.get(sid)
                        self.meter.note_started(tid, mk)
                        self.q.put(("started", {"tid": tid, "sid": sid}))
                    else:
                        self.active.pop(tid, None)
                        self.meter.note_finished(tid)
                        self.q.put(("finished", {"tid": tid}))
                    continue
                d = _as_dict(line)
                if d is None:
                    continue
                rec = self._parse_line(kind, d, path)
                if rec:
                    self._apply_est(rec, path)
                    self._emit(rec)
                if track_ctx:
                    # 本行的文本留到下一轮才算进上下文（本轮 prompt 不含模型自己的输出）
                    text_weight(d, self.ctx_chars.setdefault(path, [0, 0]))
            except Exception as e:  # 单行异常不影响整体
                sys.stderr.write(f"解析行失败({path}): {e}\n")

    def _poll_opencode(self, force=False):
        """OpenCode 把用量存在 SQLite 里，没有 jsonl 可增量读，单独轮询。

        只读打开（mode=ro），按 time_updated 增量取；每条 message 的 id 就是
        去重键，重复扫也不会重复计数。
        """
        if not self.scan_logs:
            return False
        now = now_s()
        if not force and now - self._last_oc_poll < 20.0:
            return False
        self._last_oc_poll = now
        if self._oc_db is None:
            self._oc_db = opencode_db()
        path = self._oc_db
        self.file_stats["opencode"] = 1 if path else 0
        if not path:
            return False
        got = False
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"),
                                   uri=True, timeout=2.0)
        except sqlite3.Error:
            return False
        try:
            rows = conn.execute(
                "select id, session_id, data from message "
                "where time_updated > ? order by time_updated",
                (self._oc_last,)).fetchall()
        except sqlite3.Error:
            rows = []
        finally:
            conn.close()
        for mid, sid, raw in rows:
            try:
                d = json.loads(raw)
            except (ValueError, TypeError):
                continue
            rec = parse_opencode(mid, sid, d)
            if rec:
                self._emit(rec)
                got = True
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"),
                                   uri=True, timeout=2.0)
            mx = conn.execute("select max(time_updated) from message").fetchone()
            conn.close()
            if mx and mx[0]:
                self._oc_last = int(mx[0])
        except sqlite3.Error:
            pass
        return got

    def poll(self):
        """扫描一轮；返回是否有新内容（用于自适应调节扫描频率）。"""
        now = now_s()
        do_walk = now - self._last_walk >= WALK_EVERY_S
        if do_walk:
            self._last_walk = now
        files = self._files(do_walk)
        had_new = False
        for kind, paths in files.items():
            self.file_stats[kind] = len(paths)
            for p in paths:
                lines = self._read_new(p)
                if lines:
                    had_new = True
                    self._handle_lines(kind, p, lines)
        try:
            if self._poll_opencode():
                had_new = True
        except Exception as e:
            sys.stderr.write(f"OpenCode 扫描失败: {e}\n")
        # 清理已消失文件的偏移与上下文计数
        alive = set(sum(files.values(), []))
        for p in list(self.offsets):
            if p not in alive:
                del self.offsets[p]
                self.partials.pop(p, None)
                self.ctx_chars.pop(p, None)
        self.q.put(("filestats", dict(self.file_stats)))
        return had_new

    def active_snapshot(self):
        now = now_s()
        with_stats = [(t, v[0], self.session_model.get(v[1])) for t, v in self.active.items()]
        return [(t, s, m) for t, s, m in with_stats if now - s < STALE_INFLIGHT_S]

    def run(self):
        try:
            if not self.demo:
                self._backfill_log()
            while not self.stop_flag.is_set():
                if not self.demo:  # 演示模式不读真实文件
                    try:
                        had_new = self.poll()
                    except Exception as e:
                        had_new = False
                        self.q.put(("error", str(e)))
                    if now_s() - self.last_save > SAVE_EVERY_S:
                        self.stats.save(self.offsets)   # 内部有 dirty 检查
                        self.last_save = now_s()
                    # 有新数据或生成中 → 快扫保实时；空闲 → 慢扫省 CPU
                    busy = had_new or bool(self.active_snapshot())
                    self.stop_flag.wait(POLL_FAST_S if busy else POLL_SLOW_S)
                else:
                    self.stop_flag.wait(POLL_FAST_S)
            if not self.demo:
                self.stats.save(self.offsets)
        except Exception as e:
            self.q.put(("error", f"监控线程退出: {e}"))


# ---------------------------------------------------------------- demo source

class DemoSource(threading.Thread):
    """演示模式：合成假的请求开始/结束/记录，走真实处理管线。"""

    MODELS = [("zcode", "bigmodel", "GLM-5.3-Flash"),
              ("zcode", "bigmodel", "GLM-4.7"),
              ("claude-code", "anthropic", "claude-sonnet-4-5")]

    def __init__(self, stats, meter, ui_queue, watcher):
        super().__init__(daemon=True)
        self.stats, self.meter, self.q, self.watcher = stats, meter, ui_queue, watcher
        self.stop_flag = threading.Event()
        self.n = 0

    def run(self):
        while not self.stop_flag.is_set():
            source, provider, model = self.MODELS[self.n % len(self.MODELS)]
            dur = 2.0 + (self.n * 7 % 40) / 3.0
            out = int(dur * (35 + (self.n * 13 % 45)))
            inp = 5000 + (self.n * 997 % 90000)
            tid = f"demo-{self.n}"
            self.watcher.active[tid] = (now_s(), "sess_demo")
            self.watcher.session_model["sess_demo"] = (source, provider, model)
            self.meter.note_started(tid, (source, provider, model))
            self.q.put(("started", {"tid": tid, "sid": "sess_demo"}))
            time.sleep(min(dur, 3.0))
            rec = {"ts": now_s(), "source": source, "provider": provider, "model": model,
                   "inp": inp, "out": out, "cache_r": inp * 3, "cache_w": 0,
                   "dur": dur, "key": f"demo-{self.n}", "session": "sess_demo"}
            self.watcher._emit(rec)
            self.watcher.active.pop(tid, None)
            self.meter.note_finished(tid)
            self.q.put(("finished", {"tid": tid}))
            self.n += 1
            self.stop_flag.wait(0.4)


# ---------------------------------------------------------------- GUI

BG = "#070b11"
PANEL = "#0d1420"
PANEL2 = "#0a0f18"
FG = "#e8eaed"
DIM = "#7c8798"
ACCENT = "#4ade80"
ACCENT2 = "#22d3ee"
WARN = "#fbbf24"
BORDER = "#1e2c40"
ACCENT3 = "#a78bfa"

COLS = ("model", "provider", "requests", "inp", "out", "cache_r", "cache_w",
        "total", "speed", "last")
COL_HEADERS = ("模型", "厂商", "请求", "输入", "输出", "缓存读", "缓存写",
               "缓存率", "总计", "tok/s", "最后活动")


SOURCE_NAMES = {"zcode": "ZCode", "claude-code": "Claude", "extra": "Extra",
                "workbuddy": "WorkBuddy", "codex": "Codex",
                "opencode": "OpenCode", "proxy": "直采"}


def round_rect(c, x1, y1, x2, y2, r=14, **kw):
    """在 Canvas 上画圆角矩形（12 点平滑多边形）。"""
    r = max(1, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


class RoundButton(tk.Canvas):
    """圆角胶囊按钮：悬停亮边、按下沉色、可选中态。"""

    def __init__(self, parent, text, command=None, width=88, height=30, radius=15):
        super().__init__(parent, bg=BG, highlightthickness=0, width=width,
                         height=height, cursor="hand2")
        self.btn_text = text
        self.command = command
        self.selected = False
        self._inside = False
        self._last_rel = 0.0
        self._min_w = width
        self._font = None
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: (setattr(self, "_inside", True), self._draw()))
        self.bind("<Leave>", lambda e: (setattr(self, "_inside", False), self._draw()))
        self.bind("<Configure>", lambda e: self._draw())
        self.after(50, self._draw)

    def set_text(self, t):
        self.btn_text = t
        self._draw()

    def set_selected(self, sel):
        self.selected = sel
        self._draw()

    def _on_press(self, _e):
        self._draw(pressed=True)

    def _on_release(self, _e):
        now = time.time()
        if now - self._last_rel < 0.3:   # 防抖：过滤重复触发
            return
        self._last_rel = now
        if self.command:
            self.command()
        self._draw()

    def _draw(self, pressed=False):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10:
            return
        # 文字过宽时自动加宽按钮（适配 DPI 缩放），随后 Configure 会触发重绘
        if self._font is None:
            self._font = tkfont.Font(font=("Microsoft YaHei UI", 9))
        need = self._font.measure(self.btn_text) + 40
        if w < need:
            self.configure(width=need)
            return
        c = self
        c.delete("all")
        if self.selected:
            fill, outline, fg = "#123043", ACCENT2, "#7dd3fc"
        elif pressed:
            fill, outline, fg = "#0e1521", "#3b82f6", "#ffffff"
        elif self._inside:
            fill, outline, fg = "#182335", ACCENT2, "#ffffff"
        else:
            fill, outline, fg = PANEL, BORDER, "#c3c9d4"
        round_rect(c, 1, 1, w - 2, h - 2, min(self.winfo_height() / 2 - 1, 15),
                   fill=fill, outline=outline)
        c.create_text(w / 2, h / 2 + 1, text=self.btn_text, fill=fg,
                      font=("Microsoft YaHei UI", 9))


class CornerPatch(tk.Canvas):
    """用背景色扇形遮住 Treeview 的直角，视觉上变成圆角。"""

    def __init__(self, parent, corner, r=14):
        super().__init__(parent, bg=BG, highlightthickness=0, width=r + 2, height=r + 2)
        bbox = {"nw": (-r, -r, r, r, 0, 90), "ne": (0, -r, 2 * r, r, 90, 90),
                "sw": (-r, 0, r, 2 * r, 270, 90), "se": (0, 0, 2 * r, 2 * r, 180, 90)}
        x1, y1, x2, y2, start, extent = bbox[corner]
        self.create_arc(x1, y1, x2, y2, start=start, extent=extent,
                        fill=PANEL, outline=BG)


class HudCard(tk.Canvas):
    """数据面板：hud=科幻(切角霓虹/雷达扫掠) 与 simple=简洁 两种渲染风格。"""

    def __init__(self, parent, icon, title_en, title_cn, accent, value_font):
        super().__init__(parent, bg=BG, highlightthickness=0, height=122, width=10)
        self.icon = icon
        self.title_en = title_en
        self.title_cn = title_cn
        self.accent = accent
        self.value_font = value_font
        self.style = "hud"
        self._font = None           # 数值字体缓存（用于排布单位）
        self._value = "--"
        self._unit = ""
        self._sub = ""
        self._sub_color = DIM
        self._active = False
        self._last_key = None       # 内容签名：无变化不重绘（省 CPU）
        self._last_phase = -1
        self._last_paint = 0.0

    @staticmethod
    def _shade(hex_color, f):
        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return "#%02x%02x%02x" % tuple(int(v * f) for v in rgb)

    def set_style(self, style):
        self.style = style
        self._last_key = None       # 风格切换后强制重绘
        self._last_paint = 0.0

    def update_data(self, value, sub, sub_color, active, unit=""):
        self._value, self._unit = value, unit
        self._sub, self._sub_color = sub, sub_color
        self._active = active

    # ---------------------------------------------------------- 科幻风格

    def _render_hud(self, w, h, phase):
        c = self
        c.delete("all")
        accent = self.accent
        # 圆角面板 + 内圈细描边（层次感）
        round_rect(c, 2, 2, w - 3, h - 3, 16, fill=PANEL, outline=BORDER)
        round_rect(c, 5, 5, w - 6, h - 6, 13, fill="", outline="#151d2b")
        # 顶部流动光沿（胶囊形）：活跃时变长流动，空闲时收敛
        flow = 0.72 + 0.28 * ((phase % 10) / 10) if self._active else 0.45
        x2 = 24 + (w - 48) * flow
        col = accent if self._active else self._shade(accent, 0.55)
        c.create_oval(20, 7, 28, 11, fill=col, outline="")
        c.create_rectangle(24, 7, max(x2 - 2, 24), 11, fill=col, outline="")
        c.create_oval(x2 - 4, 7, x2 + 4, 11, fill=col, outline="")
        # 圆形图标徽章 + 标题行
        badge = accent if self._active else self._shade(accent, 0.7)
        c.create_oval(18, 18, 36, 36, outline=badge)
        c.create_text(27, 27, text=self.icon, fill=badge,
                      font=("Microsoft YaHei UI", 9))
        c.create_text(44, 27, anchor="w", text=self.title_en,
                      fill=DIM, font=("Consolas", 8, "bold"))
        c.create_text(w - 18, 27, anchor="e", text=self.title_cn,
                      fill=DIM, font=("Microsoft YaHei UI", 8))
        c.create_line(18, 44, w - 18, 44, fill="#1b2739")
        # 数值：暗色偏移垫底 → 主色（辉光），单位小字沿基线排布
        if self._font is None:
            self._font = tkfont.Font(font=self.value_font)
        c.create_text(20, 74, text=self._value, font=self.value_font,
                      fill=self._shade(accent, 0.25), anchor="w")
        c.create_text(18, 72, text=self._value, font=self.value_font,
                      fill=accent if self._active else FG, anchor="w")
        if self._unit:
            ux = 18 + self._font.measure(self._value) + 7
            uy = 72 + int(self._font.metrics("linespace") * 0.32)
            c.create_text(ux, uy, text=self._unit, anchor="w",
                          font=("Consolas", 9), fill=DIM)
        # 副读数：主题色圆点 + 等宽文本
        cy_sub = h - 16
        c.create_oval(19, cy_sub - 3, 25, cy_sub + 3,
                      fill=self._sub_color if self._sub_color != DIM
                      else self._shade(accent, 0.8), outline="")
        c.create_text(32, cy_sub, anchor="w", text=self._sub, fill=self._sub_color,
                      font=("Consolas", 8))
        # 右下角雷达扫掠环（含方位刻度）
        cx, cy, r = w - 34, h - 34, 12
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=BORDER)
        c.create_oval(cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5,
                      outline=BORDER)
        for ang in (0, 90, 180, 270):
            x1 = cx + (r + 2) * math.cos(math.radians(ang))
            y1 = cy + (r + 2) * math.sin(math.radians(ang))
            x2 = cx + (r + 5) * math.cos(math.radians(ang))
            y2 = cy + (r + 5) * math.sin(math.radians(ang))
            c.create_line(x1, y1, x2, y2, fill=BORDER)
        start = (phase * 8) % 360
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=start, extent=80,
                     style="arc", width=2,
                     outline=accent if self._active else self._shade(DIM, 0.8))
        dot = 2.5 if (self._active and phase % 6 < 3) else 1.5
        c.create_oval(cx - dot, cy - dot, cx + dot, cy + dot,
                      fill=accent if self._active else DIM, outline="")

    # ---------------------------------------------------------- 简洁风格

    def _render_simple(self, w, h):
        c = self
        c.delete("all")
        round_rect(c, 2, 2, w - 3, h - 3, 14, fill=PANEL, outline=BORDER)
        c.create_text(18, 18, anchor="w", text=self.title_cn,
                      fill=DIM, font=("Microsoft YaHei UI", 9))
        c.create_text(18, 64, text=self._value, font=self.value_font, anchor="w",
                      fill=self.accent if self._active else FG)
        if self._unit:
            if self._font is None:
                self._font = tkfont.Font(font=self.value_font)
            ux = 18 + self._font.measure(self._value) + 6
            uy = 64 + int(self._font.metrics("linespace") * 0.32)
            c.create_text(ux, uy, text=self._unit, anchor="w",
                          font=("Microsoft YaHei UI", 9), fill=DIM)
        c.create_text(18, h - 19, anchor="w", text=self._sub, fill=self._sub_color,
                      font=("Microsoft YaHei UI", 9))

    def render(self, phase):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 60 or h < 60:
            return
        # 空闲且内容无变化 → 完全跳过；有变化/动画时最多 ~2.5 次/秒重绘
        #（画布 delete+重建是最大 UI 开销，节流对低配电脑收益最大）
        key = (w, h, self.style, self._value, self._unit, self._sub,
               self._sub_color, self._active)
        want = key != self._last_key or \
            (self._active and self.style == "hud" and phase != self._last_phase)
        if not want or time.perf_counter() - self._last_paint < 0.4:
            return
        self._last_key = key
        self._last_phase = phase
        self._last_paint = time.perf_counter()
        if self.style == "simple":
            self._render_simple(w, h)
        else:
            self._render_hud(w, h, phase)


class MiniChip(tk.Canvas):
    """极小模式里的迷你指标块（圆角小卡片）。"""

    def __init__(self, parent, title, accent, height=64):
        super().__init__(parent, bg=BG, highlightthickness=0, width=120, height=height)
        self.title_cn, self.accent = title, accent
        self._value = "--"
        self._sub = ""
        self._sub_color = DIM
        self._last_key = None       # 内容签名：无变化不重绘
        self.bind("<Configure>", lambda e: self.render())
        self.after(100, self.render)

    def update_data(self, value, sub="", sub_color=None):
        self._value, self._sub = value, sub
        self._sub_color = sub_color or DIM
        self.render()

    def render(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 40:
            return
        key = (w, h, self._value, self._sub, self._sub_color)
        if key == self._last_key:
            return
        self._last_key = key
        c = self
        c.delete("all")
        round_rect(c, 1, 1, w - 2, h - 2, 12, fill=PANEL, outline=BORDER)
        c.create_oval(12, 13, 16, 17, fill=self.accent, outline="")
        c.create_text(21, 15, anchor="w", text=self.title_cn, fill=DIM,
                      font=("Microsoft YaHei UI", 8))
        if self._sub:
            c.create_text(w - 10, 15, anchor="e", text=self._sub,
                          fill=self._sub_color, font=("Microsoft YaHei UI", 8))
        c.create_text(12, 37, anchor="w", text=self._value,
                      font=("Microsoft YaHei UI", 14, "bold"), fill=FG)


class App(tk.Tk):
    def __init__(self, stats, meter, ui_queue, watcher, demo=False, ca=None):
        super().__init__()
        self.stats = stats
        self.meter = meter
        self.q = ui_queue
        self.watcher = watcher
        self.demo = demo
        cfg = self._load_config()
        self._view = "today"
        self.topmost = bool(cfg.get("always_on_top", False))   # 记忆置顶状态
        self.extra_dirs = cfg.get("extra_dirs", [])
        self.ui_mode = cfg.get("ui_mode", "hud")   # hud=科幻 / simple=简洁
        watcher.extra_dirs = self.extra_dirs
        # ---- 网络直采
        self.ca = ca if ca is not None else CertAuthority()
        self.proxy = None
        self.proxy_extra_hosts = list(cfg.get("proxy_extra_hosts", []))
        self.proxy_mitm_all = bool(cfg.get("proxy_mitm_all", False))
        self.proxy_auto_probe = bool(cfg.get("proxy_auto_probe", True))
        try:
            self._proxy_port = int(cfg.get("proxy_port", PROXY_PORT_DEFAULT))
        except (TypeError, ValueError):
            self._proxy_port = PROXY_PORT_DEFAULT
        self._applied_sys = None    # 系统代理原值（用于还原）
        self._applied_env = None    # 环境变量原值
        watcher.scan_logs = bool(cfg.get("scan_logs", True))
        self._proxy_msg = ""
        self._active_count = 0
        self._active_detail = ""
        self._speed_val = 0.0
        self._disp_speed = 0.0     # 界面上平滑变化的显示值
        self._vmax = None          # 图表纵轴量程（平滑追踪）
        self._last_chart = 0.0
        self._last_table = 0.0
        self._pulse_t = 0
        self._file_stats = {}
        self._rate_cache = None     # 总缓存率缓存（避免每 tick 全量快照）
        self._rate_ts = 0.0
        self._active_now = []       # 本 tick 的生成中请求快照（只算一次）
        self._last_title = ""
        self._rows_sig = None

        self.title(APP_NAME)
        try:  # 窗口/任务栏图标（内嵌 LOGO）
            self.iconphoto(True, tk.PhotoImage(data=APP_ICON_B64))
        except Exception:
            pass
        self.configure(bg=BG)
        self.geometry("1040x690")
        self.minsize(920, 600)
        self._init_style()
        self._build_ui()
        self.after(TICK_MS, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------- style / theme

    def _init_style(self):
        try:
            self.tk.call("tk", "scaling", self.winfo_fpixels("1i") / 72.0)
        except tk.TclError:
            pass
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        base = ("Microsoft YaHei UI", 10)
        style.configure(".", background=BG, foreground=FG, font=base)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Dim.TLabel", background=BG, foreground=DIM)
        style.configure("Big.TLabel", background=PANEL, foreground=ACCENT,
                        font=("Microsoft YaHei UI", 26, "bold"))
        style.configure("Head.TLabel", background=PANEL, foreground=DIM,
                        font=("Microsoft YaHei UI", 9))
        style.configure("Value.TLabel", background=PANEL, foreground=FG,
                        font=("Microsoft YaHei UI", 15, "bold"))
        style.configure("TButton", background=PANEL, foreground=FG, padding=(10, 4))
        style.map("TButton",
                  background=[("active", "#2a3040"), ("pressed", "#333b4d")],
                  foreground=[("active", "#ffffff")])
        style.configure("Tool.TButton", background=BG, foreground=DIM, padding=(8, 2))
        style.map("Tool.TButton",
                  background=[("active", "#232833")],
                  foreground=[("active", FG)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=FG, rowheight=26, borderwidth=0, font=base)
        style.configure("Treeview.Heading", background="#232833", foreground=DIM,
                        font=("Microsoft YaHei UI", 9, "bold"), borderwidth=0, padding=(4, 4))
        style.map("Treeview", background=[("selected", "#31415a")],
                  foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", "#2a3040")])
        style.configure("Vertical.TScrollbar", background="#1a2230",
                        troughcolor=BG, bordercolor=BG, arrowcolor=DIM)
        style.configure("TRadiobutton", background=BG, foreground=DIM)
        style.map("TRadiobutton", foreground=[("selected", ACCENT)])

    def _build_ui(self):
        # ---- header HUD cards
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=12, pady=(10, 4))

        self.card_speed = HudCard(header, "⚡", "TOKEN FLOW", "实时速度", ACCENT,
                                  ("Consolas", 30, "bold"))
        self.card_today = HudCard(header, "◆", "TODAY", "今日 Tokens", ACCENT2,
                                  ("Microsoft YaHei UI", 17, "bold"))
        self.card_total = HudCard(header, "∑", "TOTAL", "累计 Tokens", ACCENT3,
                                  ("Microsoft YaHei UI", 17, "bold"))
        self.card_live = HudCard(header, "◉", "ACTIVE", "模型活动", WARN,
                                 ("Microsoft YaHei UI", 17, "bold"))
        for i, c in enumerate((self.card_speed, self.card_today, self.card_total,
                               self.card_live)):
            c.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 8, 0))

        # ---- speed chart
        chart_panel = tk.Frame(self, bg=BG)
        chart_panel.pack(fill="both", expand=True, padx=12, pady=(8, 4))
        self.chart = tk.Canvas(chart_panel, bg=BG, highlightthickness=0, height=170)
        self.chart.pack(fill="both", expand=True)
        self.chart.bind("<Configure>", lambda e: self._draw_chart())

        # ---- model table
        table_panel = tk.Frame(self, bg=BG)
        table_panel.pack(fill="both", expand=True, padx=12, pady=(4, 4))
        bar = tk.Frame(table_panel, bg=BG)
        bar.pack(fill="x", pady=(0, 4))
        self.lbl_registry = tk.Label(bar, text="▍ 按模型统计",
                                     font=("Consolas", 9, "bold"), bg=BG, fg=ACCENT2)
        self.lbl_registry.pack(side="left")
        self.btn_today = RoundButton(bar, "今日", lambda: self._set_view("today"),
                                     width=62, height=27, radius=13)
        self.btn_today.pack(side="left", padx=(12, 0))
        self.btn_all = RoundButton(bar, "累计", lambda: self._set_view("all"),
                                   width=62, height=27, radius=13)
        self.btn_all.pack(side="left", padx=(6, 0))
        btns = tk.Frame(bar, bg=BG)
        btns.pack(side="right")
        self.btn_top = RoundButton(btns, "置顶", self._toggle_topmost, width=64)
        self.btn_top.pack(side="left", padx=(6, 0))
        self.btn_proxy = RoundButton(btns, "直采", self._proxy_center, width=62)
        self.btn_proxy.pack(side="left", padx=(6, 0))
        for text, cmd, wd in (("导出数据", self._export_center, 86),
                              ("清零统计", self._reset, 86),
                              ("监控目录…", self._manage_dirs, 96)):
            RoundButton(btns, text, cmd, width=wd).pack(side="left", padx=(6, 0))
        self.btn_style = RoundButton(btns, "", self._toggle_style, width=92)
        self.btn_style.pack(side="left", padx=(6, 0))
        self.btn_mini = RoundButton(btns, "极小", self._enter_mini, width=58)
        self.btn_mini.pack(side="left", padx=(6, 0))

        cols = ("model", "provider", "requests", "inp", "out", "cache_r", "cache_w",
                "rate", "total", "speed", "last")
        self.tree = ttk.Treeview(table_panel, columns=cols, show="headings", height=8)
        widths = (140, 104, 44, 78, 78, 78, 70, 64, 78, 58, 66)
        anchors = ("w", "w", "e", "e", "e", "e", "e", "e", "e", "e", "e")
        for c, w, h, a in zip(cols, widths, COL_HEADERS, anchors):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor=a, stretch=(c in ("model", "total")))
        vsb = ttk.Scrollbar(table_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for corner, kw in (("nw", dict(x=-1, y=-1, anchor="nw")),
                           ("ne", dict(relx=1.0, x=1, y=-1, anchor="ne")),
                           ("sw", dict(rely=1.0, x=-1, y=1, anchor="sw")),
                           ("se", dict(relx=1.0, rely=1.0, x=1, y=1, anchor="se"))):
            CornerPatch(table_panel, corner, 14).place(in_=self.tree, **kw)
        self.tree.tag_configure("dim", foreground=FG)
        self.tree.tag_configure("hot", foreground="#86efac")

        # ---- status bar
        status = tk.Frame(self, bg=BG)
        self._status_frame = status
        status.pack(fill="x", padx=12, pady=(0, 8))
        self.lbl_site = tk.Label(status, text=f"官网: {OFFICIAL_SITE}", bg=BG,
                                 fg=ACCENT2, font=("Microsoft YaHei UI", 8),
                                 cursor="hand2")
        self.lbl_site.pack(side="left")
        self.lbl_site.bind("<Button-1>",
                           lambda e: webbrowser.open(OFFICIAL_SITE))
        self.lbl_status = tk.Label(status, text="SYS // BOOTING…", bg=BG, fg=DIM,
                                   font=("Consolas", 8))
        self.lbl_status.pack(side="left", padx=(12, 0))
        self.lbl_mode = tk.Label(status, text="演示模式" if self.demo else "", bg=BG, fg=WARN,
                                 font=("Microsoft YaHei UI", 8, "bold"))
        self.lbl_mode.pack(side="right")

        # ---- 极小模式面板（默认隐藏）
        self._frames_main = (header, chart_panel, table_panel)
        self.mini_frame = tk.Frame(self, bg=BG)
        chips = tk.Frame(self.mini_frame, bg=BG)
        chips.pack(fill="x", padx=8, pady=(8, 4))
        self.chip_speed = MiniChip(chips, "实时速度", ACCENT, height=52)
        self.chip_today = MiniChip(chips, "今日", ACCENT2, height=52)
        self.chip_total = MiniChip(chips, "累计", ACCENT3, height=52)
        self.chip_live = MiniChip(chips, "活动", WARN, height=52)
        for i, ch in enumerate((self.chip_speed, self.chip_today, self.chip_total,
                                self.chip_live)):
            ch.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            chips.grid_columnconfigure(i, weight=1)
        self.mini_chart = tk.Canvas(self.mini_frame, bg=BG, highlightthickness=0,
                                    height=80)
        mbar = tk.Frame(self.mini_frame, bg=BG)
        mbar.pack(fill="x", padx=8, pady=(0, 8))   # 先于波形打包，空间不足时压缩波形
        RoundButton(mbar, "还原完整界面", self._exit_mini, width=124, height=28,
                    radius=14).pack(side="left")
        tk.Label(mbar, text="极小模式 · 置顶悬浮 · 可拖拽缩放", bg=BG, fg=DIM,
                 font=("Microsoft YaHei UI", 8)).pack(side="right")
        self.mini_chart.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        self._apply_mode()
        self.attributes("-topmost", self.topmost)
        self.btn_top.set_selected(self.topmost)
        if self.ui_mode == "mini":
            self._enter_mini()

    # ------------- 极小模式

    def _enter_mini(self):
        if getattr(self, "_mini", False):
            return
        self._mode_before_mini = self.ui_mode if self.ui_mode != "mini" else "hud"
        self.ui_mode = "mini"
        self._save_config(ui_mode="mini")
        for f in self._frames_main:
            f.pack_forget()
        self._status_frame.pack_forget()   # 极小模式隐藏状态栏，压低高度
        self.mini_frame.pack(fill="both", expand=True)
        self._topmost_before = self.topmost
        self.topmost = True
        self.attributes("-topmost", True)
        self.minsize(300, 130)             # 可拖拽自由缩放的下限
        self.geometry("470x210")           # 初始极小尺寸，可随意拉伸
        self.pack_propagate(False)
        self._mini = True
        self._last_mchart = 0.0

    def _exit_mini(self):
        if not getattr(self, "_mini", False):
            return
        self.mini_frame.pack_forget()
        self._status_frame.pack(fill="x", padx=12, pady=(0, 8))
        header, chart_panel, table_panel = self._frames_main
        header.pack(fill="x", padx=12, pady=(10, 4), before=self._status_frame)
        chart_panel.pack(fill="both", expand=True, padx=12, pady=(8, 4),
                         before=self._status_frame)
        table_panel.pack(fill="both", expand=True, padx=12, pady=(4, 4),
                         before=self._status_frame)
        self.ui_mode = self._mode_before_mini
        self._save_config(ui_mode=self.ui_mode)
        self.topmost = bool(self._load_config().get("always_on_top", False))
        self.attributes("-topmost", self.topmost)
        self.pack_propagate(True)
        self.minsize(920, 600)
        self.geometry("1080x700")
        self._mini = False
        self._chart_sig = None
        self._last_chart = 0.0
        self._apply_mode()

    def _update_mini(self, disp, busy, today_total, cum_total, minute, active,
                     live_active, live_sub):
        self.chip_speed.update_data(f"{disp:.1f}", "tok/s",
                                    ACCENT if busy else DIM)
        self.chip_today.update_data(fmt_tokens(today_total),
                                    f"本分钟 +{fmt_tokens(minute)}",
                                    ACCENT2 if minute > 0 else DIM)
        self.chip_total.update_data(fmt_tokens(cum_total), "全部历史")
        if active:
            self.chip_live.update_data(f"{len(active)} 生成中", live_sub,
                                       ACCENT if live_active else DIM)
        else:
            self.chip_live.update_data("空闲", "等待请求…", DIM)
        for ch in (self.chip_speed, self.chip_today, self.chip_total, self.chip_live):
            try:
                ch.render()
            except Exception:
                pass
        self._draw_mini_chart()

    def _draw_mini_chart(self):
        c = self.mini_chart
        now = now_s()
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 60 or h < 50:
            return
        if now - getattr(self, "_last_mchart", 0) < 0.3:
            return
        self._last_mchart = now
        c.delete("all")
        round_rect(c, 1, 1, w - 2, h - 2, 14, fill=PANEL, outline=BORDER)
        pad_l, pad_r, pad_t, pad_b = 10, 10, 10, 8
        plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
        n = 120  # 迷你波形：近 2 分钟
        buckets = [0.0] * n
        for ts, tok in self.meter.history(120):
            idx = int(now - ts)
            if 0 <= idx < n:
                buckets[idx] += tok
        rates = buckets[:]
        rates.reverse()
        speeds = []
        for i in range(len(rates)):
            lo, hi = max(0, i - 2), min(len(rates), i + 3)
            speeds.append(sum(rates[lo:hi]) / (hi - lo))
        if len(speeds) < 2:
            return
        vmax = max(speeds + [10.0]) * 1.15
        pts = []
        for i, v in enumerate(speeds):
            pts.extend((pad_l + plot_w * i / (len(speeds) - 1),
                        pad_t + plot_h * (1 - min(v / vmax, 1.0))))
        ex, ey = pts[-2], pts[-1]
        poly = [pad_l, pad_t + plot_h] + pts + [ex, pad_t + plot_h]
        c.create_polygon(poly, fill="#0c2531", outline="", smooth=True)
        c.create_line(pts, fill="#22d3ee", width=2, smooth=True)
        c.create_oval(ex - 3, ey - 3, ex + 3, ey + 3, fill="#67e8f9", outline="")

    # ------------- 风格切换（科幻 HUD / 简洁）

    def _toggle_style(self):
        self.ui_mode = "simple" if self.ui_mode == "hud" else "hud"
        self._save_config(ui_mode=self.ui_mode)
        self._apply_mode()

    def _apply_mode(self):
        hud = self.ui_mode == "hud"
        for card in (self.card_speed, self.card_today, self.card_total, self.card_live):
            card.set_style(self.ui_mode)
        self.btn_style.set_text("简洁风格" if hud else "科幻风格")
        self.btn_today.set_selected(self._view == "today")
        self.btn_all.set_selected(self._view == "all")
        if hud:
            self.lbl_registry.configure(text="▍ 按模型统计",
                                        font=("Consolas", 9, "bold"), fg=ACCENT2)
        else:
            self.lbl_registry.configure(text="按模型统计",
                                        font=("Microsoft YaHei UI", 10, "bold"), fg=FG)
        self._chart_sig = None       # 强制图表立即重绘
        self._last_chart = 0.0
        self._update_status()
        self._refresh_table()

    # ------------- periodic refresh

    def _tick(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "error":
                    self.lbl_status.configure(text=f"错误: {payload}", fg=WARN)
                elif kind == "status":
                    self.lbl_status.configure(text=payload)
                elif kind == "filestats":
                    self._file_stats = payload
                    self._update_status()
                elif kind == "proxy":
                    self._proxy_msg = str(payload)
                elif kind in ("started", "finished", "record", "proxy_rec"):
                    pass
        except queue.Empty:
            pass

        self.meter.tick(self.stats)
        spd, minute = self.meter.speed_and_minute()
        self._speed_val = spd
        # 数字缓动：显示值追赶真实值，产生连续跳动的观感
        self._disp_speed += (spd - self._disp_speed) * 0.4
        if abs(spd - self._disp_speed) < 0.05:
            self._disp_speed = spd
        self._pulse_t += 1
        disp = self._disp_speed
        active = self._active_snapshot()
        self._active_now = active   # 图表等处复用，避免重复快照

        cum_total, today_total = self.stats.totals()
        if active:
            newest = max(active, key=lambda x: x[1])
            mk = newest[2]
            model = mk[2] if mk else "模型识别中"
            secs = int(now_s() - newest[1])
            live_sub = f"{model} · {secs}s" if self.ui_mode == "hud" \
                else f"{model} · {secs} 秒"
            live_active = True
        else:
            live_sub = "STANDBY // 等待请求" if self.ui_mode == "hud" else "等待请求…"
            live_active = False

        busy = spd > 0.05 or live_active
        # 总体缓存命中率（按来源口径分别折算分母）——低频重算即可
        now = now_s()
        if self._rate_cache is None or now - self._rate_ts > RATE_EVERY_S:
            num = den = 0
            for (src, _p, _m), a in self.stats.snapshot_cumulative().items():
                num += a["cache_r"]
                den += a["inp"] if src == "zcode" else a["inp"] + a["cache_r"]
            self._rate_cache = num / den * 100 if den else 0.0
            self._rate_ts = now
        cache_rate = self._rate_cache
        if self.ui_mode == "hud":
            speed_sub = "TOKENS/SEC · 实时生成中" if busy else "TOKENS/SEC · 待机"
            today_sub = f"MIN +{fmt_tokens(minute)}"
            total_sub = f"ALL-TIME · 缓存率 {cache_rate:.1f}%"
            live_val = f"● {len(active)} 生成中" if active else "○ 空闲"
        else:
            speed_sub = "实时生成中" if busy else "待机中"
            today_sub = f"本分钟 +{fmt_tokens(minute)}"
            total_sub = f"缓存率 {cache_rate:.1f}% · 全部历史记录"
            live_val = f"{len(active)} 个生成中" if active else "空闲"
        self.card_speed.update_data(f"{disp:.1f}", speed_sub,
                                    ACCENT if busy else DIM, busy, unit="tok/s")
        self.card_today.update_data(fmt_tokens(today_total), today_sub,
                                    ACCENT2 if minute > 0 else DIM, minute > 0,
                                    unit="tokens")
        self.card_total.update_data(fmt_tokens(cum_total), total_sub, DIM, False,
                                    unit="tokens")
        self.card_live.update_data(live_val, live_sub,
                                   ACCENT if live_active else DIM, live_active)
        for card in (self.card_speed, self.card_today, self.card_total, self.card_live):
            try:
                card.render(self._pulse_t)
            except Exception:
                pass  # 单卡渲染异常不拖垮整个刷新循环

        # 任务栏标题实时速度：最多每秒更新一次（降低标题栏重绘）
        if now - getattr(self, "_last_title_ts", 0.0) >= 1.0:
            self._last_title_ts = now
            t = f"小天tokens监控 · {disp:.1f} tok/s"
            if t != self._last_title:
                self._last_title = t
                self.title(t)

        if getattr(self, "_mini", False):
            self.chip_speed.update_data(f"{disp:.1f}", "tok/s",
                                        ACCENT if busy else DIM)
            self.chip_today.update_data(fmt_tokens(today_total),
                                        f"+{fmt_tokens(minute)}/分",
                                        ACCENT2 if minute > 0 else DIM)
            self.chip_total.update_data(fmt_tokens(cum_total),
                                        f"缓存率 {cache_rate:.1f}%")
            if active:
                newest = max(active, key=lambda x: x[1])
                self.chip_live.update_data(f"{len(active)} 生成中",
                                           f"{int(now_s() - newest[1])}s", ACCENT)
            else:
                self.chip_live.update_data("空闲", "等待请求", DIM)
            self.after(TICK_MS, self._tick)
            return
        if now - self._last_table >= TABLE_EVERY_S:
            self._refresh_table()
            self._last_table = now
            self._update_status()
        self._draw_chart()
        self.after(TICK_MS, self._tick)

    def _active_snapshot(self):
        """汇总所有后端（日志扫描 + 网络直采）正在生成中的请求。"""
        out = []
        for b in (self.watcher, self.proxy):
            if b is None:
                continue
            try:
                out.extend(b.active_snapshot())
            except Exception:
                pass
        return out

    def _update_status(self):
        fs = self._file_stats
        p = self.proxy.status() if self.proxy is not None else None
        if p and p["running"]:
            proxy_txt = f"● 直采 {p['addr']}"
        elif p and p["error"]:
            proxy_txt = f"✕ {p['error']}"
        elif not self.ca.supported:
            proxy_txt = "× 直采 不可用(缺 cryptography)"
        else:
            proxy_txt = "○ 直采 未开启"
        if self.ui_mode == "hud":
            self.lbl_status.configure(text=(
                f"SYS//OK · {proxy_txt} · "
                f"ZCODE {fs.get('zcode', 0)}f · LOG {fs.get('zlog', 0)}f · "
                f"CLAUDE {fs.get('claude', 0)}f · WB {fs.get('workbuddy', 0)}f · "
                f"CX {fs.get('codex', 0)}f · OC {fs.get('opencode', 0)} · "
                f"{'DEMO' if self.demo else STATE_FILE}"),
                font=("Consolas", 8), fg=DIM)
        else:
            self.lbl_status.configure(text=(
                f"{proxy_txt} · ZCode {fs.get('zcode', 0)} 文件 · "
                f"日志 {fs.get('zlog', 0)} · Claude Code {fs.get('claude', 0)} · "
                f"WorkBuddy {fs.get('workbuddy', 0)} · "
                f"Codex {fs.get('codex', 0)} · "
                f"额外 {fs.get('extra', 0)} · "
                f"{'演示模式(不落盘)' if self.demo else '数据: ' + STATE_FILE}"),
                font=("Microsoft YaHei UI", 8), fg=DIM)
        if self._proxy_msg:
            self.lbl_status.configure(text=f"{proxy_txt} · {self._proxy_msg}")
            self._proxy_msg = ""
        try:
            self.btn_proxy.set_selected(bool(p and p["running"]))
        except Exception:
            pass

    # ------------- chart

    def _lerp_color(self, c1, c2, t):
        t = max(0.0, min(1.0, t))
        a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
        b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
        return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))

    def _draw_chart(self):
        c = self.chart
        now = now_s()
        w = c.winfo_width() or 600
        h = c.winfo_height() or 150
        if w < 60 or h < 40:
            return
        # 无新数据时降频重绘，保持流畅不闪烁
        sig = (len(self.meter.samples), len(self._active_now))
        if now - self._last_chart < CHART_MIN_DT_S or \
           (now - self._last_chart < CHART_IDLE_S and sig == getattr(self, "_chart_sig", None)):
            return
        self._chart_sig = sig
        self._last_chart = now
        c.delete("all")
        round_rect(c, 1, 1, w - 2, h - 2, 18, fill=PANEL, outline=BORDER)
        pad_l, pad_r, pad_t, pad_b = 46, 12, 12, 18
        plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b

        # 1s 分桶 + 5s 滑动平均 → 平滑流畅的波形（消除锯齿毛刺）
        n_buckets = int(CHART_WINDOW_S)
        buckets = [0.0] * n_buckets
        for ts, tok in self.meter.history(CHART_WINDOW_S):
            idx = int(now - ts)
            if 0 <= idx < n_buckets:
                buckets[idx] += tok
        rates = buckets[:]
        rates.reverse()
        speeds = []
        for i in range(len(rates)):
            lo, hi = max(0, i - 2), min(len(rates), i + 3)
            speeds.append(sum(rates[lo:hi]) / (hi - lo))
        cur = speeds[-1] if speeds else 0.0

        # 纵轴量程平滑追踪
        target = max(speeds + [10.0]) * 1.2
        self._vmax = target if self._vmax is None else self._vmax + (target - self._vmax) * 0.25
        vmax = self._vmax

        def x_of(i):
            return pad_l + plot_w * i / max(len(speeds) - 1, 1)

        def y_of(v):
            return pad_t + plot_h * (1 - min(v / vmax, 1.0))

        # 网格与刻度
        for frac in (0.25, 0.5, 0.75, 1.0):
            yy = pad_t + plot_h * (1 - frac)
            c.create_line(pad_l, yy, pad_l + plot_w, yy, fill=BORDER)
            c.create_text(pad_l - 6, yy, text=f"{vmax * frac:.0f}", fill=DIM,
                          anchor="e", font=("Consolas", 8))
        for sec in (0, 60, 120, 180, 240, 300):
            xx = pad_l + plot_w * (1 - sec / CHART_WINDOW_S)
            c.create_text(xx, h - pad_b + 8, text=f"-{sec // 60}m" if sec else "现在",
                          fill=DIM, font=("Microsoft YaHei UI", 8))
        c.create_text(pad_l + 4, pad_t - 6, anchor="nw", fill=DIM,
                      text="实时生成速度 · 近 5 分钟", font=("Microsoft YaHei UI", 8))

        if len(speeds) < 2:
            return
        base_y = pad_t + plot_h
        simple = self.ui_mode == "simple"
        pts = []
        for i, v in enumerate(speeds):
            pts.extend((x_of(i), y_of(v)))
        ex, ey = x_of(len(speeds) - 1), y_of(cur)

        if simple:
            # 简洁：柔和面积填充 + 平滑单线 + 端点圆点
            poly = [pad_l, base_y] + pts + [ex, base_y]
            c.create_polygon(poly, fill="#0e1b26", outline="", smooth=True)
            c.create_line(pts, fill=ACCENT2, width=2, smooth=True)
            c.create_oval(ex - 3, ey - 3, ex + 3, ey + 3, fill=ACCENT2, outline="")
        else:
            # 科幻：平滑面积填充 + 发光双线（粗暗线垫底 + 细亮线），无竖条纹
            poly = [pad_l, base_y] + pts + [ex, base_y]
            c.create_polygon(poly, fill="#0c2531", outline="", smooth=True)
            c.create_line(pts, fill="#155e75", width=4, smooth=True,
                          joinstyle="round")
            c.create_line(pts, fill="#7dd3fc", width=2, smooth=True,
                          joinstyle="round")
            # 末端脉冲光点 + 当前值（贴近右缘时文字自动换到点的左侧）
            pulse = 3.0 + (1.6 if cur > 0.5 and (self._pulse_t // 3) % 2 else 0)
            r = pulse + 3
            c.create_oval(ex - r, ey - r, ex + r, ey + r, outline="#22d3ee", width=1)
            c.create_oval(ex - pulse, ey - pulse, ex + pulse, ey + pulse,
                          fill="#67e8f9", outline="")
            if ex > pad_l + plot_w - 52:
                c.create_text(ex - 12, ey, text=f"{cur:.0f}", fill="#a5f3fc",
                              anchor="e", font=("Consolas", 10, "bold"))
            else:
                c.create_text(ex + 12, ey, text=f"{cur:.0f}", fill="#a5f3fc",
                              anchor="w", font=("Consolas", 10, "bold"))
        # 近 60 秒峰值虚线（两种风格共用），文字放在虚线左端避开右侧波形
        recent = speeds[max(0, len(speeds) - 120):]
        peak = max(recent) if recent else 0
        if peak > 5:
            py = y_of(peak)
            c.create_line(pad_l, py, pad_l + plot_w, py, fill="#365a71", dash=(4, 4))
            c.create_text(pad_l + 6, py + 10, text=f"峰值 {peak:.0f}",
                          fill="#5b8ba3", anchor="w", font=("Microsoft YaHei UI", 8))

        if not simple:
            # ---- 科幻装饰：四角角标 + 周期扫掠线 + LIVE 指示
            L = 14
            for x0, y0, dx, dy in ((pad_l, pad_t, 1, 1), (pad_l + plot_w, pad_t, -1, 1),
                                   (pad_l, base_y, 1, -1), (pad_l + plot_w, base_y, -1, -1)):
                c.create_line(x0, y0, x0 + dx * L, y0, fill="#31465f", width=1)
                c.create_line(x0, y0, x0, y0 + dy * L, fill="#31465f", width=1)
            # 扫掠线只在生成中时流动，空闲时静止（省去无谓重绘细节）
            moving = bool(self._active_now) or cur > 0.5
            scan_t = (now % 6) / 6 if moving else 0.62
            sx = pad_l + plot_w * scan_t
            c.create_line(sx, pad_t, sx, base_y, fill=ACCENT2, stipple="gray50")
            if sx - 7 > pad_l:
                c.create_line(sx - 7, pad_t, sx - 7, base_y, fill=ACCENT2,
                              stipple="gray25")
            # LIVE 指示放在左下角，避开右侧正在跳动的波形
            live_now = bool(self._active_now)
            lx, ly = pad_l + 6, base_y - 8
            if live_now:
                col = ACCENT if (self._pulse_t // 5) % 2 else "#14532d"
                c.create_text(lx, ly, anchor="sw", text="● LIVE",
                              fill=col, font=("Consolas", 8, "bold"))
            else:
                c.create_text(lx, ly, anchor="sw", text="○ IDLE",
                              fill="#566270", font=("Consolas", 8))
        elif cur > 1:
            c.create_text(pad_l + 6, base_y - 8, anchor="sw",
                          text=f"{cur:.0f} tok/s", fill=DIM,
                          font=("Microsoft YaHei UI", 8))

    # ------------- table

    def _rows(self):
        data = self.stats.snapshot_today() if self._view == "today" \
            else self.stats.snapshot_cumulative()
        # 面板叫「按模型统计」，所以按 (厂商, 模型) 合并。
        # 同一个模型名经常同时来自 ZCode / Claude Code / WorkBuddy
        # （例如 deepseek-v4-pro），按来源分行会看起来像重复且列宽放不下来源标记。
        merged = {}
        for (source, provider, model), a in data.items():
            vendor = guess_provider(model) or provider or \
                SOURCE_NAMES.get(source, source) or "-"
            m = merged.get((vendor, model))
            if m is None:
                m = merged[(vendor, model)] = dict(a)
                m.setdefault("est_req", 0)
            else:
                for f in ("requests", "inp", "out", "cache_r", "cache_w", "gen_s"):
                    m[f] += a[f]
                m["est_req"] = m.get("est_req", 0) + a.get("est_req", 0)
                m["last_ts"] = max(m["last_ts"], a["last_ts"])
        rows = []
        for (vendor, model), a in merged.items():
            total = a["inp"] + a["out"]
            speed = a["out"] / a["gen_s"] if a["gen_s"] > 0 else 0.0
            rate = cache_rate_pct(a["inp"], a["cache_r"], "")
            # 有估算成分的输入加 ≈，避免把估算当成实测
            inp_txt = ("≈" if a.get("est_req") else "") + fmt_tokens(a["inp"])
            cols = (model, vendor, a["requests"],
                    inp_txt, fmt_tokens(a["out"]),
                    fmt_tokens(a["cache_r"]), fmt_tokens(a["cache_w"]),
                    f"{rate:.1f}%", fmt_tokens(total), f"{speed:.1f}",
                    fmt_ago(a["last_ts"]))
            rows.append((total, a["last_ts"], cols))
        rows.sort(key=lambda r: -r[0])
        return [(cols, now_s() - ts < 15) for _total, ts, cols in rows]

    def _set_view(self, v):
        self._view = v
        self.btn_today.set_selected(v == "today")
        self.btn_all.set_selected(v == "all")
        self._rows_sig = None       # 视图切换强制重绘
        self._refresh_table()

    def _refresh_table(self):
        rows = self._rows()
        sig = tuple(c for c, _ in rows)
        if sig == self._rows_sig:
            return                  # 内容无变化，跳过重建（省 CPU 且不闪）
        self._rows_sig = sig
        self.tree.delete(*self.tree.get_children())
        for cols, hot in rows:
            self.tree.insert("", "end", values=cols,
                             tags=("hot",) if hot else ("dim",))

    # ------------- actions

    def _toggle_topmost(self):
        self.topmost = not self.topmost
        self.attributes("-topmost", self.topmost)
        self._save_config(always_on_top=self.topmost)   # 记住置顶状态
        self.btn_top.set_selected(self.topmost)

    def _reset(self):
        if messagebox.askyesno(APP_NAME, "确定清零所有统计数据？\n（监控文件偏移会保留，历史记录不会重新计入）"):
            self.stats.reset()
            self.meter.clear()
            self.stats.save(self.watcher.offsets)
            self._rate_cache = None     # 缓存率立即刷新
            self._rows_sig = None
            self._refresh_table()

    # ------------- 导出中心

    def _export_center(self):
        win = tk.Toplevel(self)
        win.title("导出数据")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self)
        tk.Label(win, text="选择要导出的数据", bg=BG, fg=FG,
                 font=("Microsoft YaHei UI", 11, "bold")).pack(pady=(18, 6))
        tk.Label(win, text="记录字段：时间、模型、输入/输出/缓存 tokens、耗时、速度",
                 bg=BG, fg=DIM, font=("Microsoft YaHei UI", 9)).pack(pady=(0, 14))
        f9 = tkfont.Font(font=("Microsoft YaHei UI", 9))
        opts = (("① 每日使用汇总（按天 × 模型）", self._export_daily),
                ("② 明细记录（每次请求，含时间）", self._export_detail),
                ("③ 模型统计（当前表格视图）", self._export_csv))
        site_t = "④ 官网 · 前往 aicgxt.com/chat"
        bw = max(f9.measure(t) for t, _ in opts + ((site_t, None),)) + 60

        def add(text, cmd):
            RoundButton(win, text, cmd, width=bw, height=34, radius=17).pack(pady=4)

        for t, cmd in opts:
            add(t, lambda t=t, c=cmd: (win.destroy(), c()))
        RoundButton(win, site_t, lambda: webbrowser.open(OFFICIAL_CHAT_URL),
                    width=bw, height=34, radius=17).pack(pady=4)
        RoundButton(win, "取消", win.destroy, width=bw, height=30,
                    radius=15).pack(pady=(8, 18))
        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - win.winfo_width()) // 2
        y = self.winfo_y() + 120
        win.geometry(f"+{x}+{y}")

    def _load_log(self):
        """读取明细日志并按 key 去重，按时间排序。"""
        recs = {}
        try:
            with open(LOG_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    k = d.get("key") or (d.get("ts"), d.get("model"))
                    if k not in recs:
                        recs[k] = d
        except OSError:
            pass
        return sorted(recs.values(), key=lambda d: d.get("ts", 0))

    def _export_daily(self):
        agg = {}
        for d in self._load_log():
            date = time.strftime("%Y-%m-%d", time.localtime(d.get("ts", 0)))
            k = (date, d.get("model", "?"), d.get("source", ""))
            a = agg.setdefault(k, [0, 0, 0, 0, 0, 0.0, 0])
            a[0] += 1
            a[1] += d.get("inp", 0)
            a[2] += d.get("out", 0)
            a[3] += d.get("cache_r", 0)
            a[4] += d.get("cache_w", 0)
            a[5] += d.get("dur", 0.0)
            a[6] += d.get("inp", 0) if d.get("source") == "zcode" \
                else d.get("inp", 0) + d.get("cache_r", 0)
        if not agg:
            messagebox.showinfo(APP_NAME, "暂无记录可导出")
            return
        fn = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=f"每日汇总-{time.strftime('%Y%m%d')}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not fn:
            return
        with open(fn, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(("日期", "模型", "来源", "请求数", "输入tokens", "输出tokens",
                        "缓存读tokens", "缓存写tokens", "总计tokens",
                        "缓存命中率(%)", "生成耗时(秒)", "平均速度(tok/s)"))
            for (date, model, source), a in sorted(agg.items()):
                total = a[1] + a[2]
                speed = a[2] / a[5] if a[5] > 0 else 0.0
                rate = a[3] / a[6] * 100 if a[6] > 0 else 0.0
                w.writerow((date, model, SOURCE_NAMES.get(source, source), a[0],
                            a[1], a[2], a[3], a[4], total, f"{rate:.1f}",
                            f"{a[5]:.1f}", f"{speed:.1f}"))
        messagebox.showinfo(APP_NAME, f"已导出 {len(agg)} 行每日汇总\n{fn}")

    def _export_detail(self):
        recs = self._load_log()
        if not recs:
            messagebox.showinfo(APP_NAME, "暂无记录可导出")
            return
        fn = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"明细记录-{time.strftime('%Y%m%d-%H%M')}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not fn:
            return
        with open(fn, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(("时间", "日期", "模型", "来源", "输入tokens", "输出tokens",
                        "缓存读tokens", "缓存写tokens", "总计tokens",
                        "缓存命中率(%)", "耗时(秒)", "速度(tok/s)"))
            for d in recs:
                dur = d.get("dur", 0.0)
                speed = d.get("out", 0) / dur if dur > 0 else ""
                total = d.get("inp", 0) + d.get("out", 0)
                rate = cache_rate_pct(d.get("inp", 0), d.get("cache_r", 0),
                                      d.get("source", ""))
                w.writerow((d.get("time", ""),
                            time.strftime("%Y-%m-%d", time.localtime(d.get("ts", 0))),
                            d.get("model", ""), SOURCE_NAMES.get(d.get("source", ""),
                                                                 d.get("source", "")),
                            d.get("inp", 0), d.get("out", 0),
                            d.get("cache_r", 0), d.get("cache_w", 0), total,
                            f"{rate:.1f}",
                            f"{dur:.1f}" if dur else "", speed))
        messagebox.showinfo(APP_NAME, f"已导出 {len(recs)} 条明细记录\n{fn}")

    def _export_csv(self):
        fn = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=f"tokens-{time.strftime('%Y%m%d-%H%M')}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not fn:
            return
        with open(fn, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(COL_HEADERS)
            w.writerows(cols for cols, _hot in self._rows())
        self.lbl_status.configure(text=f"已导出: {fn}")

    def _manage_dirs(self):
        win = tk.Toplevel(self)
        win.title("额外监控目录")
        win.configure(bg=BG)
        win.geometry("520x300")
        tk.Label(win, text="除 ZCode / Claude Code 默认目录外，可监控其他目录下的 .jsonl 记录文件：",
                 bg=BG, fg=FG, wraplength=490, justify="left").pack(anchor="w", padx=12, pady=8)
        lb = tk.Listbox(win, bg=PANEL, fg=FG, selectbackground="#31415a",
                        highlightthickness=1, highlightbackground=BORDER)
        lb.pack(fill="both", expand=True, padx=12)
        for d in self.extra_dirs:
            lb.insert("end", d)
        def add():
            d = filedialog.askdirectory()
            if d:
                lb.insert("end", os.path.normpath(d))
        def remove():
            sel = lb.curselection()
            if sel:
                lb.delete(sel[0])
        def save_close():
            self.extra_dirs = list(lb.get(0, "end"))
            self.watcher.extra_dirs = self.extra_dirs
            self._save_config(extra_dirs=self.extra_dirs)
            win.destroy()
        btns = tk.Frame(win, bg=BG)
        btns.pack(fill="x", padx=12, pady=8)
        ttk.Button(btns, text="添加目录…", command=add).pack(side="left")
        ttk.Button(btns, text="移除所选", command=remove).pack(side="left", padx=6)
        ttk.Button(btns, text="保存并关闭", command=save_close).pack(side="right")

    # ------------- 网络直采

    def proxy_running(self):
        return bool(self.proxy is not None and self.proxy.running)

    def _make_proxy(self):
        return MitmProxy(self.watcher._emit, self.q, self.ca, meter=self.meter,
                         port=self._proxy_port,
                         extra_hosts=list(self.proxy_extra_hosts),
                         mitm_all=self.proxy_mitm_all,
                         auto_probe=self.proxy_auto_probe)

    def start_proxy(self):
        """只启动本地代理，不改动系统设置。返回 (ok, msg)。"""
        if self.demo:
            return False, "演示模式不支持网络直采"
        if not self.ca.supported:
            return False, self.ca.error or "缺少 cryptography 库"
        if self.proxy_running():
            return True, f"已在监听 {self.proxy.addr}"
        if not self.ca.ensure():
            return False, self.ca.error or "根证书初始化失败"
        p = self._make_proxy()
        self.proxy = p
        p.start()
        for _ in range(60):          # 等监听就绪（最多 3 秒）
            if p.running or p.error:
                break
            time.sleep(0.05)
        if p.error:
            msg = p.error
            self.proxy = None
            return False, msg
        return True, f"已监听 {p.addr}"

    def stop_proxy(self):
        p = self.proxy
        if p is None:
            return
        p.stop()
        try:
            p.join(timeout=2.0)
        except RuntimeError:
            pass
        self.proxy = None

    def _ensure_backup(self):
        if self._applied_sys is None and self._applied_env is None:
            self._applied_sys = SystemProxy.read()
            self._applied_env = SystemProxy.read_env()
            save_proxy_backup({"active": True, "sys": self._applied_sys,
                               "env": self._applied_env,
                               "port": self._proxy_port})
            write_restore_bat()

    def apply_system_proxy(self):
        if winreg is None:
            return False, "仅 Windows 支持系统代理接管"
        self._ensure_backup()
        SystemProxy.apply(f"{PROXY_HOST}:{self._proxy_port}")
        return True, f"系统代理已指向 {PROXY_HOST}:{self._proxy_port}"

    def apply_env_proxy(self):
        if winreg is None:
            return False, "仅 Windows 支持环境变量注入"
        self._ensure_backup()
        prefix = f"http://{PROXY_HOST}:{self._proxy_port}"
        SystemProxy.apply_env({
            "HTTP_PROXY": prefix, "HTTPS_PROXY": prefix, "ALL_PROXY": prefix,
            "http_proxy": prefix, "https_proxy": prefix,
            "NODE_USE_ENV_PROXY": "1",
            "NODE_EXTRA_CA_CERTS": self.ca.cert_path,
        })
        return True, "代理环境变量已写入（对之后新启动的程序生效）"

    def revert_system_proxy(self):
        if self._applied_env:
            SystemProxy.restore_env(self._applied_env)
            self._applied_env = None
        if self._applied_sys:
            SystemProxy.restore(self._applied_sys)
            self._applied_sys = None
        clear_proxy_backup()

    def enable_direct_capture(self, quiet=False):
        """一键开启：启动代理 + 装证书 + 接管系统代理 + 注入环境变量。"""
        self._proxy_port = self._read_port()
        ok, msg = self.start_proxy()
        if not ok:
            if not quiet:
                messagebox.showerror(APP_NAME, msg, parent=self)
            return False
        try:
            self.ca.install()
        except Exception:
            pass
        self._ensure_backup()
        try:
            SystemProxy.apply(f"{PROXY_HOST}:{self._proxy_port}")
            self.apply_env_proxy()
        except Exception as e:
            if not quiet:
                messagebox.showwarning(APP_NAME, f"代理已启动，但系统设置写入失败：{e}")
        # 根证书：命令行程序靠环境变量已可解密；浏览器 / Electron 需要信任区
        ca_note = ""
        try:
            ok_ca, msg_ca = self.ca.install()
            if not (ok_ca or self.ca.is_installed()):
                ca_note = f"（根证书未信任：{msg_ca}）"
        except Exception as e:
            ca_note = f"（根证书安装异常：{e}）"
        # 直采已覆盖所有程序，本地日志扫描就没有必要了
        self.watcher.scan_logs = False
        self._save_config(scan_logs=False, proxy_port=self._proxy_port,
                          proxy_extra_hosts=self.proxy_extra_hosts,
                          proxy_mitm_all=self.proxy_mitm_all)
        self._set_msg(f"网络直采已开启 · {PROXY_HOST}:{self._proxy_port} · "
                      f"新启动的程序也已生效 {ca_note}")
        return True

    def disable_direct_capture(self, quiet=False):
        self.stop_proxy()
        try:
            self.revert_system_proxy()
        except Exception:
            pass
        self._set_msg("网络直采已停止，系统代理与环境变量已还原")
        if not quiet:
            try:
                self._proxy_refresh()
            except Exception:
                pass

    def _read_port(self):
        try:
            v = int(str(self._p_port.get()).strip()) if hasattr(self, "_p_port") \
                else self._proxy_port
            if 1024 <= v <= 65535:
                return v
        except (ValueError, tk.TclError):
            pass
        return self._proxy_port if 1024 <= self._proxy_port <= 65535 \
            else PROXY_PORT_DEFAULT

    def _set_msg(self, text):
        try:
            self.lbl_status.configure(text=text, fg=ACCENT2)
        except tk.TclError:
            pass

    def _on_close(self):
        try:
            if self.proxy is not None:
                self.stop_proxy()
            if not getattr(self, "keep_proxy_on_close", False) and \
                    (self._applied_sys is not None or self._applied_env is not None):
                self.revert_system_proxy()
        except Exception:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _proxy_center(self):
        if self.demo:
            messagebox.showinfo(APP_NAME, "演示模式下不启用网络直采。")
            return
        win = getattr(self, "_pwin", None)
        try:
            alive = win is not None and win.winfo_exists()
        except tk.TclError:
            alive = False
        if alive:
            win.lift()
            win.focus_force()
            return
        if self.ca.supported:
            self.ca.ensure()
        win = tk.Toplevel(self)
        self._pwin = win
        self._p_gen = getattr(self, "_p_gen", 0) + 1
        self._p_sig = None
        win.title("网络直采 · 直接统计本机所有 AI 调用的 tokens")
        win.configure(bg=BG)
        win.geometry("830x700")
        win.transient(self)

        tk.Label(win, text="不依赖任何软件自己的日志：本机所有程序发往 AI 服务的请求都会经过本地代理，"
                           "从 API 返回值里直接读出真实 token 用量。",
                 bg=BG, fg=FG, wraplength=750, justify="left",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(
                     anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="内置识别 Claude / GPT / Gemini / DeepSeek / GLM / Kimi / Qwen / 豆包 / "
                           "Grok / 文心 / 混元 / 阶跃 等，以及各类 OpenAI 兼容中转站。",
                 bg=BG, fg=DIM, wraplength=750, justify="left",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=14, pady=(0, 8))

        box = tk.Frame(win, bg=PANEL, highlightthickness=1,
                       highlightbackground=BORDER)
        box.pack(fill="x", padx=14)
        self._p_lbls = {}
        for key, label in (("svc", "代理服务"), ("ca", "根证书"),
                           ("sys", "系统代理"), ("env", "环境变量"),
                           ("hit", "抓取统计")):
            row = tk.Frame(box, bg=PANEL)
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=label, bg=PANEL, fg=DIM, width=9, anchor="w",
                     font=("Microsoft YaHei UI", 9)).pack(side="left")
            v = tk.Label(row, text="-", bg=PANEL, fg=FG, anchor="w",
                         font=("Microsoft YaHei UI", 9, "bold"))
            v.pack(side="left", fill="x", expand=True)
            self._p_lbls[key] = v

        prow = tk.Frame(win, bg=BG)
        prow.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(prow, text="监听端口", bg=BG, fg=DIM,
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        self._p_port = tk.StringVar(value=str(self._proxy_port))
        tk.Entry(prow, textvariable=self._p_port, width=7, bg=PANEL, fg=FG,
                 relief="flat", insertbackground=FG,
                 font=("Consolas", 10)).pack(side="left", padx=6)
        self._p_mitm = tk.BooleanVar(value=self.proxy_mitm_all)
        tk.Checkbutton(prow, text="解密所有 HTTPS", variable=self._p_mitm,
                       command=self._toggle_mitm_all, bg=BG, fg=DIM,
                       selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG, highlightthickness=0,
                       font=("Microsoft YaHei UI", 9)).pack(side="left", padx=8)
        self._p_probe = tk.BooleanVar(value=self.proxy_auto_probe)
        tk.Checkbutton(prow, text="自动识别未知中转", variable=self._p_probe,
                       command=self._toggle_auto_probe, bg=BG, fg=ACCENT2,
                       selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG, highlightthickness=0,
                       font=("Microsoft YaHei UI", 9)).pack(side="left")

        hrow = tk.Frame(win, bg=BG)
        hrow.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(hrow, text="额外域名（逗号分隔，回车生效）", bg=BG, fg=DIM,
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        self._p_hosts = tk.StringVar(value=",".join(self.proxy_extra_hosts))
        ent = tk.Entry(hrow, textvariable=self._p_hosts, bg=PANEL, fg=FG,
                       relief="flat", insertbackground=FG,
                       font=("Consolas", 9))
        ent.pack(side="left", fill="x", expand=True, padx=6)
        ent.bind("<Return>", lambda _e: self._apply_extra_hosts())

        bar = tk.Frame(win, bg=BG)
        bar.pack(fill="x", padx=14, pady=(0, 4))
        for text, cmd, wd in (("一键开启直采", self._act_enable, 116),
                              ("停止并还原", self._act_disable, 100),
                              ("安装根证书", self._act_ca_install, 100),
                              ("卸载根证书", self._act_ca_uninstall, 100)):
            RoundButton(bar, text, cmd, width=wd, height=30).pack(
                side="left", padx=(0, 8))
        bar2 = tk.Frame(win, bg=BG)
        bar2.pack(fill="x", padx=14, pady=(0, 6))
        for text, cmd, wd in (("只设系统代理", self._act_sys_on, 100),
                              ("还原系统代理", self._act_sys_off, 100),
                              ("注入环境变量", self._act_env_on, 100),
                              ("清除环境变量", self._act_env_off, 100)):
            RoundButton(bar2, text, cmd, width=wd, height=28).pack(
                side="left", padx=(0, 8))

        opt = tk.Frame(win, bg=BG)
        opt.pack(fill="x", padx=14)
        self._p_scanlogs = tk.BooleanVar(value=self.watcher.scan_logs)
        tk.Checkbutton(opt, text="同时扫描本地日志（ZCode / Claude Code / WorkBuddy / Codex / OpenCode / 额外目录）",
                       variable=self._p_scanlogs, command=self._toggle_scan_logs,
                       bg=BG, fg=DIM, selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG, highlightthickness=0,
                       font=("Microsoft YaHei UI", 9)).pack(side="left")
        self._p_auto = tk.BooleanVar(value=Autostart.enabled())
        tk.Checkbutton(opt, text="开机自启", variable=self._p_auto,
                       command=self._toggle_autostart, bg=BG, fg=DIM,
                       selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG, highlightthickness=0,
                       font=("Microsoft YaHei UI", 9)).pack(side="right")

        tk.Label(win, text="▍ 最近抓到的调用", bg=BG, fg=ACCENT2,
                 font=("Consolas", 9, "bold")).pack(anchor="w", padx=14,
                                                    pady=(10, 2))
        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        cols = ("time", "model", "vendor", "inp", "out", "dur", "note", "host")
        heads = ("时间", "模型", "厂商", "输入", "输出", "耗时", "说明", "服务")
        widths = (62, 186, 106, 60, 60, 50, 62, 150)
        self._p_tree = ttk.Treeview(frame, columns=cols, show="headings",
                                    height=8)
        for c, h, wd in zip(cols, heads, widths):
            self._p_tree.heading(c, text=h)
            self._p_tree.column(c, width=wd, anchor="w",
                                stretch=(c in ("model", "note", "host")))
        vsb = ttk.Scrollbar(frame, orient="vertical",
                            command=self._p_tree.yview)
        self._p_tree.configure(yscrollcommand=vsb.set)
        self._p_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._p_tree.tag_configure("est", foreground=WARN)
        self._p_tree.tag_configure("ok", foreground=FG)

        tk.Label(win, text=f"根证书：{CA_CERT_FILE}    一键还原脚本：{RESTORE_BAT}\n"
                           "· 首次安装根证书时 Windows 会弹出安全警告，请点『是』。\n"
                           "· 命令行程序（Claude Code / Codex 等）靠代理环境变量生效，"
                           "需要重启该程序；浏览器 / Electron 程序装完证书即可，"
                           "必要时重启。\n"
                           "· 勾选「解密所有 HTTPS」后，没信任根证书的程序可能访问不了网站，"
                           "建议先用默认的按域名解密。\n"
                           "· 程序退出时会自动还原系统代理与环境变量；"
                           "若异常退出导致上不了网，双击上面的一键还原脚本即可。",
                 bg=BG, fg=DIM, justify="left", wraplength=750,
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=14,
                                                      pady=(0, 10))
        self._proxy_refresh()

    # ---- 面板动作

    def _act_enable(self):
        if self.enable_direct_capture():
            self._proxy_refresh()
            self._update_status()

    def _act_disable(self):
        self.disable_direct_capture()
        self._update_status()

    def _act_ca_install(self):
        if not self.ca.ensure():
            messagebox.showerror(APP_NAME, self.ca.error or "根证书不可用")
            return
        ok, msg = self.ca.install()
        if ok:
            messagebox.showinfo(APP_NAME,
                                "根证书已加入当前用户的「受信任的根证书颁发机构」。\n"
                                "浏览器 / Electron 类程序立即生效。")
        else:
            messagebox.showerror(APP_NAME, f"安装失败：{msg}")
        self._proxy_refresh()

    def _act_ca_uninstall(self):
        if not self.ca.available:
            self.ca.ensure()
        ok, msg = self.ca.uninstall()
        if ok:
            messagebox.showinfo(APP_NAME, "根证书已从系统信任区移除。")
        else:
            messagebox.showerror(APP_NAME, f"卸载失败：{msg}")
        self._proxy_refresh()

    def _act_sys_on(self):
        ok, msg = self.apply_system_proxy()
        self._set_msg(msg)
        self._proxy_refresh()

    def _act_sys_off(self):
        try:
            if self._applied_sys:
                SystemProxy.restore(self._applied_sys)
                self._applied_sys = None
            else:
                SystemProxy.restore({"ProxyEnable": 0, "ProxyServer": "",
                                     "ProxyOverride": ""})
            clear_proxy_backup()
            self._set_msg("系统代理已还原")
        except Exception as e:
            self._set_msg(f"还原失败: {e}")
        self._proxy_refresh()

    def _act_env_on(self):
        ok, msg = self.apply_env_proxy()
        self._set_msg(msg)
        self._proxy_refresh()

    def _act_env_off(self):
        try:
            SystemProxy.restore_env(self._applied_env or {
                k: None for k in _ENV_NAMES})
            self._applied_env = None
            self._set_msg("代理环境变量已清除")
        except Exception as e:
            self._set_msg(f"清除失败: {e}")
        self._proxy_refresh()

    def _toggle_mitm_all(self):
        try:
            self.proxy_mitm_all = bool(self._p_mitm.get())
        except tk.TclError:
            return
        if self.proxy is not None:
            self.proxy.mitm_all = self.proxy_mitm_all
        self._save_config(proxy_mitm_all=self.proxy_mitm_all)

    def _toggle_autostart(self):
        """开机自启：写 HKCU\\...\\Run（不需要管理员权限）。"""
        try:
            want = bool(self._p_auto.get())
        except tk.TclError:
            return
        ok, msg = Autostart.set_on(want)
        if not ok:
            try:
                self._p_auto.set(Autostart.enabled())
            except tk.TclError:
                pass
        self._set_msg(msg)

    def _toggle_auto_probe(self):
        """未知中转自动识别：对名字像 AI 服务的陌生域名先解密看一眼路径。"""
        try:
            self.proxy_auto_probe = bool(self._p_probe.get())
        except tk.TclError:
            return
        if self.proxy is not None:
            self.proxy.auto_probe = self.proxy_auto_probe
            if not self.proxy_auto_probe:
                self.proxy.probe_cache.clear()
        self._save_config(proxy_auto_probe=self.proxy_auto_probe)

    def _apply_extra_hosts(self):
        raw = self._p_hosts.get().replace("，", ",").replace("；", ",")
        hosts = [h.strip() for h in raw.replace(";", ",").split(",") if h.strip()]
        self.proxy_extra_hosts = hosts
        self._p_hosts.set(",".join(hosts))
        if self.proxy is not None:
            self.proxy.extra_hosts = list(hosts)
        self._save_config(proxy_extra_hosts=hosts)
        self._set_msg(f"额外域名已更新：{len(hosts)} 个")

    def _toggle_scan_logs(self):
        try:
            self.watcher.scan_logs = bool(self._p_scanlogs.get())
        except tk.TclError:
            return
        self._save_config(scan_logs=self.watcher.scan_logs)

    def _proxy_refresh(self, gen=None):
        if gen is None:
            gen = getattr(self, "_p_gen", 0)
        elif gen != getattr(self, "_p_gen", 0):
            return                      # 旧窗口的定时器，作废
        win = getattr(self, "_pwin", None)
        try:
            if win is None or not win.winfo_exists():
                return
        except tk.TclError:
            return
        lbl = getattr(self, "_p_lbls", None)
        if not lbl:
            return
        p = self.proxy
        st = p.status() if p is not None else None
        if st and st["running"]:
            lbl["svc"].configure(text=f"● 运行中 · {st['addr']}", fg=ACCENT)
        elif st and st["error"]:
            lbl["svc"].configure(text=f"✕ {st['error']}", fg=WARN)
        elif not self.ca.supported:
            lbl["svc"].configure(text="× 不可用（缺少 cryptography 库）", fg=WARN)
        else:
            lbl["svc"].configure(text="○ 未启动", fg=DIM)

        if not self.ca.supported:
            lbl["ca"].configure(text=self.ca.error or "不可用", fg=WARN)
        elif self.ca.available:
            if self.ca.is_installed():
                lbl["ca"].configure(text="● 已生成，且已加入系统信任区",
                                    fg=ACCENT)
            else:
                lbl["ca"].configure(text="● 已生成（尚未加入系统信任区）", fg=WARN)
        else:
            lbl["ca"].configure(text="○ 未生成", fg=DIM)

        cur = SystemProxy.read() if winreg is not None else {}
        server = str(cur.get("ProxyServer") or "")
        if cur.get("ProxyEnable") and str(self._proxy_port) in server:
            lbl["sys"].configure(text=f"● 已接管 → {server}", fg=ACCENT)
        elif cur.get("ProxyEnable"):
            lbl["sys"].configure(text=f"○ 已开启（别的程序设的 {server}）", fg=DIM)
        else:
            lbl["sys"].configure(text="○ 未开启", fg=DIM)
        envd = SystemProxy.read_env() if winreg is not None else {}
        hp = str(envd.get("HTTPS_PROXY") or "")
        if hp:
            lbl["env"].configure(
                text=f"● {hp}",
                fg=ACCENT if str(self._proxy_port) in hp else DIM)
        else:
            lbl["env"].configure(text="○ 未注入", fg=DIM)
        if st:
            lbl["hit"].configure(
                text=f"已解密 {st['sniffed']} · 直通 {st['passthru']} · "
                     f"解密失败 {st['failed']} · 生成中 {st['active']}",
                fg=FG)
        else:
            lbl["hit"].configure(text="-", fg=DIM)

        rows = list(p.recent)[:80] if p is not None else []
        sig = rows[0]["ts"] if rows else 0
        if sig != getattr(self, "_p_sig", None):
            self._p_sig = sig
            tree = getattr(self, "_p_tree", None)
            if tree is not None:
                tree.delete(*tree.get_children())
                for r in rows:
                    note = "估算" if r["est"] else "精确"
                    if r["status"] and not (200 <= r["status"] < 300):
                        note = f"HTTP {r['status']}"
                    tree.insert("", "end", values=(
                        time.strftime("%H:%M:%S", time.localtime(r["ts"])),
                        r["model"], r["provider"], fmt_tokens(r["inp"]),
                        fmt_tokens(r["out"]), f"{r['dur']:.1f}s", note,
                        r.get("host", "")),
                        tags=("est",) if r["est"] else ("ok",))
        try:
            if win.winfo_exists():
                win.after(1200, lambda: self._proxy_refresh(gen))
        except tk.TclError:
            pass

    @staticmethod
    def _load_config():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_config(self, **kw):
        cfg = self._load_config()
        cfg.update(kw)
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except OSError:
            pass


# ---------------------------------------------------------------- selftest

def selftest():
    print(f"[自检] 状态文件: {STATE_FILE}")
    # 自检 = 全量重算：不从 state.json 载入累计（也不会载入 offsets），
    # 否则「已载入的累计」会和本次从头扫描的记录重复相加。
    stats, meter = Stats(), SpeedMeter()
    q = queue.Queue()
    w = Watcher(stats, meter, q)
    t0 = now_s()
    w.poll()
    recs = 0
    while True:
        try:
            kind, payload = q.get_nowait()
            if kind == "record":
                recs += 1
        except queue.Empty:
            break
    print(f"[自检] 本次扫描 {now_s() - t0:.1f}s — 新增记录 {recs} 条")
    print(f"[自检] 文件数: {w.file_stats}")
    for title, snap in (("累计", stats.snapshot_cumulative()), ("今日", stats.snapshot_today())):
        print(f"\n按模型统计（{title}）:")
        # 与界面一致：同一模型可能来自多个客户端，按 (厂商, 模型) 合并显示
        merged = {}
        for (source, provider, model), a in snap.items():
            vendor = guess_provider(model) or provider or \
                SOURCE_NAMES.get(source, source) or "-"
            m = merged.get((vendor, model))
            if m is None:
                merged[(vendor, model)] = dict(a)
            else:
                for f in ("requests", "inp", "out", "cache_r", "cache_w",
                          "gen_s", "est_req"):
                    m[f] += a.get(f, 0)
                m["last_ts"] = max(m["last_ts"], a["last_ts"])
        rows = sorted(merged.items(),
                      key=lambda kv: -(kv[1]["inp"] + kv[1]["out"]))
        for (vendor, model), a in rows[:15]:
            speed = a["out"] / a["gen_s"] if a["gen_s"] else 0
            mark = "≈" if a.get("est_req") else ""
            print(f"  {model:<32} {vendor:<12} 请求{a['requests']:<5} "
                  f"输入{mark}{fmt_tokens(a['inp']):<10} 输出{fmt_tokens(a['out']):<10} "
                  f"缓存读{fmt_tokens(a['cache_r']):<10} 平均{speed:.1f} tok/s")
        if not rows:
            print("  (无记录)")
    cum, today = stats.totals()
    print(f"\n[自检] 今日合计 {fmt_tokens(today)} · 累计 {fmt_tokens(cum)} tokens")
    if not w.file_stats.get("zcode") and not w.file_stats.get("claude") \
            and not w.file_stats.get("workbuddy") \
            and not w.file_stats.get("codex"):
        print("[自检][警告] 未发现任何监控数据文件")


# ---------------------------------------------------------------- main

def _restore_from_backup():
    """把上次接管前的系统代理 / 环境变量还原回去。"""
    b = load_proxy_backup()
    if not b:
        return False
    try:
        if b.get("env"):
            SystemProxy.restore_env(b["env"])
        if b.get("sys"):
            SystemProxy.restore(b["sys"])
    except Exception:
        pass
    clear_proxy_backup()
    return True


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--selftest", action="store_true", help="命令行自检")
    parser.add_argument("--demo", action="store_true", help="演示模式（合成数据）")
    parser.add_argument("--fresh", action="store_true", help="忽略已保存的状态")
    parser.add_argument("--proxy", action="store_true",
                        help="启动时自动开启网络直采（接管系统代理）")
    parser.add_argument("--proxy-only", action="store_true",
                        help="只启动本地代理，不改动系统代理与环境变量"
                             "（供手动指向代理的程序使用）")
    parser.add_argument("--no-logs", action="store_true",
                        help="不扫描本地日志，只用网络直采")
    parser.add_argument("--port", type=int, default=0, help="网络直采监听端口")
    parser.add_argument("--restore", action="store_true",
                        help="还原系统代理设置后退出")
    args = parser.parse_args()

    if args.restore:
        ok = _restore_from_backup()
        print("[还原] 系统代理与环境变量已还原" if ok else "[还原] 没有需要还原的记录")
        return

    if args.selftest:
        selftest()
        return

    # 上次异常退出可能仍处于接管状态 —— 先还原，避免影响上网
    _restore_from_backup()

    stats, meter = Stats(), SpeedMeter()
    offsets = {} if args.fresh or args.demo else stats.load()

    q = queue.Queue()
    watcher = Watcher(stats, meter, q, demo=args.demo)
    watcher.offsets = offsets
    if args.no_logs:
        watcher.scan_logs = False
    ca = CertAuthority()

    # 高 DPI 适配 + 深色标题栏（尽力而为）
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = App(stats, meter, q, watcher, demo=args.demo, ca=ca)
    if args.port:
        app._proxy_port = args.port
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
    except Exception:
        hwnd = None
    watcher.start()
    threads = [watcher]
    if args.demo:
        demo = DemoSource(stats, meter, q, watcher)
        demo.start()
        threads.append(demo)
    if hwnd:
        try:
            import ctypes
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20,
                                                       ctypes.byref(ctypes.c_int(1)), 4)
        except Exception:
            pass
    if args.proxy and not args.demo:
        app.enable_direct_capture(quiet=True)
        app._update_status()
    elif args.proxy_only and not args.demo:
        ok, msg = app.start_proxy()
        app._set_msg(f"直采代理仅监听模式：{msg}"
                     if ok else f"直采代理启动失败：{msg}")
        app._update_status()
    app.mainloop()
    for t in threads:
        t.stop_flag.set()


if __name__ == "__main__":
    main()
