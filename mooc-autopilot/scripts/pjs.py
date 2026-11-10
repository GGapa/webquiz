# -*- coding: utf-8 -*-
"""带超时的 JS 求值。

为什么要这个（2026-11-07 血的教训）：
Playwright 的 `page.evaluate()` / `frame.evaluate()` **没有超时**。当 frame 正在导航、
或者 iframe 只挂了个空壳（执行上下文一直不 attach）时，`evaluate` 会**无限期挂住**，
整个批处理就卡死了（walk3 卡过 9 分钟、讨论帧卡过 7 分钟）。

`frame.wait_for_function()` 有 timeout 参数，超时会抛 TimeoutError 而不是挂死；
它返回 JSHandle，用 `.json_value()` 取回真实值。拿它当 evaluate 的替身即可。
"""
from __future__ import annotations


def ev(target, body: str, arg=None, timeout: int = 8000, default=None):
    """在 frame/page 上跑一段函数体（要自己 return），带超时。

    body 里可以直接用 `a` 拿到 arg：
        ev(frame, "const t = document.body.innerText; return t.slice(0, 20);")
        ev(frame, "return a.x + 1;", {"x": 41})

    超时 / 出错返回 default（默认 None），不会抛异常。

    注意 `polling=100`：默认轮询是 requestAnimationFrame，**窗口最小化/在屏幕外时 rAF 会停**，
    于是 wait_for_function 永远不触发、每次都超时（这就是“后台跑不动”的隐形杀手之一）；
    改成 100ms 的定时轮询，配合 Edge 的 --disable-background-timer-throttling 就不会停。
    """
    src = "(a) => ({v: (() => {\n" + body + "\n})()})"
    try:
        handle = target.wait_for_function(src, arg=arg, timeout=timeout, polling=100)
        payload = handle.json_value()
        if isinstance(payload, dict) and "v" in payload:
            return payload["v"]
        return default
    except Exception:  # noqa: BLE001
        return default


def alive(target, timeout: int = 5000) -> bool:
    """frame/page 的执行上下文是否可用（不挂死）。"""
    return ev(target, "return 1;", timeout=timeout) == 1
