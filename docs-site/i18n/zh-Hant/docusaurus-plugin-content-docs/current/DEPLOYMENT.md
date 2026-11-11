# 部署手冊

## 1. 目標拓撲

- Cloudflare Worker Cron：每五分鐘排程收集。
- Cloudflare R2：不可變壓縮 raw objects 與 run manifests。
- Google Cloud Run：容器化 FastAPI 與 Python 模型 runtime。
- Vercel 或 Cloudflare Pages：React production build。
- GitHub Actions：每次 push 執行測試與建置。

## 2. Secret 政策

絕不 commit 憑證。本地 secrets 只能在 `.env`，production credentials 只能在平台加密 secret store。`.env.example` 只記錄名稱與安全預設值。

## 3. Cloudflare collector

本地開發時不強制使用雲端收集。macOS 可由 `infra/launchd/com.singyu.youbike-collector.plist` 保持 scheduler 跨 terminal session 執行；如 repository 搬移，必須更新絕對路徑。使用 `make collector-status` 檢查，並在 `data/logs/collector.jsonl` 查看來源結果。

Smoke test 時不得啟動官方時鐘。功能驗收後，在 `.env` 將 `COLLECTION_START_AT` 設為含明確 offset 的 ISO 8601 時間，安裝／重載 LaunchAgent，並確認 `/api/v1/data/quality` 由同一官方時間的零開始。

雲端部署前置：Cloudflare 帳號、Wrangler 驗證、R2 bucket。

```bash
cd infra/cloudflare-collector
cp wrangler.toml.example wrangler.toml
npx wrangler login
npx wrangler r2 bucket create greater-taipei-youbike-raw
npx wrangler secret put COLLECT_TOKEN
npm run typecheck
npm run deploy
```

部署後：

1. 驗證 `/health`。
2. 用 bearer token 觸發一次手動收集，或等待 Cron；未設 `COLLECT_TOKEN` 時手動 route 停用。
3. 確認 R2 中三個 source objects 與一個 manifest。
4. 確認下一次 Cron 產生新 timestamped objects。
5. 設定 Worker failure notifications。

可重現訓練需另建一組只限 `greater-taipei-youbike-raw` 的 R2 S3 Object Read token。Endpoint、access key ID、secret access key 與 bucket 只能寫入本地 `.env`，然後執行 `make sync-r2`。不可重用 Wrangler OAuth token，也不可給 training pipeline 寫入權限。

## 4. Backend

```bash
docker build --build-arg GIT_COMMIT="$(git rev-parse HEAD)" -t greater-taipei-youbike-api .
docker run --rm -p 8080:8080 --env-file .env greater-taipei-youbike-api
```

Cloud Run 上將 R2 values 放入 secrets，並在 build 時附上版本化 model artifact，或啟動時下載。Minimum instances 設為零以維持免費額度，並接受閒置後 demo 的 cold start。

## 5. Frontend

將 `VITE_API_BASE_URL` 設為 Cloud Run HTTPS URL：

```bash
cd frontend
npm ci
npm run build
```

部署 `frontend/dist`，並在 production release 前將公開前端 origin 加入 backend `ALLOWED_ORIGINS`。

## 6. 文件網站

目前正式網址：

- [產品 App](https://greater-taipei-youbike-app.singyu-bravetalk.workers.dev)
- [英文技術文件](https://greater-taipei-youbike-docs.singyu-bravetalk.workers.dev)
- [繁中技術文件](https://greater-taipei-youbike-docs.singyu-bravetalk.workers.dev/zh-Hant/)

中英雙語 Docusaurus 網站位於 `docs-site`。英文位於 `/`，繁中位於 `/zh-Hant/`，共用文件 routes 位於 `/docs`。Production command 為 `npm ci && npm run build`，靜態輸出為 `docs-site/build`。Cloudflare Pages 或 Vercel 無需 server 或 runtime secret 即可部署：root directory 設 `docs-site`、build command 設 `npm run build`、output directory 設 `build`。文件站 build 時將 `PRODUCT_APP_URL` 設為已部署的 React App 網址；React build environment 將 `VITE_DOCS_URL` 設為文件站網址。這兩個公開設定建立「產品 ↔ 文件」雙向連結，並非憑證。

公開產品使用 `infra/app-worker/wrangler.toml` 部署為 Cloudflare Worker with Static Assets。同源 Edge API 在資料收集期間提供即時站點；validated model artifact 尚未產生前，正式預測、metrics、drivers 與 what-if endpoints 維持不可用。

本機 Wrangler 完成登入後，可重現發布：

```bash
make deploy-product
make deploy-docs
```

## 7. Rollback

- Frontend：重新部署前一個不可變 build。
- Backend：Cloud Run traffic 切回前一 revision。
- Model：改變 backend 引用的 model object version 並重啟。
- Collector：部署前一個 Worker version。Rollback 永遠不刪 raw data。

## 8. 成本防線

- 啟用 Cloud Run 前設定 Cloud Billing budget alerts，minimum instances 保持為零。
- Raw data 壓縮儲存，retention 需求滿足後才設 R2 lifecycle。
- Weather 不每五分鐘 polling，每小時保留一個 issue-time forecast。
- Worker 必須有 `COLLECTION_END_AT`，到點後在任何 fetch/R2 write 前停止。
- `MAX_OBJECT_BYTES` 在儲存前拒絕異常大 payload，程式上限 1 MB。
- 每次 run 前，`control/cost-guard.json` 保守預留六次寫入與 4 MB；達 10,000 writes 或 8 GB 前就停止，80% 時警告。
- 公開 health route 不執行 R2 operation，外部流量無法消耗 Class B reads。
- 五分鐘 Cron 的五日窗口少於 1,500 invocations 與 6,000 Class A writes，低於 R2 每月免費一百萬次。
- Cloudflare budget notifications 是警示，不是保證扣款截止。專案 deadline 與 payload cap 才是可執行的截止；下載證據後移除 Cron。
