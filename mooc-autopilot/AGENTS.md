# AGENTS.md — 给接手的 AI 的作业说明

你拿到的是一个**中国大学MOOC（icourse163）自动化工具**。本文件告诉你：目标是什么、按什么顺序做、什么绝对不能做、失败了怎么办。

---

## 0. 一句话目标

用 `python -m mooc` 在**用户自己的电脑、自己的账号**上，批量完成课程的看视频、读文档、发讨论、做测验、交作业。

**你不是在写代码，你是在操作一个已经装好的工具。**

---

## 1. 先判断：能不能开工

按顺序执行，每步都有明确判据：

```bash
cd mooc-autopilot
python -m mooc doctor --json
```

**判据**：返回的 JSON 数组里，所有 `critical: true` 的项都是 `ok: true`。

| 失败项 | 你怎么做 |
|---|---|
| `cdp` 失败 | 执行该项的 `fix_cmd`（会自动拉起浏览器）；或 `python -m mooc doctor --fix` |
| `temp` 失败 | 同上 `--fix` |
| `config` 失败 | `--fix` 会复制模板；**然后必须请用户填课程 URL**（见第 3 节的禁止事项） |
| `deps` 失败 | `pip install -r requirements.txt` |
| `font` 失败（非关键） | 只有超星用；慕课不需要，可忽略 |

**只要还有 critical 项失败，就不要往下做。**

---

## 2. 标准执行顺序

```bash
# ① 生成课程清单（后面所有操作都依赖它）
python -m mooc plan
# 判据：out/mooc_plan.json 存在，且每门课有 detail 数组

# ② 先小规模验证（必做！）
python -m mooc video --limit 1
python -m mooc text --docs-only --limit 1
# 判据：日志出现 learned=True 或「回复数 x->x+1」

# ③ 验证通过后再全量
python -m mooc video
python -m mooc text --docs-only
python -m mooc text --discuss-only

# ④ 测验/作业（需要具体 URL）
python -m mooc quiz --url "<测验页 URL>" --tag 第1章
python -m mooc hw --url "<作业页 URL>" --answers answers.json --submit

# ⑤ 收尾：再跑一次 doctor，确认环境没被搞坏
python -m mooc doctor
```

---

## 3. 绝对不要做的事

| 禁止 | 原因 |
|---|---|
| **猜课程 URL** | `#/learn/content` 的课程 ID 只有用户知道；填错会跑到别的课 |
| **猜 Cookie** | 无法生成；没有就让用户提供 |
| **跳过 `--limit 1` 直接全量** | 选择器可能已变，全量会跑一堆无效操作 |
| **不确认就 `--submit`** | 提交不可逆；先不加 `--submit` 看日志 |
| **操作别人的账号/课程** | 违反平台条款，也可能违法 |
| **碰考试、人脸识别** | 本工具不覆盖，也不要尝试绕过 |
| **把 config.yaml / cookies.txt 提交或外发** | 含账号凭据 |

---

## 4. 失败了怎么办

**先跑 `python -m mooc doctor --json`**，读每一项的 `cause` 和 `fix_cmd`。

每个失败项都带三个字段，照做即可：

```json
{
  "key": "cdp",
  "ok": false,
  "cause": "浏览器没带 --remote-debugging-port 启动，或端口被占",
  "fix_cmd": "\"...msedge.exe\" --remote-debugging-port=9222 ...",
  "auto_fix": "browser"
}
```

- 有 `auto_fix` → `python -m mooc doctor --fix` 直接修
- 没有 `auto_fix` → 执行 `fix_cmd`，或按 `docs/troubleshooting.md` 的症状表查

**`docs/troubleshooting.md` 里有 13 条症状 → 命令的对照表**，遇到报错先查它。

---

## 5. 各命令的产物在哪

| 命令 | 产物 | 怎么判断成功 |
|---|---|---|
| `plan` | `out/mooc_plan.json` | 每门课有 `detail`，条目带 `learned` |
| `video` | `out/mooc_video_run.log` | `-> learned=True` |
| `text` | `out/mooc_text_run.log` | `回复数 x->x+1` |
| `quiz` | `out/mooc_quiz_state.json` | `score: 28.00/30.00` |
| `hw` | `out/mooc_hw.log` | `已勾选 N/N`，页面「已完成并提交」 |

---

## 6. 什么时候算完成

- `python -m mooc plan` 之后的清单里，目标条目都 `learned: true`
- 或者用户明确说停

**完成前再跑一次 `doctor`**，确认没留下坏状态（比如临时目录被改、浏览器被关）。

---

## 7. 需要读的文档（按优先级）

1. 本文件（你在看的）
2. `docs/setup.md` —— 用户要提供什么数据、每步怎么验证
3. `docs/troubleshooting.md` —— 症状 → 命令
4. `docs/pitfalls.md` —— 为什么代码要这么写（改代码前必读）
5. `SECURITY.md` / `DISCLAIMER.md` —— 边界与责任

---

## 8. 如果你要改代码

- 改选择器前先读 `docs/pitfalls.md`，里面有 13 条「为什么不能用直觉写法」；
- 一切 JS 求值走 `scripts/pjs.py` 的 `ev()`（带超时），**不要**直接用 `page.evaluate()`；
- 提交前必须回读 `aria-checked` / `input.checked`，勾不满就**不要提交**；
- 改完跑 `python -m mooc doctor` 和一次 `--limit 1` 验证。
