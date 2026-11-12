# 實作紀錄

## 2026-11-09

### 已完成

- 對官方端點確認台北即時 schema，並確認新北 schema 與分頁參數。
- 實作互相獨立、有界重試與 timeout 的 asynchronous collectors。
- 實作本地 atomic gzip storage、R2-compatible adapter 與每五分鐘 Cloudflare Worker。
- 保留第一份驗證過的本地 raw snapshot：台北 1,824 站、新北 1,622 站與三個天氣網格。
- 建立可容忍單一來源失敗且寫入 JSONL logs 的本地 scheduler。
- 版本化台北市資料大平台 110 個官方捷運站座標。
- 將首兩個快照重建為 3,446 列 normalized Parquet。
- 加入 checksum object naming、source/date/hour partitions、dataset manifests、source-specific normalization 與 invariant validation。
- 實作 60 分鐘 label alignment、lags 與 rolling features。
- 實作 persistence/trend/previous-hour baselines，以及 Ridge、Random Forest、Extra Trees、Histogram Gradient Boosting、LightGBM、XGBoost、CatBoost。
- 加入最後 24 小時 holdout、三個 12 小時 expanding folds 與 60 分鐘 purge gap。
- 加入 out-of-fold uncertainty calibration、holdout subgroup metrics、permutation importance 與 global/local SHAP。
- 實作受證據門檻保護的 forecast、metrics、drivers、quality 與 weather what-if API。
- 建立 React/TypeScript map application 與 FastAPI service，加入桌面／行動 QA、120 小時 gate 與 scheduler outcomes。
- 清除已知 frontend 依賴警示，確認兩個 Node projects 均為零已報告弱點。
- 通過 Python lint 與 11 tests、frontend lint/build、Worker typecheck 與首次 GitHub Actions。

### 仍等待的證據

- 雲端部署憑證與公開 URL。
- 五個完整日排程 raw objects。
- 首批符合條件的一小時 labels。
- 真實歷史 model metrics、SHAP drivers 與 what-if measurements。
- 公開部署 smoke tests。

本紀錄只描述已觀察到的工作，後續會加入精確指令、測試結果、部署 revision、收集覆蓋與 metrics。

## 2026-11-10

### 已完成

- 加入版本化 macOS LaunchAgent，驗證可啟動、持續執行、寫入成功快照與安全停止。
- 分離開發快照與尚未啟動的五日證據期，加入含時區驗證的 `COLLECTION_START_AT`。
- 強制五日、95% 完整率與 final-holdout MAE 擊敗 persistence 的 serving gates。
- 所有時間與空間 join 改用 `(source, station_id)` 複合 key，並加入 collision regression test。
- React 連接 forecast interval、final metrics、SHAP drivers 與天氣 what-if；模型 ready 時地圖風險與網路統計改用一小時預測。
- 以非特權使用者建置／健康檢查 production container，確認 health HTTP 200 與模型發佈前 HTTP 503。
- 驗證 desktop 與 390px mobile、live map、搜尋、城市篩選、無水平 overflow 與無 console errors。
- 通過 Python lint/15 tests、frontend lint/build、Worker typecheck 與零弱點 npm audits。
- 2026-11-10 15:51:49 Asia/Taipei 啟動正式證據期，驗證首次本地台北 1,824 站與新北 1,622 站。
- 啟用 R2 Standard 免費額度、建立 `greater-taipei-youbike-raw`，並部署五分鐘 Cron Worker `5f39a239-6e3a-42d5-ac3b-0df9682fff6b`。
- 加入 fail-closed Cloudflare cost controls：固定停止時間、1 MB object limit、10,000 writes、8 GB stops 與 80% warning。
- 從公開 health 移除 R2 reads，避免不受信流量消耗 Class B operations。
- 部署 Worker `cfe13c8e-882d-40d5-bf51-ef0902ced73a`，使用由不可變 keys 重建並增量更新的私有 R2 品質狀態。
- 驗證首份 cloud quality report：18.82 小時，台北 215/226、新北 215/226、最低完整率 95.13%，三次完整 tracked runs 且無初始化後失敗。
- 重建 local preview 237,774 station rows、183,492 feature rows、3,399 stations，在 56 timestamps 找到 94,936 eligible labels。
- 確認訓練以 `Not enough time coverage...` fail closed，未發佈臨時模型。
- 復原 `youbike-build-features` CLI，鎖定 Hatchling editable build requirement。
- 建立 bucket-scoped Object Read Only workflow，完成首次同步：795 objects、534 已驗證 source snapshots、約 56 MB，未暴露憑證。
- 分離 `data/cloud_raw` 正式證據與 `data/raw` 筆電備份；將 516 cloud snapshots 重建為 889,068 normalized rows 與 876,684 feature rows，共 3,399 站。
- 重跑 cloud-only trainer；21 小時仍無法形成 purged folds 與 final holdout，因此正確 fail closed。
- 修正 R2 fixed-length upload，驗證 16:50、16:55、17:00、17:05 成功 Cron；17:00 也測到每小時天氣路徑。

