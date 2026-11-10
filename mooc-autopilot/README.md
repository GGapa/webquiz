# mooc-autopilot（icourse163 子项目）

> 📁 **这是 `webquiz` 仓库里的子项目**：本目录只放「中国大学MOOC（icourse163）」这一半的自动化脚本。
> 仓库根目录的 `webquiz/` 是超星（学习通）那一半，两者互不影响，配置思路一致。
>
> 在本目录下执行命令：`cd mooc-autopilot` 后再 `python -m mooc ...`。

用 Playwright + Chrome DevTools Protocol **接管一个已经登录好的浏览器**，批量完成网课里的重复操作：看视频、读文档、发讨论、做随堂测验/单元测验、交作业。

支持两个平台：

| 平台 | 能力 |
|---|---|
| **超星学习通**（mooc1/mooc2-ans.chaoxing.com） | 章节测验：发现、解码（含字体混淆）、离线答题模板、自动填涂与提交、重考循环 |
| **中国大学MOOC**（icourse163.org，含 SPOC） | 视频续播、文档打卡、讨论区发帖、随堂测验、单元测验、作业填答 |

> ⚠️ **使用前必读**
> - [DISCLAIMER.md](DISCLAIMER.md) —— **免责条款**：本项目按「现状」提供、无任何担保，使用风险与合规责任由使用者自行承担。不同意条款请勿使用。
> - [SECURITY.md](SECURITY.md) —— **安全申明**：数据全部留在本地、哪些文件属于敏感信息、API Key 怎么放。
> - [docs/setup.md](docs/setup.md) —— **你需要提供哪些数据 + 完整操作流程**。
>
> 一句话：本项目是浏览器自动化的技术示例，用于学习 Playwright + CDP 的工程实践；请只操作你自己的账号与课程，并遵守平台条款与学校学术规范。

---

## 三分钟上手

```bash
# 1. 装依赖
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# 2. 环境自检（会告诉你缺什么、怎么修；--fix 自动修）
python -m mooc doctor
python -m mooc doctor --fix

# 3. 准备配置（详见 docs/setup.md）
copy config.example.yaml config.yaml     # 填课程 URL、Cookie

# 4. 用带调试端口的浏览器登录（doctor --fix 也能帮你拉起），然后
python -m webquiz discover -c config.yaml          # 超星：扫课程
python -m mooc plan                                # 慕课：生成清单
```

**你只需要提供 4 样东西**（全部留在本地，无需提供账号密码）：

| 数据 | 从哪来 | 放哪 |
|---|---|---|
| 浏览器调试端口 | 启动浏览器时指定（默认 9222） | `config.yaml` |
| 课程页 URL | 浏览器地址栏复制 | `config.yaml` |
| 登录 Cookie | 开发者工具 → Network → Request Headers | `cookies.txt` |
| 大模型 API Key（可选） | 自行申请 | 环境变量 `DEEPSEEK_API_KEY` |

详见 [docs/setup.md](docs/setup.md)。

---

## 为什么不用「无头浏览器 + 账号密码登录」

网课平台普遍有风控（滑块、扫码、异地登录校验），脚本登录既脆弱又容易触发风控。本项目走另一条路：

1. 你自己用**带调试端口的 Chrome/Edge** 打开并登录；
2. 脚本通过 CDP `connect_over_cdp("http://127.0.0.1:9222")` 接管这个浏览器；
3. 所有操作复用你的登录态，不接触账号密码。

启动示例（Windows）：

```bat
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir=C:\edge-debug ^
  --disable-background-timer-throttling ^
  --disable-backgrounding-occluded-windows ^
  --disable-renderer-backgrounding ^
  --disable-features=CalculateNativeWinOcclusion,IntensiveWakeUpThrottling ^
  --mute-audio --window-position=-3200,-3200 --window-size=1280,800
```

`--window-position=-3200,-3200` 把窗口放到屏幕外，`--mute-audio` 静音，
几个 `--disable-*-throttling` 保证窗口不在前台时 JS 定时器不被降频（**这条很关键**，见 `docs/pitfalls.md`）。

---

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

如果要用超星的「字体混淆」解码，先下载参考字体（约 16 MB，不放进仓库）：

```bash
python scripts/fetch_reference_font.py
```

## 配置

```bash
copy config.example.yaml config.yaml
```

`config.yaml` 里填两类东西：

```yaml
# 1) 超星：把课程页地址栏 studentstudy?... 整段粘进来
course:
  main_url: "https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=...&courseId=...&enc=..."
  cookie_file: "cookies.txt"

# 2) 中国大学MOOC：课程名 -> 课程内容页链接
icourse163:
  courses:
    我的课程A: "https://www.icourse163.org/learn/XXX-1234567#/learn/content"
```

`cookies.txt` 支持两种格式：浏览器开发者工具里复制的整段 Cookie 头，或 JSON 数组。

## 用法

### 超星学习通（章节测验）

```bash
# 1. 扫一遍课程，列出所有章节/小节/测验，把页面存到 out/html
python -m webquiz discover -c config.yaml

# 2. 解码题目（会对字体混淆的字形做匹配还原）
python -m webquiz decode -c config.yaml

# 3. 生成答题纸与答案模板（offline 也能用）
python -m webquiz solve -c config.yaml

# 4. 填答案（--confirm 才真正提交）
python -m webquiz submit -c config.yaml --answers answers.json --confirm

# 作业（mooc2/work/dowork 那种）
python -m webquiz homework -c config.yaml --url "<作业页 URL>"
```

### 中国大学MOOC（视频 / 文档 / 讨论 / 测验 / 作业）

