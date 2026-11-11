# 系統架構

## 1. 目的

系統預測台北市與新北市每個 YouBike 站點 60 分鐘後的可借車數。它不是單一 notebook，而是完整資料產品：收集、不可變歷史、可重現處理、無洩漏模型選擇、推論 API、響應式 Web App、監控與技術文件一併版本化。

## 2. 架構決策

| 關切 | 決策 | 理由 |
|---|---|---|
| 收集頻率 | 每五分鐘 | 捕捉短時通勤流動，同時控制 API 與儲存負擔。 |
| 原始歷史 | Cloudflare R2 不可變 gzip JSON | 保留證據、可重播，並符合免費額度。 |
| 本地分析 | DuckDB、Polars 與分區 Parquet | 不需維運資料庫伺服器即可處理數百萬列。 |
| 模型服務 | Google Cloud Run 上的 Python FastAPI | 原生載入 Python 模型、scale-to-zero、有 OpenAPI 合約。 |
| Web App | React、TypeScript、MapLibre | 比 notebook 式 UI 具有更好交互與視覺控制。 |
| 文件網站 | Docusaurus 與雙語本地搜尋 | 版本化英文與繁中說明，可獨立部署為靜態網站。 |
| Web 托管 | Vercel 或 Cloudflare Pages | 靜態資源全球快取，且可獨立部署。 |
| 排程收集 | Cloudflare Worker Cron | 五日收集不依賴筆電持續開機。 |

官方收集期間始於 2026-11-10。Worker Cron 每五分鐘寫入 Standard-class R2；版本化 macOS LaunchAgent 作為臨時獨立備份。Worker 在證據期結束後自動停止，並在請求上游前實施保守的寫入、容量與單物件限制。

R2 也是正式完整率的權威來源。不可變 source objects 與 run manifests 是稽核證據；`control/collection-quality.json` 是可重建的增量索引。筆電日誌僅是診斷備份，電腦休眠不會拉低雲端完整率。

## 3. 執行流程

```text
Taipei live API ----------+
New Taipei paged API -----+--> Cloudflare Worker (every 5 min)
Open-Meteo forecast ------+       | retries, timeouts, validation
                                  v
                         Cloudflare R2 raw history
                                  |
                 deterministic normalization pipeline
                                  v
                   leakage-safe feature generation
                                  |
                   expanding-window model competition
                                  |
                    untouched final 24-hour test
                                  |
                          versioned model bundle
                                  |
                      FastAPI <----> React dashboard
                                         ^     |
                       PRODUCT_APP_URL   |     | VITE_DOCS_URL
                                         |     v
                                Docusaurus documentation
```

## 4. 失敗邊界

台北、新北與天氣請求是獨立作業；單一來源失敗不會刪除其他成功回應。每次排程均寫入所有結果的 manifest。失敗採有界指數退避；新北分頁有安全上限與重複站點檢查。物件名含取得時間與內容 checksum，重試不會靜默覆寫其他歷史。

本地 Python collector 使用臨時檔、`fsync` 與原子改名；雲端 collector 將 gzip 直接串流至 R2，並附上 SHA-256 metadata。

## 5. 安全邊界

- 憑證僅由環境變數或平台 Secret store 提供。
- `.env` 與產生資料集不進 Git。
- 瀏覽器不會取得 R2 憑證。
- 生產 CORS origin 必須明確列出。
- 公開端點除記憶體內 what-if 推論外均唯讀。手動收集路徑需 Worker bearer token；未設定時停用。

## 6. 目前實作狀態

已實作並在本地驗證：

- 台北與完整分頁的新北收集。
- 大台北三個網格點的 Open-Meteo issue-time forecast。
- 本地原子 gzip 儲存與 Cloudflare R2 Worker。
- 來源特定 normalization 到統一 schema。
- 增量 raw-to-Parquet 重建。
- 60 分鐘 purge gap、expanding-window 與 final holdout。
- 七模型競賽、out-of-fold 區間校準、分群評估、SHAP 與 permutation drivers。
- React 地圖 App 與受證據門檻保護的 FastAPI。
- 可搜尋的中英雙語 Docusaurus 文件站，以及產品與文件的雙向導覽。
- Python 測試、靜態檢查、前端 production build 與 Worker typecheck。

待完成證據門檻：

- 五個完整日的官方歷史。
- 真實歷史模型比較指標。
- 真實 SHAP 與天氣 what-if 結果。
- 生產網址與雲端健康檢查。
