# 大台北 YouBike 一小時車輛預測

[繁體中文](README.zh-TW.md) | [English](README.md)

本專案是一套端到端機器學習系統，預測台北市與新北市每個 YouBike 站點一小時後的可借車數。

> 狀態：正式 120 小時收集與 untouched final evaluation 已完成。CatBoost 通過預先定義的 regression gate，公開 App 已提供版本化 R2 逐站預測快照。

## 正式網站

- 產品 App：<https://greater-taipei-youbike-app.singyu-bravetalk.workers.dev>
- 英文技術文件：<https://greater-taipei-youbike-docs.singyu-bravetalk.workers.dev>
- 繁中技術文件：<https://greater-taipei-youbike-docs.singyu-bravetalk.workers.dev/zh-Hant/>

公開產品使用同源 Cloudflare Edge API 讀取雙北目前庫存、正式逐站預測、metrics、drivers 與天氣 what-if。它會顯示 forecast origin，絕不以目前庫存冒充預測。

## 系統目標

- 保留有 timestamp 的不可變 raw API responses。
- 由 raw snapshots 可重現地建立有文件資料集。
- 以無洩漏 rolling validation 比較多個 baselines 與模型家族。
- 解釋全域與站點級預測 drivers，包含天氣 what-if。
- 提供響應式公開 dashboard 與版本化 prediction API。

## 架構摘要

Production design 將收集與使用者應用分離。Scheduler 寫入不可變 source snapshots；決定性 jobs 重建 Parquet 資料集與無洩漏 features；多個模型在向前時間窗競賽；離線 publisher 把勝出 artifact 的逐站預測寫入 R2；React 與同源 Worker API 顯示地圖、雙語捷運篩選、不確定性、drivers 與 scenarios。FastAPI 保留為原生 Python reference runtime。

Cloudflare Worker collector 使用五分鐘 Cron 與 Standard-class R2 完成正式證據窗，並由固定停止時間、1 MB object cap、10,000 writes、8 GB project stop 與 80% warning 控制用量。CatBoost 已通過 final MAE gate；公開 App 讀取版本化 R2 forecast snapshot，絕不用 demo prediction 取代真實模型。

## 本地開發

建議 Python 3.12 與 Node.js 20+。

```bash
cp .env.example .env
make install
make test
make collect
```

在不同 terminal 啟動：

```bash
make api
make frontend
```

開啟 `http://localhost:5173`，API 文件位於 `http://localhost:8000/docs`。

啟動中英雙語文件網站：

```bash
make docs-install
make docs
```

開啟 `http://localhost:3000`。網站提供左側分類導覽、本地全文搜尋、明暗主題、響應式版型與英文／繁中切換。`make docs-build` 會將 production build 寫入 `docs-site/build`。

React 產品與文件站具有雙向入口。本地預設網址為 `http://localhost:5173` 與 `http://localhost:3000`；部署 build 分別用文件站的 `PRODUCT_APP_URL` 與產品前端的 `VITE_DOCS_URL` 指向正式網址。

雲端收集未啟用時，可在電腦持續唤醒與連線時執行 `make collect-scheduled`；日誌位於 `data/logs/collector.jsonl`。

正式資料集或模型執行前，先同步私有 R2 證據：

```bash
make sync-r2
make dataset
make features
make train
```

R2 憑證只保留在 `.env`，絕不 commit。五日門檻前的 preview 只能用於診斷，serving layer 不會發佈。

## 資料與洩漏原則

Raw layer 原樣保留 source responses。Object keys 依 source、UTC date 與 UTC hour 分區，檔名含 fetch timestamp 與 content checksum。Normalization 保留來源、update time、capacity、available bikes/docks 與新北一般／電動車數。

- 樣本依完整 timestamps 切分，絕不隨機分列。
- Training 至少在 validation 前 60 分鐘結束。
- 最後 24 小時在 model selection 前已完全 hold out。
- `t + 60 minutes` 天氣只使用不晚於 `t` 發布的預報。
- Hyperparameter selection 只使用 expanding-window folds；final test 只評估一次。

## 技術文件

可從 `docs-site` 以分類、搜尋與中英切換瀏覽，或直接查看 [docs](docs/) 內的英文 Markdown。繁中對應文件位於 `docs-site/i18n/zh-Hant/docusaurus-plugin-content-docs/current/`。

- [專案完整導讀：從問題、資料、模型到產品](docs-site/i18n/zh-Hant/docusaurus-plugin-content-docs/current/PROJECT_GUIDE.md)
- [產品設計系統](design.md)

## 已驗證品質門檻

```bash
ruff check src tests
pytest
cd frontend && npm run lint && npm run build && npm audit
cd infra/cloudflare-collector && npm run typecheck && npm audit
cd docs-site && npm run typecheck && npm run build && npm audit
```

測試包含完整合成七模型競賽、三個 purged expanding-window folds 與最終 24 小時 holdout。真實 metrics 只在所需歷史門檻通過後發佈。