统一入口是 `python -m mooc`，每个子命令都能单独 `--help`：

```bash
python -m mooc plan                          # ① 生成课程清单（后面都依赖它）
python -m mooc video --limit 2               # ② 刷视频（2 倍速）
python -m mooc text --docs-only              # ③ 只做文档
python -m mooc text --discuss-only           # ④ 只发讨论
python -m mooc quiz-list                     # ⑤ 枚举每门课的测验 id
python -m mooc quiz --url "<测验页 URL>" --tag 第1章 --votes 2
python -m mooc suip --cids 123456,234567     # 随堂测验
python -m mooc hw --url "<作业页>" --answers answers.json --submit
```

每个子命令都支持 `--course "课程名"` 只做某一门课（名字要和 `config.yaml` 里一致）。

底层是 `scripts/` 下的独立脚本，也可以直接跑（行为完全一致）：

```bash
python scripts/mooc_refresh_plan.py
python scripts/mooc_video_walk.py --limit 2
python scripts/mooc_text_walk.py --no-disc
python scripts/mooc_quiz_list.py
python scripts/mooc_quiz_do.py 第1章 "https://www.icourse163.org/learn/XXX-123#/learn/quiz?id=456"
python scripts/mooc_hw_fill.py --url "<作业页>" --answer-file answers.json --submit
```

---

## 目录结构

```
webquiz/                 超星那套的库（CLI：discover/decode/solve/submit/homework）
  browser.py             浏览器启动/接管、点击小节、找作业帧
  fontdecode.py          字体混淆解码（把乱码字形还原成真字）
  parse.py               题目解析（单选/多选/判断/填空）
  fill.py                填涂与提交（含重考）
  dowork.py              作业（dowork）填答
mooc/                    慕课统一入口：python -m mooc <plan|video|text|quiz|suip|hw>
scripts/
  courses.py             从 config.yaml 读课程列表（惰性加载）
  env.py                 CDP 地址、输出目录、连接失败时的友好提示
  pjs.py                 带超时的 JS 求值（避免 evaluate 卡死）
  mooc_*.py              icourse163 的各个动作驱动（也可单独运行）
  fetch_reference_font.py 下载参考字体
docs/
  setup.md               你需要提供的数据 + 完整操作流程
  pitfalls.md            踩过的坑与设计取舍（强烈建议先读）
SECURITY.md              安全申明：数据流向、敏感文件、API Key 管理
DISCLAIMER.md            免责条款（使用前必读）
```

## 兼容性与已知限制

**已验证可用的场景（我在干净目录实测过）**

| 项 | 状态 |
|---|---|
| `python -m webquiz --help` / 各子命令 `-c` 参数 | ✅ 正常 |
| `scripts/*.py --help` | ✅ 打印用法后退出，不连浏览器、不读配置 |
| 没有 `config.yaml` 时 | ✅ 给出可操作的中文提示（不是 traceback） |
| 浏览器没启动 / 端口不对 | ✅ 提示"连不上浏览器"并给出启动命令 |
| `CDP_URL` 环境变量覆盖端口 | ✅ 生效 |

**前置条件**

- **Python 3.10+**（代码用了 `str | None`、`dict[str, str]` 等语法）；
- **可写的临时目录**：Playwright 启动浏览器驱动需要 `TEMP`/`TMP`（Windows 上默认 `%LOCALAPPDATA%\Temp`）。如果 `TEMP` 指向一个不存在或不可写的目录，会报 `No usable temporary directory found`；
- **Windows 为主**：示例命令是 Windows 路径，Python 代码本身跨平台，但未在 macOS/Linux 上实测；
- 需要一个**已登录**且带 `--remote-debugging-port` 的 Chrome/Edge。

**已知限制（不要指望它开箱即用）**

1. **慕课那套脚本仍是"流水线式"**：`mooc_video_walk.py` 等按顺序执行、没有 `--dry-run`，适合"照着 README 一步步跑"，不适合当库调用；
2. **`mooc_suip.py` 需要手动传 `--cids`**（随堂测验条目的 cid），没有做自动发现；
3. **超星的字体解码依赖参考字体版本**：字体换了要重新对照，解码结果建议人工复核；
4. **平台改版即失效**：选择器是按 2026 年 11 月的页面写的，平台前端一改就要跟着改；
5. **没有单元测试**：所以"能跑"是我在真实课程上验证的，不是 CI 保证的；
6. **接口/页面文案是中文**，非中文环境需要自己改选择器。

如果你要拿它当项目依赖，建议先按 `docs/setup.md` 跑一遍超星的 `discover → decode`，确认能拿到题目再往下走。

## 设计要点（一句话版）

- **一切 JS 求值都要带超时**：`page.evaluate()` 没有超时，遇到导航或空壳 iframe 会无限挂起；`pjs.ev()` 用 `wait_for_function(polling=100)` 实现带超时的求值。
- **后台运行要同时满足三件事**：窗口在屏幕外、`--disable-*-throttling`、JS 轮询不用 `requestAnimationFrame`。
- **提交前必须逐题校验勾选状态**，否则会交白卷（平台不会提示）。
- **答案库**：把「批阅结果里满分的题」存下来，下一轮直接复用。

细节见 `docs/pitfalls.md`。

## 安全与合规

- 数据全部留在本地，无服务端（见 [SECURITY.md](SECURITY.md)）；
- `config.yaml` / `cookies.txt` / `answers.json` / `out/` 已被 `.gitignore` 排除，**不要提交**；
- 只操作你自己的账号与课程；不要用于代刷、代考、绕过监考；
- 完整条款见 [DISCLAIMER.md](DISCLAIMER.md)。

## License

MIT
