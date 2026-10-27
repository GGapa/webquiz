# webquiz

本地运行的学习通/超星（`mooc1.chaoxing.com`）章节测验与作业辅助工具。
用你自己已登录的浏览器 Cookie，在你自己电脑上跑；不上传任何数据。

> **先读 [DISCLAIMER.md](DISCLAIMER.md)。** 仅限本人账号、课程测验/作业，不要用于考试。
> 超星用户协议可能禁止自动化，账号有被风控的风险，责任自负。

## 它能做什么

- 列出课程里哪些小节带测验，以及完成状态/分数；
- 解密超星的 `font-cxsecret` 字体反爬，把题干和选项还原成正常中文；
- 按选项原文匹配（选项顺序会打乱），自动勾选并提交；
- 支持两种课程结构：左侧目录里的独立“章节测试”，以及嵌在每个小节视频后的测验；
- 支持 `mooc2/work/dowork` 的一次性作业（提交前会要求确认）。

**不做**：视频观看时长、考试、代刷、云端代挂。

## 快速开始（Windows，给不想碰命令行的同学）

1. 安装 Python 3.10+（勾选 Add to PATH）。
2. 下载/克隆本仓库，双击 `start.bat`。
3. 第一次会生成 `config.yaml` 并打开记事本：
   - `course.main_url`：浏览器里打开课程后地址栏的 `studentstudy?...` 整段 URL；
   - `course.cookie_file`：把浏览器里复制的 Cookie 存成 `cookies.txt`（格式见下）。
4. 再双击 `start.bat`，它会下载参考字体并列出所有小节/测验。

> `playwright install chromium` **不要跑**——本工具直接用系统已安装的 Chrome。

## 手动安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python scripts/fetch_reference_font.py
copy config.example.yaml config.yaml
```

## Cookie 格式

`cookies.txt` 支持两种：

```
# 1) 浏览器开发者工具里复制的整段 Cookie 请求头
fid=xxx; _uid=xxx; UID=xxx; ...
```

```json
[
  {"name": "fid", "value": "xxx", "domain": ".chaoxing.com"},
  {"name": "UID", "value": "xxx", "domain": ".chaoxing.com"}
]
```

Cookie 等同账号密码，**不要发给别人、不要提交到 git**。

## 命令

```bash
# 1. 发现：逐个点开小节，记录是否有测验、状态、分数，并保存 HTML
python -m webquiz discover -c config.yaml

# 只检查某几个章节
python -m webquiz discover -c config.yaml --only <chapterId1> <chapterId2>

# 2. 解码：把 out/html/*.html 还原成 out/questions/*.questions.json
python -m webquiz decode -c config.yaml

# 3. 填写：默认 dry-run，只点选不提交
python -m webquiz submit -c config.yaml \
  --tag 02_<chapterId> --answers answers.json

# 确认无误后提交
python -m webquiz submit -c config.yaml \
  --tag 02_<chapterId> --answers answers.json --confirm

# 已提交且页面有 Redo 时
python -m webquiz submit -c config.yaml \
  --tag 02_<chapterId> --answers answers.json --retake --confirm

# 一次性作业（mooc2/work/dowork）
python -m webquiz homework -c config.yaml \
  --url "https://mooc1.chaoxing.com/mooc-ans/mooc2/work/dowork?..." \
  --answers answers.json --confirm
```

输出目录：

```
out/
  discover.json              # 每个小节：chapterId / 是否有测验 / 状态 / 分数
  html/02_<chapterId>.html    # 页面快照，可离线解码
  questions/02_...questions.json
  questions/02_...map.json   # 字体码位 -> 真实字符
  result_<chapterId>.txt
```

## 答案格式

```json
{
  "answers": {
    "1": ["C"],
    "8": ["A", "B", "D"],
    "21": ["A"]
  }
}
```

- 字母是**页面显示顺序**的 A/B/C，不是隐藏 `data` 里的规范字母。
- 提交时按选项原文匹配，所以选项乱序不影响。
- 判断题通常 `A=True`、`B=False`。

## 工作原理（简述）

页面把中文渲染成一个每次加载都重新排列的 `font-cxsecret` 子集字体：
HTML 里的字符是无关汉字，字形才是真题。工具会：

1. 从当前页面 base64 提取 TTF；
2. 把每个码位渲染成 48×48 灰度图；
3. 与 Source Han Sans 的 3 万字符模板做余弦匹配；
4. 得到 `码位 -> 真字` 映射后解析题目；
5. 用页面上的 `addChoice`/`addMultipleChoice` 勾选，再用 `toadd()+form1submit()`
   或 `submitValidate()` 提交。

详细坑位见 `webquiz/` 源码注释，以及仓库根目录的 `NOTES.md`（开发笔记）。

## 已知限制

- 需要自己提供有效 Cookie；过期会跳到登录页。
- 页面结构可能随超星改版变化，选择器需要更新。
- 视频小节通常没有字幕/文字稿，课程特有事实（培养方案、院史、队史）只能靠外部资料。
- 没有 Redo 链接的测验/作业是一次性的，提交后本地无法修改。
- 不内置答案库：`answers.json` 需要你自己准备或由其他工具生成。

## 开发

```bash
python -m unittest discover -s tests -v
```

目录：

```
webquiz/
  fontdecode.py   # 字体反混淆
  parse.py        # HTML -> questions
  textmatch.py    # 选项文本匹配
  browser.py      # Playwright / cookie
  discover.py     # 课程目录扫描
  fill.py         # 勾选与提交
  cli.py          # 命令行
```

## License

MIT。参考字体 Source Han Sans 采用 SIL OFL，不随仓库分发，由脚本下载。
