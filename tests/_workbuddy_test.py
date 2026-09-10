# -*- coding: utf-8 -*-
"""回归测试：WorkBuddy 转录解析 / 三种口径修正 / 重复计数消除。

跑法：  C:\\Python314\\python.exe tests\\_workbuddy_test.py

覆盖的坑（都是实测踩出来的）：
  1. ZCode 的 inputTokens 已含 cacheReadTokens —— 必须减掉，否则输入被整份重复计入
  2. Claude Code 把同一次调用分多次写盘（message.id 相同）—— 必须按 id 去重、
     并丢弃 output=0 的半截记录，否则虚高约 2.3 倍
  3. WorkBuddy 转录里 input_tokens 同样含缓存读（与 Claude 的命名相反）
  4. 第三方中转不回传输入用量时（input_tokens 恒为 0），按会话文本估算
  5. records.jsonl 不能因为「回填 + 首次全量扫描」而写两遍
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokenmon as T   # noqa: E402

FAILED = []


def check(name, got, want):
    ok = got == want
    print("  %-52s got=%-12s want=%-12s %s"
          % (name, got, want, "OK" if ok else "FAIL"))
    if not ok:
        FAILED.append(name)


def check_between(name, got, lo, hi):
    ok = lo <= got <= hi
    print("  %-52s got=%-12s 期望[%s,%s] %s"
          % (name, got, lo, hi, "OK" if ok else "FAIL"))
    if not ok:
        FAILED.append(name)


def wl(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main():
    tmp = tempfile.mkdtemp(prefix="tokenmon-wb-")
    try:
        # ---- 隔离出假的目录结构，绝不碰真实数据 ----
        wb_dir = os.path.join(tmp, "wb", "proj-a")
        cl_dir = os.path.join(tmp, "claude", "proj-a")
        zc_dir = os.path.join(tmp, "zcode")
        zlog_dir = os.path.join(tmp, "zlog")
        for d in (wb_dir, cl_dir, zc_dir, zlog_dir):
            os.makedirs(d, exist_ok=True)
        app_dir = os.path.join(tmp, "app")
        os.makedirs(app_dir, exist_ok=True)

        T.WORKBUDDY_PROJECTS_DIR = os.path.join(tmp, "wb")
        T.CLAUDE_PROJECTS_DIR = os.path.join(tmp, "claude")
        T.ZCODE_ROLLOUT_DIR = zc_dir
        T.ZCODE_LOG_DIR = zlog_dir
        T.APP_DIR = app_dir
        T.LOG_FILE = os.path.join(app_dir, "records.jsonl")
        T.STATE_FILE = os.path.join(app_dir, "state.json")

        # ---------------------------------------------------- 造 WorkBuddy 转录
        wb = os.path.join(wb_dir, "sess.jsonl")
        # 一次调用的分片记录（不带 usage）—— 不能算数
        wl(wb, {"id": "r0", "type": "reasoning", "parentId": "p0",
                "providerData": {"model": "glm-5.3-flash"}})
        # 真正带 usage 的两条
        wl(wb, {"id": "r1", "type": "function_call", "parentId": "p1",
                "sessionId": "s1", "timestamp": 1789033742446,
                "providerData": {"model": "glm-5.3-flash"},
                "message": {"usage": {"input_tokens": 1000, "output_tokens": 100,
                                      "total_tokens": 1100,
                                      "cache_read_input_tokens": 600}}})
        wl(wb, {"id": "r2", "type": "message", "parentId": "p2",
                "sessionId": "s1", "timestamp": 1789033752446,
                "providerData": {"model": "hy4-preview"},
                "message": {"usage": {"input_tokens": 2000, "output_tokens": 50,
                                      "cache_read_input_tokens": 1500}}})
        # 非 jsonl 的旁路文件必须被忽略
        wl(os.path.join(wb_dir, "x.file-rollback.ndjson"),
           {"message": {"usage": {"input_tokens": 99999, "output_tokens": 99999}}})

        # ---------------------------------------------------- 造 Claude Code 日志
        cl = os.path.join(cl_dir, "sess.jsonl")
        LONG = "x" * 4000     # 4000 字符英文 → 约 1000 token
        wl(cl, {"type": "user", "sessionId": "c1",
                "message": {"role": "user",
                            "content": [{"type": "text", "text": LONG}]}})
        # 同一次调用被写三遍：半截 + 补全 + 完全重复
        wl(cl, {"type": "assistant", "sessionId": "c1",
                "timestamp": "2026-09-10T08:00:00.000Z",
                "message": {"id": "m1", "model": "deepseek-v4-pro",
                            "usage": {"input_tokens": 100, "output_tokens": 0},
                            "content": []}})
        wl(cl, {"type": "assistant", "sessionId": "c1",
                "timestamp": "2026-09-10T08:00:01.000Z",
                "message": {"id": "m1", "model": "deepseek-v4-pro",
                            "usage": {"input_tokens": 5000, "output_tokens": 200,
                                      "cache_read_input_tokens": 4000,
                                      "cache_creation_input_tokens": 300},
                            "content": []}})
        wl(cl, {"type": "assistant", "sessionId": "c1",
                "timestamp": "2026-09-10T08:00:01.100Z",
                "message": {"id": "m1", "model": "deepseek-v4-pro",
                            "usage": {"input_tokens": 5000, "output_tokens": 200,
                                      "cache_read_input_tokens": 4000,
                                      "cache_creation_input_tokens": 300},
                            "content": []}})
        # 第三方中转：上游不回传输入用量 → 应走字符估算
        wl(cl, {"type": "assistant", "sessionId": "c1",
                "timestamp": "2026-09-10T08:00:02.000Z",
                "message": {"id": "m2", "model": "gpt-5.6-sol",
                            "usage": {"input_tokens": 0, "output_tokens": 300},
                            "content": []}})

        # ---------------------------------------------------- 造 ZCode rollout
        zc = os.path.join(zc_dir, "model-io-1.jsonl")
        wl(zc, {"requestId": "z1", "attempt": 1,
                "completedAt": "2026-09-10T08:14:11.784Z", "durationMs": 1000,
                "model": {"modelId": "deepseek-v4-pro", "providerId": "abc"},
                "response": {"usage": {"inputTokens": 1000, "outputTokens": 100,
                                       "totalTokens": 1100,
                                       "cacheReadTokens": 600}}})

        # ---------------------------------------------------- 跑一轮
        stats = T.Stats()
        meter = T.SpeedMeter()
        import queue
        q = queue.Queue()
        w = T.Watcher(stats, meter, q)
        w._backfill_log()          # 与真实启动顺序一致：先回填，再扫描
        w.poll()

        snap = stats.snapshot_cumulative()
        got = {k: v for k, v in snap.items()}

        print("\n[1] 解析结果")
        for k in sorted(got, key=lambda x: str(x)):
            a = got[k]
            print("     %-40s 请求=%-3d 输入=%-8d 输出=%-6d 缓存读=%-8d 缓存写=%d"
                  % ("%s|%s|%s" % k, a["requests"], a["inp"], a["out"],
                     a["cache_r"], a["cache_w"]))

        print("\n[2] ZCode：inputTokens 含缓存读 → 必须拆开")
        z = got.get(("zcode", "abc", "deepseek-v4-pro"))
        check("zcode 存在", z is not None, True)
        if z:
            check("zcode 输入(新增,不含缓存)", z["inp"], 400)
            check("zcode 输出", z["out"], 100)
            check("zcode 缓存读", z["cache_r"], 600)

        print("\n[3] Claude Code：同一 message.id 只算一次，半截记录丢弃")
        c = got.get(("claude-code", "anthropic", "deepseek-v4-pro"))
        check("claude 请求数(应为 1)", c["requests"] if c else None, 1)
        if c:
            check("claude 输入", c["inp"], 5000)
            check("claude 输出", c["out"], 200)
            check("claude 缓存写", c["cache_w"], 300)

        print("\n[4] Claude Code：输入用量缺失时按文本估算")
        g = got.get(("claude-code", "anthropic", "gpt-5.6-sol"))
        check("gpt-5.6-sol 存在", g is not None, True)
        if g:
            check("gpt-5.6-sol 请求数", g["requests"], 1)
            check("gpt-5.6-sol 输出", g["out"], 300)
            check_between("gpt-5.6-sol 输入(估算 4000 字符≈1000)", g["inp"], 950, 1100)

        print("\n[5] WorkBuddy：读数正确、分片不重复、非 jsonl 被忽略")
        wb1 = got.get(("workbuddy", "智谱GLM", "glm-5.3-flash"))
        check("wb glm 存在", wb1 is not None, True)
        if wb1:
            check("wb glm 请求数(2 条 -> 只算 1 条 usage)", wb1["requests"], 1)
            check("wb glm 输入(1000-600)", wb1["inp"], 400)
            check("wb glm 输出", wb1["out"], 100)
            check("wb glm 缓存读", wb1["cache_r"], 600)
        wb2 = got.get(("workbuddy", "腾讯混元", "hy4-preview"))
        check("wb hy4 厂商识别=腾讯混元", wb2 is not None, True)
        if wb2:
            check("wb hy4 输入(2000-1500)", wb2["inp"], 500)
            check("wb hy4 缓存读", wb2["cache_r"], 1500)
        total_wb = sum(v["inp"] for k, v in got.items() if k[0] == "workbuddy")
        check("wb 合计输入(99999 未被计入)", total_wb, 900)

        print("\n[6] records.jsonl 不重复写（回填 + 首次扫描只留一份）")
        rows = [json.loads(l) for l in open(T.LOG_FILE, encoding="utf-8")
                if l.strip()]
        keys = [r.get("key") for r in rows]
        check("明细行数", len(rows), len(set(keys)))
        check("无重复 key", len(keys) - len(set(keys)), 0)

        print("\n[7] 输入口径一致性：inp 都不含缓存读")
        for k, a in got.items():
            if a["inp"] < 0:
                check("负输入 %s" % (k,), a["inp"], 0)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILED:
        print("[结果] 失败 %d 项：%s" % (len(FAILED), FAILED))
        return 1
    print("[结果] 全部通过 ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
