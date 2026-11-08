# OPENING RADAR · 七平台未开票演出监测网页

一个可直接部署到 GitHub Pages 的静态响应式网页，附每日数据更新脚本与 GitHub Actions 工作流。

## 包含的功能

- 仅列出首次预售/公开发售**未来才开始**且有官方可验证来源的演出。
- 首次开票时间在**未来90天**内，演出时间不必在90天内（避免错过早期开票）。
- 按平台、艺人关键词筛选；支持开票时间/演出日期排序、CSV 导出。
- 每场提供官方页面、X 与小红书搜索入口；**不捏造社媒互动数字**。
- 另列 Google News RSS 发现的候选线索（不进入正式榜单）。
- 官方 API 自动接入 Ticketmaster AU；其他六个平台需人工核实或额外获得合法数据接口。

## 五步部署（无需服务器）

1. 创建一个 GitHub 仓库，上传这个 ZIP 解压后的**所有文件**，确保 `.github/workflows/daily.yml` 一并上传。
2. GitHub 仓库 **Settings → Pages → Build and deployment → Deploy from a branch → main → / (root)** → Save。
3. 在 [Ticketmaster Developer](https://developer.ticketmaster.com/) 申请 Discovery API Key。
4. 仓库 **Settings → Secrets and variables → Actions → New repository secret**，名称填 `TICKETMASTER_API_KEY`，值填你自己的 API Key。
5. **Actions → Daily concert onsale refresh → Run workflow** 手动运行第一次；之后会每日大约新加坡时间 09:15 触发，GitHub 可能延迟。

访问地址通常是 `https://你的GitHub用户名.github.io/仓库名/`。

> GitHub Actions 任务要能 push 到 main：Settings → Actions → General → Workflow permissions → Read and write permissions。若分支受保护，需要改用 PR 工作流。

## 如何录入其他六个平台

编辑 `data/verified_events.json`：

```json
[
  {
    "id": "sample-unique-id",
    "platform": "Cityline",
    "artist": "示例艺人（请替换）",
    "title": "示例演唱会（请替换）",
    "country": "Hong Kong",
    "timezone": "Asia/Hong_Kong",
    "first_sale_utc": "2027-01-03T02:00:00Z",
    "event_date_utc": "2027-05-18T12:00:00Z",
    "official_url": "https://www.cityline.com/",
    "verified": true,
    "verification": "官方公告，已核查全部会员/公开预售",
    "verified_at": "2027-01-01",
    "social_score": null
  }
]
```

上面只是**格式示例，不是真实项目**。仅在验证首场预售尚未发生后才设 `verified: true`；所有时间必须 ISO UTC 带 Z，并填实际当地时区。

**重要**：录入的人工核实记录，`verified_at` 超过7天会自动退出正式列表，必须重新核实后更新日期。Ticketmaster API 不保证记录所有私密预售：因此 API 上尚未开票也只能代表“按 API 可见信息尚未开票”，需自行复核艺人会员公告。

## 更新数据的限制

- **Ticketmaster SG**：Discovery API 未保证覆盖，不能假设 AU API 会包含新加坡。
- **ThaiTicketMajor、HK Ticketing、Cityline、NOL、Melon**：暂无稳定已授权售票数据接入，本项目仅抓公开新闻搜索线索并要求官方确认，不做登录、验证码绕过或高频爬取。
- **X / 小红书**：仅提供检索入口，不自动采集点赞/转发、不能计算真实跨平台热度分数。可在后续添加授权 API 或合规数据供应商。
- GitHub Pages 是静态站点；Actions 定时任务可能延迟，数据不实时，不能保证每天各平台均有新公告。
- `generated_at` 是数据脚本执行时间，不等于各平台全部项目经过当天人工核实。

本地预览：在本项目目录执行 `python -m http.server 8000`，浏览器打开 `http://localhost:8000/`。
