# 使用前准备：你需要提供哪些数据、按什么流程操作

本文档只讲一件事：**要用这套脚本，你得准备什么、每一步怎么做、怎么确认它真的生效了。**

---

## 一、你需要提供的数据（共 4 类，全部留在你自己电脑上）

| # | 数据 | 必填 | 从哪里拿 | 存到哪 |
|---|---|---|---|---|
| 1 | **浏览器调试端口** | 是 | 启动浏览器时自己指定（默认 `9222`） | `config.yaml` → `browser.cdp_url` |
| 2 | **课程页面 URL** | 是 | 在浏览器里打开课程，复制地址栏 | `config.yaml` → `course.main_url`（超星）/ `icourse163.courses`（慕课） |
| 3 | **登录 Cookie** | 超星必填 | 浏览器开发者工具 → Network → 任一请求 → Request Headers 里的 `Cookie` | 同目录 `cookies.txt` |
| 4 | **大模型 API Key** | 可选 | 自己申请（默认 DeepSeek） | 环境变量 `DEEPSEEK_API_KEY` |

### 1. 浏览器调试端口

用带 `--remote-debugging-port=9222` 启动 Chrome/Edge（见 README 的启动命令）。
脚本靠这个端口接管浏览器，**不需要你的账号密码**。

### 2. 课程页面 URL

- **超星学习通**：打开课程任意一节，地址栏形如
  `https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=...&courseId=...&clazzid=...&cpi=...&enc=...`
  **整段原样复制**（`&`、`=`、`enc` 都不能丢），`chapterId` 随便哪一节都行。
- **中国大学MOOC**：打开课程的「课件」页，地址形如
  `https://www.icourse163.org/learn/XXX-1234567#/learn/content`
  （SPOC 是 `/spoc/learn/...`）。注意**不是**课程首页 `/course/...`。

### 3. 登录 Cookie（超星）

两种格式任选其一，存成 `cookies.txt`：

```
# 格式 A：整段 Cookie 头
fid=xxx; _uid=xxx; UID=xxx; ...
```

```json
[
  {"name": "fid", "value": "xxx", "domain": ".chaoxing.com"},
  {"name": "_uid", "value": "xxx", "domain": ".chaoxing.com"}
]
```

获取方式：登录后按 F12 → Network → 随便点一个请求 → Request Headers → 复制 `Cookie:` 后面整段。

> 慕课（icourse163）不需要提供 Cookie：脚本直接接管你已登录的浏览器。

### 4. 大模型 API Key（可选）

不提供也能用：脚本会生成答题纸，你自己填答案（`answers.json`）。
提供则可以让它自动作答（理解题、多选、判断），但**准确率取决于题目领域**，务必人工复核。

---

## 二、操作流程

### 0. 一次性准备

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml     # 然后按上面填 4 类数据
python scripts/fetch_reference_font.py   # 只有超星字体解码需要（约 16MB）
```

### 1. 启动并登录浏览器

```bat
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
  --remote-debugging-port=9222 --user-data-dir=C:\edge-debug ^
  --disable-background-timer-throttling --disable-backgrounding-occluded-windows ^
  --disable-renderer-backgrounding --mute-audio ^
  --window-position=-3200,-3200 --window-size=1280,800
```

在弹出的窗口里**正常登录两个平台**，然后确认端口可用：

```bash
curl http://127.0.0.1:9222/json/version
# 返回 JSON（含 "Browser": "..."）即成功
```

### 2A. 超星学习通流程

```bash
# ① 发现：遍历课程，列出章节/小节/测验，页面存到 out/html
python -m webquiz discover -c config.yaml

#   ✅ 验证：out/html 里出现多个 .html 文件，日志里能看到"找到 N 个测验"

# ② 解码：把字体混淆的题目还原成正常文字
python -m webquiz decode -c config.yaml

#   ✅ 验证：out/questions/*.json 里题干是正常中文（不是「嘍嗁喿」这种）

# ③ 作答：生成答题纸，填进 answers.json（或接大模型自动答）
python -m webquiz solve -c config.yaml

# ④ 填涂并提交（先不加 --confirm 试跑，看日志再真交）
python -m webquiz submit -c config.yaml --answers answers.json
python -m webquiz submit -c config.yaml --answers answers.json --confirm

#   ✅ 验证：日志里"已勾选 30/30"；提交后页面出现「本次得分」

# ⑤ 作业（如「作业」是 mooc2/work/dowork 类型）
python -m webquiz homework -c config.yaml --url "<作业页 URL>"
```

### 2B. 中国大学MOOC 流程

```bash
# ① 生成课程清单（每个文档/视频/讨论/测验一条，带 learned 状态）
python scripts/mooc_refresh_plan.py
#   ✅ 验证：out/mooc_plan.json，日志显示「XX课程: N items left」

# ② 刷视频（2 倍速，自动跳过已完成的）
python scripts/mooc_video_walk.py
#   ✅ 验证：out/mooc_video_run.log 出现「-> learned=True」

# ③ 文档打卡（打开停留约 20 秒即计入）
python scripts/mooc_text_walk.py --no-disc

# ④ 讨论发帖（--no-disc 的反面；有每日上限，失败会重试）
python scripts/mooc_text_walk.py
#   ✅ 验证：日志「回复数 471->472 见到正文=True」

# ⑤ 单元测验：先枚举 id，再逐个做
python scripts/mooc_quiz_list.py
python scripts/mooc_quiz_do.py 第1章 "https://www.icourse163.org/learn/XXX-123#/learn/quiz?id=456"
#   ✅ 验证：日志「score: 28.00/30.00」

# ⑥ 作业：答案放 JSON（文本 + 可选附件）
python scripts/mooc_hw_fill.py --url "<作业页>" --answer-file answers.json --submit
#   ✅ 验证：上传附件后答题区出现缩略图；页面显示「已完成并提交」
```

### 3. 收尾检查

```bash
# 慕课总览：三门课的视频/文档/讨论/测验完成度
python scripts/mooc_refresh_plan.py     # 看每门课还剩几条
```

---

## 三、提交类操作的安全习惯（务必遵守）

1. **先 dry-run**：`submit` 不加 `--confirm`、`mooc_hw_fill` 不加 `--submit`，先看日志填得对不对。
2. **提交前看勾选数**：日志必须是「已勾选 N/N」，少一道都别提交（平台不会提示你交白卷）。
3. **提交前确认计分规则**：多数章节测验是「多次作答取最高分」，重考不会变低；但也有课是「取最后一次」，做之前先看清楚。
4. **附件要二次确认**：上传后回读答题区，确认出现文件名/缩略图，否则等于没交。
5. **别碰他人数据**：只用你自己的账号、你自己的课程。
