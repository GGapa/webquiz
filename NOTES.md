# 开发笔记 / 踩坑记录

这些是维护选择器、修 bug 时最容易再踩的坑。

## 字体反混淆

- `font-cxsecret` 是**每页重新随机**的 TrueType 子集。不要缓存“码位→字”的
  映射跨页复用；只能在提交前对 `frame.content()` 现场建映射。
- PIL 的 `Image.getbbox()` 在白底图片上返回整张画布，不是字形 bbox。
  必须用 `np.where(arr < 200)` 自己算 ink bbox，否则所有字形都从同一偏移开始，
  匹配分数会普遍掉到 0.5 左右。
- `ImageFont.truetype(BytesIO)` 会推进文件指针；循环渲染同一字体时每次要给新的
  `BytesIO` 或 `seek(0)`，否则只有第一个字能渲染。
- 参考字体用 SourceHanSansSC-Normal（OFL），与超星子集同源时 top-1 分数约 0.96；
  低于 0.85 通常说明页面换了字重/字体，需要换参考字体。

## 选项与匹配

- 选项乱序时，`span.num_option[data]` 是服务端规范字母，显示的文字是位置字母。
  **永远按选项原文匹配**，不要按 `data` 或位置答题。
- 匹配必须 exact-first：
  `软件工程` 是 `软件工程专业导论` 的子串；先子串匹配会点错，多选题里还会把
  已选项 toggle 掉。
- 归一化时只去掉“字母 + 空白”形式的标签。`B+`、`A+` 这类选项不能把 B/A 削掉，
  否则整题所有选项都变成 `+`。
- 兼容汉字/康熙部首（`⺠→民`、`⻛→风`）要归一化；字体映射漏掉的字形会显示成
  `▀`，比较时直接删掉并允许 difflib ratio ≥ 0.8。

## 提交

- `doHomeWorkNew`：`toadd(['',''])` 会写 `#enc` 和 `#answerwqbid`，然后
  `form1submit()` 直接 AJAX 提交。确认弹窗（`#confirmSubWin`）经常不出现，
  不要依赖它。
- `mooc2/work/dowork`：`a.completeBtn` → `#workpop` → `#popok`；
  `submitValidate()` 先请求 `/work/validate`。
- 提交后结果页可能一直显示 Submit 按钮，这是正常模板行为；以页面文字里的
  `This time N score` / `Final score N score` 为准。
- 结果页没有 `Redo` 链接 = 只有一次机会，交完改不了。

## 课程结构

- 侧边栏模式：`div.posCatalog_select` 里直接有“章节测试”条目，点开是 work frame。
- 小节内嵌模式：侧边栏只有视频，点每个小节后才会出现 work frame；
  必须每点一个小节都检查 `frame_content` 是否变成 `/work/...`。
- `selectWorkQuestionYiPiYue` = 已交；`doHomeWorkNew` = 可作答。
- 视频没有字幕时 `/richvideo/allsubtitle` 常返回 `[]`，`knowledge/cards` 只有
  “观看时长需 ≥ 90%”，课程特有事实只能外部查。

## 安全

- cookie 等同账号密码；不要日志打印、不要提交、不要上传服务器。
- `.gitignore` 已排除 `cookies.txt`、`config.yaml`、`answers*.json`、`out/`、`.cache/`。
