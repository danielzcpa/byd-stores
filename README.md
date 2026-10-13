# BYD 澳洲门店监控

静态网页（Leaflet + OpenStreetMap 底图，可叠加邮编区域边界）+ 定时抓取。数据来自 BYD 官网 Find Us 页面内嵌的门店数组，只保留销售点（Experience Centre 类）。

## 目录
- `scrape_byd.py` — 抓取脚本，写出 `docs/data/locations.json`，并把与上次快照的差异（新增 / 关闭 / 改名）追加到 `docs/data/history.json`
- `docs/` — 网站根目录（GitHub Pages 发布目录）；`docs/data/poa.json` 为 ABS 2021 邮编区域（POA）边界，已简化至约 3.9 MB（gzip 后 0.8 MB），网页按需加载
- `.github/workflows/refresh.yml` — 每 30 分钟自动抓取并提交；提交后 GitHub Pages 自动重新发布

## 部署（约 5 分钟）
1. 在 GitHub 新建一个仓库（建议 Private 或 Public 均可；Public 仓库的 Pages 免费，Private 仓库需 Pro）。
2. 把本目录全部文件推送到仓库的 `main` 分支。
3. 仓库 Settings → Pages → Build and deployment：Source 选 **Deploy from a branch**，Branch 选 **main**，目录选 **/docs**，保存。
4. 仓库 Settings → Actions → General → Workflow permissions：选 **Read and write permissions**，保存。
5. Actions 页面打开 "Refresh BYD store data"，点 **Run workflow** 跑一次确认正常。
6. 1–2 分钟后访问 `https://<你的用户名>.github.io/<仓库名>/`。

## 自定义域名（可选）
Settings → Pages → Custom domain 填写你自己的域名（例如 `stores.yourdomain.com`），并在域名 DNS 加一条 CNAME 指向 `<你的用户名>.github.io`。

## 调整抓取频率
修改 `.github/workflows/refresh.yml` 中的 cron。GitHub 定时任务最短间隔为 5 分钟，但官网门店名单变动频率低，当前为 30 分钟。

## 本地运行
```bash
python3 scrape_byd.py --out docs/data
```
