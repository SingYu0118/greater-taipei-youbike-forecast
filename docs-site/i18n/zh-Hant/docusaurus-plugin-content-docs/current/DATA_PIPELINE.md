# 資料管線

## 1. 資料來源

### 台北 YouBike

- 格式：單一 JSON array，含所有站點即時狀態。
- 欄位：站點 ID、中英文名稱、行政區、地址、座標、容量、可借車、可還車柱、營運旗標與多個來源時間。
- 收集：每五分鐘一次。

### 新北 YouBike

- 格式：使用 `page` 與 `size` 的分頁 JSON arrays。
- 重要差異：多數數值是字串，且分開提供一般與電動輔助車數。
- 收集：持續請求至該頁少於設定 page size，並檢查跨頁重複 ID。

### Open-Meteo

- 三個代表網格點覆蓋台北中心、大台北西側與東側。
- 每小時快照保留完整 48 小時預報與發布時間。
- 變數含氣溫、體感溫度、相對濕度、降雨、降雨機率、天氣碼、風速與陣風。

## 2. 原始物件合約

```text
source=<source>/date=<UTC date>/hour=<UTC hour>/
  <UTC fetch timestamp>-<first 12 SHA-256 characters>.json.gz
```

未修改的 API 回應先以 UTF-8 JSON 編碼，再雜湊與 gzip 壓縮。雲端物件含 `sha256` 與 `fetched_at` metadata；下游作業絕不編輯 raw objects。

## 3. 標準化

每個原始站點物件對應一個 Parquet shard，使增量重建具備冪等性，並能從 processed row 直接追回 raw response。來源時間以 Asia/Taipei 解析後儲存為 UTC；fetch time 與 source update time 維持獨立，不互相取代。

驗證會拒絕：空快照、同快照重複站點 ID、負的容量／車／車柱數、可借車大於容量、不支援的時間格式。

各來源請求互相獨立。單一來源重試後仍失敗時，其他成功物件照常保留，scheduler 記錄 `partial_failure` 與清理過的錯誤訊息；下一次排程正常繼續。

## 4. Label 對齊

觀測時間 `t` 的目標，是同一站點最接近 `t + 60 分鐘` 的可借車數。容忍範圍為 ±7 分鐘；超出時直接排除，不強行配對誤導 label。Target 只用於 label 與評估，絕不當作 predictor feature。

## 5. 特徵可用性政策

特徵必須在預測時點或之前已可得。

- Bike lag 使用不晚於 `t - lag` 的快照。
- Rolling statistics 結束於 `t`。
- 日曆值是可预先確定的。
- 未來天氣必須來自不晚於 `t` 發布的預報。
- 第一版排除活動資料，因為難以可靠建立歷史發布時間。

## 6. 可重現性

```bash
youbike-sync-r2
youbike-build-dataset
youbike-build-features
youbike-train
```

`youbike-sync-r2` 需在 `.env` 設定 S3-compatible endpoint、access key、secret key 與 bucket。它會分頁列出 source、manifest 與 control objects，驗證 gzip 與 SHA-256，原子寫入並略過未變的不可變證據。後續階段在缺輸入時明確失敗。Manifest 記錄建立時間、程式版本、列數、時間／站點覆蓋、模型名與驗證結果。

`data/cloud_raw` 是正式資料集唯一 raw input；`data/raw` 僅含 LaunchAgent 備份。正式 normalized shards 位於 `data/formal_processed`，features 位於 `data/formal_features`，避免筆電額外唤醒快照改變雲端頻率與驗證分佈。

## 7. 資料品質報告

設定 `COLLECTION_START_AT` 後，開發 smoke snapshots 保留但排除於官方證據期間。權威收集品質狀態位於私有 R2 `control/collection-quality.json`；首次部署可由不可變 object keys 重建，之後每次 Cron 根據 manifest 結果增量更新。預期數量以五分鐘站點頻率與每小時天氣頻率計算，報告 observed hours、各來源物件、完整率與五日／95% 門檻。公開 health check 絕不讀取該物件，避免外部流量消耗 R2 operations。

本地 LaunchAgent 日誌是獨立營運備份，不是權威完整率來源。電腦休眠時，已執行 run 可能 100% 成功，但仍遺漏排程區間。證據期結束後，最終模型輸入由 R2 不可變 raw objects 同步；在此之前本地 preview metrics 都明確標示為非最終。

Feature query 在計算 lag、rolling window、label、neighbour 與 training coverage 前使用相同時間下界，因此開發觀測不會影響正式模型。

最終報告將含：預期與成功 run、快照間最大／中位缺口、來源更新延遲、站點數變化、重複／無效列、target match coverage、weather forecast match coverage 與各欄缺值率。
