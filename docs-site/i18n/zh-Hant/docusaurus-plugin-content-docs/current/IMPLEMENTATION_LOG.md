# 工程實作紀錄

本頁記錄已完成的系統元件、技術合約、驗證邊界與營運控制，而不是逐日工作流水帳。模型數值請見[五日正式模型結果](./FINAL_RESULTS.md)。

## 執行架構

| 元件 | 技術 | 責任 |
|---|---|---|
| 排程蒐集器 | Cloudflare Worker Cron | 抓取台北、新北分頁資料與 issue-time Open-Meteo |
| 證據儲存 | Cloudflare R2 Standard | 保存不可覆寫的壓縮回應、manifest 與 control objects |
| 可重現管線 | Python、Polars、DuckDB、Parquet | 正規化、檢核、標籤對齊與特徵建立 |
| 模型管線 | scikit-learn、LightGBM、XGBoost、CatBoost | baseline、時間驗證、final evaluation 與解釋 |
| 推論服務 | FastAPI `ForecastService` | 載入正式 artifact 並產生有界預測 |
| 公開 serving | Cloudflare Worker＋R2 snapshot | 提供預測、品質、metrics、drivers 與 what-if |
| 產品 | React、TypeScript、MapLibre | 搜尋、城市導覽、風險地圖、站點詳情與證據 |
| 技術文件 | Docusaurus | 發布英文與繁體中文技術合約 |

## 蒐集與失敗處理

蒐集器每五分鐘執行。台北與新北獨立抓取，單一上游失敗不會丟掉另一個成功來源。請求設有 timeout 與有限次重試；新北分頁另有頁數安全上限。

每次執行保存 source-level manifest，可區分 complete、partial、failed 並留下失敗來源。品質狀態由不可變 R2 objects 重建，不依賴 process-local counter。

原始物件合約：

```text
source={source}/date=YYYY-MM-DD/hour=HH/
YYYYMMDDTHHMMSS.ffffffZ-{sha256-prefix}.json.gz
```

未壓縮 JSON 的 SHA-256 同時寫入 metadata 與檔名。正式處理前會檢查 gzip、metadata checksum、檔名 checksum 與 byte count。

## 成本與安全控制

- 正式蒐集有固定停止條件，物件大小、寫入次數或儲存量超過上限時 fail closed。
- 達硬上限前先寫入 80% warning state。
- 公開 health route 不讀取 R2。
- R2 存取限制指定 bucket，本地 S3 credential 維持 read-only。
- 憑證只由 `.env` 或平台 Secret 載入，不進入 Git。
- 公開 Worker 使用快取並受 Free-plan 限制保護。

## 正規化資料合約

台北與新北欄位統一成 station schema，包含複合識別 `(source, station_id)`、站點資訊、座標、容量、車數、空位、上游更新時間與蒐集時間。

所有時間與空間 join 都使用複合識別，不能只用可能跨縣市碰撞的 `station_id`。正規化會拒絕錯誤座標、負庫存與不一致容量。

Parquet artifacts 可完全由 R2 raw history 重建。開發資料、practice history、筆電備份與正式證據窗使用實體分離目錄。

## Target 與特徵合約

每個時間 `t` 的站點觀測配對同一複合站點在 `t + 60 分鐘` 的目標，只接受 ±7 分鐘內最接近的觀測。沒有合格未來目標的 row 仍可用於推論，但不進入 supervised evaluation。

35 個正式輸入涵蓋：

- 當下車數、空位、容量與車輛比例；
- 5、15、30、60 分鐘 lag、delta、rolling mean 與 variation；
- 小時、星期、週末、週期時間編碼與台灣國定假日；
- 最近 MRT 距離與 station/district/source codes；
- 一公里內最多五個鄰站及其車輛統計；
- issue-time 溫度、體感溫度、濕度、雨量、降雨機率、天氣代碼、風速與陣風。

天氣只使用當時已發布並封存的 forecast；未來站點狀態與事後實際天氣不會進入 prediction-time row。

## 時間驗證合約

正式 trainer 先隔離最後 24 小時作為 untouched holdout。其餘 development window 建立三個 expanding folds，每個 fold 使用 12 小時 validation，前方保留 60 分鐘 purge。

