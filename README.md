# Opening Radar — 纯网页检索版（无需 API Key）

监测七个平台公开网页，关注**未来 90 天内尚未开始第一次预售**的演唱会。部署在 GitHub Pages，通过 GitHub Actions 每天自动尝试扫描。

## 一、部署

1. 创建一个 GitHub 公共仓库 `opening-radar`。
2. 将本压缩包解压后，直接将所有文件和文件夹放在仓库根目录（主页必须是 `index.html`）。
3. Settings → Pages → Deploy from a branch → main → `/ (root)` → Save。
4. Settings → Actions → General → Workflow permissions → `Read and write permissions`。
5. Actions → **Daily public-webpage concert scan** → Run workflow。之后每天约新加坡时间 09:15 自动尝试运行（GitHub 定时可能延迟）。

**无需申请或配置任何 API Key，也不需要安装 Python 第三方依赖。**

## 二、已实现及限制

- `scripts/update.py` 每天用 HTTP 请求读取七个平台公开活动目录的 HTML，提取可能相关的演出链接。
- 网页线索写到 `data/events.json` 的 `candidates`：**并不代表该场未开票**。目录含广告、非演唱会、已售项目，需核实。
- 若网页需要 JavaScript 渲染、登录或触发 403/429，标记抓取失败，不绕过访问控制，也不伪造成功。
- 官方开票信息经过核查后，可以录入 `data/verified_events.json`。仅满足「首次预售时间在未来90天，且验证时间在最近7天内」的活动进入正式榜。
- 首次预售一旦开始，即使普通公开开票还没开始，也会被自动剔除。
- X 与小红书仅提供关键词搜索入口；无法合法稳定获得完整互动数据时，热度排名留空。
- 网站是 GitHub Pages 静态站点，自动抓取运行于 GitHub Actions（而非用户浏览器）。

## 三、手动添加经过核实的未售演出

在 `data/verified_events.json` 写入如下对象数组（日期为示例，**不是实际演出**）：

```json
[
  {
    "id": "example-001",
    "platform": "Ticketmaster SG",
    "artist": "示例艺人",
    "title": "示例演唱会",
    "country": "Singapore",
    "timezone": "Asia/Singapore",
    "first_sale_utc": "2027-01-01T02:00:00Z",
    "event_date_utc": "2027-03-01T12:00:00Z",
    "official_url": "https://ticketmaster.sg/",
    "verified": true,
    "verification": "人工查阅官方公告，确认首次会员预售时间与链接",
    "verified_at": "2026-12-31",
    "social_score": null
  }
]
```

请使用真实官方详情 URL、真实时间和当天日期。填写后运行 GitHub Actions；日期超过7天未经重新复核，系统会把活动从正式榜单撤下。不要仅用“公开开售时间在未来”推断“从未预售”。

## 四、常见故障

- **404**：确认 `index.html` 位于根目录，Pages 分支是 `main` / root。
- **页面显示没有演出**：说明 `events` 中还没有符合严格条件且近期核实的活动；可查看待核实线索。
- **所有平台显示抓取失败**：打开 Actions 日志查看 HTTP 错误，可能是网站防机器人、地域限制或网络问题；不表示无演出。
- **更新后网页看不到新数据**：等待 GitHub Pages 重新部署并强制刷新。
- **使用本地双击 `index.html` 失败**：推荐经 GitHub Pages 打开，或在项目文件夹运行 `python -m http.server 8000` 后访问 `http://localhost:8000`。
