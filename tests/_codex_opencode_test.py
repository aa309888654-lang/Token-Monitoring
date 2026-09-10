# -*- coding: utf-8 -*-
"""Codex / OpenCode / 开机自启 / 未知中转自动识别 的冒烟测试。

独立可执行：`python tests/_codex_opencode_test.py`
会自建临时目录，不污染真实配置。
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAILS = []


def check(name, got, want):
    ok = got == want
    if not ok:
        FAILS.append(name)
    print("  %-46s got=%-14s want=%-14s %s"
          % (name, str(got)[:14], str(want)[:14], "OK" if ok else "**FAIL**"))


def check_true(name, cond, note=""):
    if not cond:
        FAILS.append(name)
    print("  %-46s %s %s" % (name, "OK" if cond else "**FAIL**", note))


import tokenmon as T  # noqa: E402

print("[1] Codex rollout 解析")

tmp = tempfile.mkdtemp(prefix="tokenmon_cx_")
try:
    # 构造一个 Codex rollout：settings 带模型名，后面跟用量记录
    lines = [
        json.dumps({"timestamp": "2026-09-10T11:41:02.570Z", "type": "event_msg",
                    "payload": {"type": "thread_settings_applied",
                                "model": "gpt-5.6-sol"}}),
        json.dumps({"timestamp": "2026-09-10T11:41:33.394Z",
                    "type": "token_usage_record",
                    "payload": {"response_id": "resp_aaa",
                                "thread_id": "t1", "session_id": "s1",
                                "usage": {"input_tokens": 30447,
                                          "cached_input_tokens": 29440,
                                          "cache_write_input_tokens": 0,
                                          "output_tokens": 193,
                                          "reasoning_output_tokens": 56,
                                          "total_tokens": 30640}}}),
        # 重复写一遍同一 response_id —— 不应重复计数
        json.dumps({"timestamp": "2026-09-10T11:41:33.394Z",
                    "type": "token_usage_record",
                    "payload": {"response_id": "resp_aaa",
                                "usage": {"input_tokens": 30447,
                                          "cached_input_tokens": 29440,
                                          "output_tokens": 193,
                                          "reasoning_output_tokens": 56}}}),
        json.dumps({"timestamp": "2026-09-10T11:43:16.995Z",
                    "type": "token_usage_record",
                    "payload": {"response_id": "resp_bbb",
                                "usage": {"input_tokens": 42181,
                                          "cached_input_tokens": 29440,
                                          "output_tokens": 215,
                                          "reasoning_output_tokens": 13}}}),
    ]
    d = T._as_dict(lines[0])
    check("模型名提取", T.codex_model_of(d), "gpt-5.6-sol")

    rec = T.parse_codex(T._as_dict(lines[1]), "gpt-5.6-sol")
    # input 含缓存：30447 - 29440 = 1007
    check("首条 inp（已扣缓存）", rec["inp"], 1007)
    # 输出要含推理：193 + 56 = 249
    check("首条 out（含推理）", rec["out"], 249)
    check("首条 cache_r", rec["cache_r"], 29440)
    check("首条厂商", rec["provider"], "OpenAI")
    check("去重键", rec["key"], "codex:resp_aaa")

    # 非用量行不产出
    check("event_msg 不产出记录",
          T.parse_codex(T._as_dict(lines[0]), "gpt-5.6-sol"), None)

    # 走 Watcher 管线验证去重（同 response_id 只算一次）
    stats, meter = T.Stats(), T.SpeedMeter()
    import queue
    w = T.Watcher(stats, meter, queue.Queue())
    fp = os.path.join(tmp, "rollout-2026-09-10T19-00-00-abc.jsonl")
    with open(fp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    for ln in lines:
        r = w._parse_line("codex", ln, fp)
        if r:
            w._emit(r)
    tot_in = sum(a["inp"] for a in stats.snapshot_cumulative().values())
    tot_out = sum(a["out"] for a in stats.snapshot_cumulative().values())
    # 1007 + (42181-29440)=12741 → 13748；重复那条被丢弃
    check("两条唯一调用的输入合计", tot_in, 1007 + 12741)
    check("两条唯一调用的输出合计", tot_out, 249 + 228)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n[2] OpenCode SQLite 解析")
tmp2 = tempfile.mkdtemp(prefix="tokenmon_oc_")
try:
    import sqlite3
    db = os.path.join(tmp2, "opencode.db")
    conn = sqlite3.connect(db)
    conn.execute("create table message (id text, session_id text, "
                 "time_created integer, time_updated integer, data text)")
    rows = [
        ("msg_1", "ses_1", 1, 1, json.dumps({
            "role": "user", "modelID": "ling-3.0-flash", "time": {"created": 1}})),
        ("msg_2", "ses_1", 2, 2, json.dumps({
            "role": "assistant", "modelID": "ling-3.0-flash",
            "providerID": "opencode",
            "tokens": {"total": 30551, "input": 231, "output": 172,
                       "reasoning": 45,
                       "cache": {"write": 0, "read": 30103}},
            "time": {"created": 2000, "completed": 5000}})),
        ("msg_3", "ses_1", 3, 3, json.dumps({
            "role": "assistant", "modelID": "nemotron-3.5",
            "tokens": {"input": 100, "output": 20, "reasoning": 5,
                       "cache": {"write": 3, "read": 7}},
            "time": {"created": 3000, "completed": 4000}})),
    ]
    conn.executemany("insert into message values (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    r2 = T.parse_opencode("msg_2", "ses_1", json.loads(rows[1][4]))
    check("OpenCode inp（不含缓存，不扣）", r2["inp"], 231)
    check("OpenCode out（含推理）", r2["out"], 217)
    check("OpenCode cache_r", r2["cache_r"], 30103)
    check("OpenCode 耗时(s)", round(r2["dur"], 1), 3.0)
    check("OpenCode 去重键", r2["key"], "oc:msg_2")
    check("user 行不产出", T.parse_opencode("msg_1", "ses_1",
                                           json.loads(rows[0][4])), None)
    r3 = T.parse_opencode("msg_3", "ses_1", json.loads(rows[2][4]))
    check("第二个模型", r3["model"], "nemotron-3.5")
    check("第二个 cache_w", r3["cache_w"], 3)

    # 走 Watcher 的 SQLite 轮询（_oc_db 指到临时库）
    stats, meter = T.Stats(), T.SpeedMeter()
    import queue
    w = T.Watcher(stats, meter, queue.Queue())
    w._oc_db = db
    w._last_oc_poll = 0.0
    w._poll_opencode(force=True)
    snap = stats.snapshot_cumulative()
    check("轮询入库条数", sum(a["requests"] for a in snap.values()), 2)
    check("轮询后 _oc_last 已推进", w._oc_last > 0, True)
    w._poll_opencode(force=True)   # 再扫一次不应重复
    check("重复扫描不重复计数",
          sum(a["requests"] for a in stats.snapshot_cumulative().values()), 2)
finally:
    shutil.rmtree(tmp2, ignore_errors=True)

print("\n[3] 未知中转自动识别")
check("api.foo-relay.com 值得探测", T.is_probe_host("api.foo-relay.com"), True)
check("IP + 非标端口值得探测", T.is_probe_host("36.151.149.103", 8080), True)
check("IP + 443 不探测", T.is_probe_host("36.151.149.103", 443), False)
check("localhost 不探测", T.is_probe_host("127.0.0.1", 15721), False)
check("普通网站不探测", T.is_probe_host("www.taobao.com"), False)
check("gov 域名不探测", T.is_probe_host("api.gov.cn"), False)

print("\n[4] 开机自启注册表")
if T.winreg is None:
    print("  跳过（非 Windows）")
else:
    before = T.Autostart.enabled()
    ok_on, msg_on = T.Autostart.set_on(True)
    check_true("写入 Run 成功", ok_on, msg_on)
    check("enable 读回", T.Autostart.enabled(), True)
    ok_off, msg_off = T.Autostart.set_on(False)
    check("取消后读回", T.Autostart.enabled(), False)
    T.Autostart.set_on(before)
    check("恢复原状", T.Autostart.enabled(), before)

print()
if FAILS:
    print("[结果] 失败 %d 项: %s" % (len(FAILS), FAILS))
    sys.exit(1)
print("[结果] 全部通过 ✔")