Persistence、recent trend、previous-hour baseline 與七個學習模型共用相同時間切分。依平均 validation MAE、再依 RMSE 選模；選定後才評估 final holdout 一次。

任一條件不成立時，publication 會 fail closed：

1. 正式蒐集至少 120 小時；
2. 最低站點完整率至少 95%；
3. 選定模型在 final-holdout MAE 打敗 persistence。

## 模型 Artifact 合約

| Artifact | 內容 |
|---|---|
| `model.joblib` | fitted pipeline、feature order、category maps、q90 residual band、metadata |
| `evaluation.json` | fold ranking、final/segment metrics、timings、publication decision |
| `drivers.json` | global/local SHAP、permutation importance、解讀限制 |

`ForecastService` 在必要證據缺失時拒絕推論。預測限制在 `[0, capacity]`，並提供 empirical q90 error band。

## 公開 Forecast Snapshot

Python publisher 載入正式 artifact，對每站最新 row 評分，並預先評分 dry／heavy-rain 兩個受控情境，發布到：

```text
control/latest-forecasts.json
```

物件包含 schema version、產生時間、forecast origin、model metadata、站點數、point prediction、bounded interval 與 scenario predictions。相對最大觀測時間超過 15 分鐘的舊站點會被排除。

| 公開 route | 合約 |
|---|---|
| `GET /health` | 不讀取 R2 品質物件的 serving state |
| `GET /api/v1/forecasts/latest` | 已發布的站點預測 snapshot |
| `POST /api/v1/stations/{id}/what-if` | 預先計算的受控天氣回應 |
| `GET /api/v1/model/metrics` | sanitized 正式 evaluation |
| `GET /api/v1/model/drivers` | sanitized explanation report |
| `GET /api/v1/data/quality` | sanitized collection quality |
| `GET /api/v1/stations/live` | normalized 官方即時資料 fallback |

UI 永遠顯示 forecast origin，不把儲存的預測冒充成較新的 live prediction。

## 產品導覽

React client 內含與 feature engineering 同一份版本化官方捷運座標。使用者可先選五條台北捷運線之一，再用「中文站名（English Name）」選站。選線時，地圖會 fit 整條路線並保留各站 700 公尺內的 YouBike；選站後移到該座標，列出一公里內最近六站的目前可借數與 +60 分鐘預測。主搜尋框同時支援中英文捷運站名。Forecast publisher 也會加入官方 YouBike `snaen` 與 `sareaen`，所以站名、行政區與搜尋都能支援中英文，不使用自行翻譯的名稱。

## 驗證與發布門檻

Repository 驗證 source normalization、上游失敗 mapping、複合 identity、跨城市 collision、時間順序、purge gap、label tolerance、issue-time weather join、七模型 artifact、推論、區間、what-if 與 ready/not-ready API contract。

Release checks 包含 Python Ruff/Pytest、React ESLint/TypeScript/build、中英文 Docusaurus typecheck/build、Worker bundle/HTTP smoke tests，以及 desktop／375px mobile 的地圖、雙語捷運搜尋、路線／站點導覽、station panel、console 與 overflow QA。

## 已知工程限制

- 五日資料沒有重複的每週與季節情境。
- 目前最佳化車數誤差；空站／滿站 recall 仍需獨立 objective。
- 公開預測使用版本化 R2 batch snapshot，不在免費 Worker isolate 內直接跑 CatBoost。
- 活動資料延後到取得可靠、可地理定位的活動歷史後再加入。
- 自動刷新仍需連接有上限的 Python scheduler；serving contract 已與排程平台解耦。

## 下一個 Production Increment

1. 每小時執行 publisher，並拒絕超過 freshness SLO 的 snapshot。
2. 建立獨立 empty/full classifier，在 development folds 調整 threshold。
3. 歷史週期足夠後加入 previous-day 與 previous-week baselines。
4. 監控 snapshot age、feature drift、prediction drift 與 segment error。
5. 滿一個月後讓 global sequence 或 graph model 在相同 untouched holdout 下競賽。
