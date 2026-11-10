# 排障手册：症状 → 原因 → 一条能直接跑的命令

这份手册的目标：**任何人（或任何 AI）遇到问题，能在这里找到一条可执行的命令，而不是重新调试一遍。**

先跑一次自检，大部分问题会被直接指出来：

```bash
python -m mooc doctor          # 人看
python -m mooc doctor --json   # 程序读（含 cause / fix_cmd / auto_fix）
python -m mooc doctor --fix    # 自动修能修的部分
```

---

## 一、症状速查表

| 你会看到 | 原因 | 直接跑这一条 | 能自愈吗 |
|---|---|---|---|
| `连不上浏览器（http://127.0.0.1:9222）` | 浏览器没用调试端口启动 | `python -m mooc doctor --fix` | ✅ 自动拉起 |
| `No usable temporary directory found` | `TEMP` 指向不存在/不可写目录 | `python -m mooc doctor --fix` | ✅ 自动改用 `.tmp` |
| `找不到 config.yaml` | 没从模板复制 | `python -m mooc doctor --fix` | ✅ 复制模板（**仍需你填课程 URL**） |
| `config.yaml 里 icourse163.courses 是空的` | 课程 URL 没填 | 编辑 `config.yaml`，填 `课程名: "https://.../learn/XXX-123#/learn/content"` | ❌ 只有你知道 |
| 超星题目显示 `嘍嗁喿嗀` | 字体混淆，缺参考字体 | `python scripts/fetch_reference_font.py` | ✅ |
| 超星页面要求登录 / 跳登录页 | Cookie 过期 | 重新复制 Cookie 到 `cookies.txt` | ❌ |
| 慕课页面跳 `/passport/member/logout` | 登录态被踢 | 在调试浏览器里重新登录一次 | ❌ |
| `click failed` 一片 | SPA 没重渲染（hash 路由） | 已在代码里修（先 `about:blank` 再进）；仍失败就 `python -m mooc plan` 重建清单 | ✅ 代码已处理 |
| 提交后 0 分 / “未作答” | 选项没真的勾上 | 已用 `aria-checked` 回读校验；日志出现「勾选不足，不提交」就说明被挡下了 | ✅ 代码已处理 |
| 作业显示已提交但没有附件 | 上传没完成就提交 | 上传后回读答题区，见 `mooc_hw_fill` 的 `upload()`；失败就重开作业页重传 | ⚠️ 半自动 |
| 讨论发了但 `learned` 不变 | 每日回帖上限 / 需审核 | 等次日；`python -m mooc text --discuss-only` | ❌ 平台限制 |
| `ModuleNotFoundError: playwright` | 没装依赖 | `pip install -r requirements.txt` | ✅ |
| `invalid non-printable character U+FEFF` | 文件带 BOM | `python scripts/strip_bom.py`（见仓库脚本） | ✅ |

---

## 二、给 AI / 脚本的执行顺序（Playbook）

如果你要让另一个 AI 接手，直接让它按这个顺序做，**每一步都有明确成功判据**：

```
1) python -m mooc doctor --json
   判据：所有 critical=true 的项 ok=true
   失败：执行 fix_cmd；若该项有 auto_fix，直接 python -m mooc doctor --fix

2) python -m mooc doctor --json | grep '"key": "config"'
   判据：detail 里课程数 >= 1
   失败：需要人工填 config.yaml（AI 不要猜课程 URL）

3) python -m mooc plan
   判据：输出 out/mooc_plan.json，且每门课有 detail

4) 按需执行：
   python -m mooc video --limit 1     # 先跑 1 条验证
   python -m mooc text --docs-only --limit 1
  判据：日志出现 learned=True / 回复数 +1

5) 全量执行，最后再跑一次 doctor 确认环境没被搞坏
```

**关键约定**：AI 不要自己编课程 URL、不要猜 Cookie、不要跳过 `--limit 1` 的验证步骤。

---

## 三、这些风险在代码里是怎么被“挡掉”的

| 风险 | 代码位置 | 挡掉的方式 |
|---|---|---|
| JS 求值卡死 | `scripts/pjs.py` | 用 `wait_for_function(polling=100)` 代替 `evaluate`，超时返回默认值 |
| 窗口不可见导致 rAF 停摆 | `env.py` 的启动参数注释 + README | 显式 `polling=100`，不用 rAF |
| SPA hash 路由不重载 | `scripts/mooc_*_walk.py` 的 `open_list()` | 先 `goto("about:blank")` 再进目标 URL |
| 选项没勾上就提交 | `mooc_quiz_do.py` / `mooc_text_walk.py` 的填涂逻辑 | 回读 `aria-checked`；勾选数不足直接**拒绝提交** |
| 提交确认弹窗 | `quiz_retake.py` / `mooc_quiz_do.py` | 点完提交后循环找 `#popok` 并点掉 |
| 讨论“假成功” | `mooc_post6.py` / `mooc_post_json.py` | 提交后 reload，对比「共 N 个回复」是否 +1 |
| 附件没传上 | `mooc_hw_fill.py` 的 `upload()` | 上传后回读答题区 |
| 连不上浏览器 | `scripts/env.py` 的 `connect()` | 抛 `SystemExit` 并附启动命令（不是 traceback） |
| 配置缺失 | `scripts/courses.py` | 惰性加载 + 中文提示 + 模板复制命令 |
| 环境不可用 | `mooc/doctor.py` | 逐项检查 + `--fix` 自动修 + `--json` 给程序读 |

---

## 四、仍然挡不掉的风险（诚实说明）

这几类**只能靠人**，代码无法替你挡：

1. **平台改版**：选择器失效。`doctor --live`（规划中）会探测关键选择器是否还在，但改版后具体怎么改，得人工看页面。
2. **账号风控**：请求过快、异地登录。代码里有随机等待，但阈值由平台决定。
3. **每日额度**：讨论发帖上限。只能等次日。
4. **学术规范**：这门课允许不允许自动化，只有你和老师知道。

---

## 五、给维护者：怎么加一条新的检查

1. 在 `mooc/doctor.py` 里写一个 `check_xxx() -> Check`；
2. 填 `cause`（为什么会这样）、`fix_cmd`（人能直接跑的命令）、`auto_fix`（内部修复动作名）；
3. 如果需要自动修复，在 `try_fix()` 里加一个分支；
4. 把 `check_xxx()` 加进 `main()` 的检查序列；
5. 在本手册第一节的表格里补一行。

这样下一个人遇到同样问题，`doctor` 直接告诉他怎么修。