### 剩餘證據

- 官方收集達 120 小時且快照完整率至少 95%。
- 建立最終可重現資料集，在真實歷史執行模型選擇。
- 發佈 final holdout metrics、drivers、what-if、production URLs 與最終簡報。

## 2026-11-11

### 已完成

- 依實際五日、多站、直接 60 分鐘預測設計審查模型家族，文件化納入與延後條件。
- 加入 Random Forest、Histogram Gradient Boosting、XGBoost，由四候選擴充為七候選。
- 所有候選保持相同的無洩漏評估，不給任何模型有利切分。
- 將 XGBoost 加入可重現 dependency group，在 Docker 發現 standard package 多餘 NVIDIA NCCL 後，Linux 改用 CPU-only package。
- 成功重建 production image，確認 Linux container 可載入 XGBoost 3.4.1 與七個 candidate factories。
- 通過 Python lint 與全部 20 tests，包含七模型合成競賽、artifact serialization、API inference、prediction intervals 與 weather what-if。
- 重跑 formal trainer，確認正式歷史未達時間覆蓋前會在 fit 候選模型前 fail closed。
- React 產品與同源即時站點 Edge API 已部署至 `https://greater-taipei-youbike-app.singyu-bravetalk.workers.dev`。
- 中英雙語 Docusaurus 文件站已部署至 `https://greater-taipei-youbike-docs.singyu-bravetalk.workers.dev`。
- 已驗證產品、英文文件與繁中文件皆回傳 HTTP 200；smoke test 當下公開 Edge API 回傳 3,446 個 normalized live stations。
- 模型維持 fail-closed 於 `collecting-training-data`；本次部署未發布 preview metrics 或預測。

### 由證據條件延後，並非遺漏

- ARIMA/ARIMAX 需獨立站點級 rolling design 與更多重複季節歷史。
- Global neural sequence 與 graph models 需至少一個月歷史，才能支持額外變異與營運成本。

## 2026-11-12

### 已完成

- 加入事先固定的 72 小時診斷：前 48 小時訓練、60 分鐘 purge、第三天作為所有模型與 baseline 共用的 untouched test。
- 加入 `make early-diagnostic`，可同步 R2、重建正式 dataset/features，並輸出不會發布至 serving API 的 preliminary evaluation。
- 將產品部署時固定的品質快照改為即時讀取 R2 `control/collection-quality.json` 的 sanitized view。
- 驗證無需重新部署即可自動更新：下一次 collector 後，公開 API 由 53.99 增至 54.07 小時，完整 runs 由 425 增至 426。
- 公開 health route 仍不讀 R2；品質 route 加入五分鐘 shared cache。
- 完成四頁英文模型選用簡報草稿與獨立中文白話講稿；模型分數在證據門檻通過前刻意保持空白。
