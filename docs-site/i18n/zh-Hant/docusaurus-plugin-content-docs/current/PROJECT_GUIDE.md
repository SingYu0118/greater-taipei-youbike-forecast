# 專案完整導讀：從問題、資料、模型到產品

這一章是整個專案的「白話論文版」。結構像技術報告，但不會故意堆術語。每個專業設計都會先說它在做什麼，再說為什麼需要，以及目前是否真的已經有證據。

## 摘要

這個系統要預測台北市與新北市每個 YouBike 站點，在 **60 分鐘後還有幾台車可以借**。

乍看之下，這像是一個「選模型」的題目，但真正困難的地方在資料。官方 API 會告訴我們現在每站有幾台車，卻沒有提供一份完整、可直接下載的「雙北每五分鐘歷史庫存」。所以不能一開始就訓練模型，而是要先自己建立歷史資料。

本專案因此完成了一整套流程：Cloudflare Worker 定時收集資料、R2 保存不可覆寫的原始紀錄、資料管線建立可重現資料集、七種模型在不偷看未來的時間驗證中競賽、FastAPI 驗證模型資格，React 地圖則把正式結果呈現給使用者。

正式 120 小時證據窗與模型競賽已完成。CatBoost 在 untouched final holdout 的 MAE 是 2.026 輛，優於 persistence 的 2.056 輛，因此通過預先定義的 regression publication gate。公開 App 現在從 R2 讀取版本化逐站預測快照，並顯示 forecast origin、區間與天氣 what-if。

## 1. 我們到底要解決什麼問題？

對某個站點 \(s\)，在時間 \(t\) 看到目前狀態後，我們要估計：

```text
預測車數（站點, t + 60 分鐘）= 模型（時間 t 當下可取得的資訊）
```

白話就是：

> 把現在已知的站點、時間、天氣、最近變化和附近站點資訊放進模型，預測同一站一小時後的可借車數。

預測值不能小於零，也不能大於站點容量，所以最後會限制在 `0` 到 `capacity` 之間。

這不是單純的「租借需求預測」。需求模型可能預測某區會有多少人借車，但這個專案直接回答使用者最在意的庫存問題：

- 車數接近 0：到了站點卻沒有車可借。
- 空位接近 0：騎到目的地卻沒有位置可還。

因此站點身分、容量、現在庫存和附近站點狀態都不能被忽略。

## 2. 怎樣才算成功？

在看到正式結果前，就先固定成功規則，避免分數不好時臨時改標準：

1. 正式起始時間後至少累積 120 小時，也就是五天。
2. 站點快照完整率至少 95%。
3. 所有驗證都依時間向前，不能隨機把資料列打散。
4. Training 和 validation 之間保留 60 分鐘 purge gap。
5. 最後 24 小時完全不能參與選模型，只能在最後評估一次。
6. 先看三個 validation folds 的平均 MAE，RMSE 作為同分判斷。
7. 最終模型在 final holdout 的 MAE 必須打敗 persistence baseline。
8. 另外報告空站、滿站 recall，以及不同城市、時段、天氣與站點類型的誤差。

Persistence 的意思非常簡單：

> 假設一小時後的車數跟現在完全一樣。

這個 baseline 很強。如果複雜模型連它都打不贏，就沒有理由上線。

## 3. 整套系統長什麼樣？

```text
台北即時 API ------------+
新北分頁 API ------------+--> Cloudflare Worker 每五分鐘執行
Open-Meteo 天氣 ----------+       retry、檢查、成本防線
                                    |
                                    v
                           R2 不可變原始歷史
                                    |
                                    v
                          正規化成 Parquet
                                    |
                                    v
                  建立一小時標籤與 35 個安全特徵
                                    |
                                    v
                    三個 baselines + 七種模型
                                    |
                       三折時間驗證 + 最後一天
                                    |
                                    v
                          模型檔與評估報告
                                    |
                           離線預測 publisher
                                    |
                       R2 snapshot + Worker API
                                    |
                 React + MapLibre + 雙語捷運篩選
```

這樣分層的好處是，出錯時可以知道是哪一層：

- 上游 API 沒回應；
- collector 抓取失敗；
- raw data 格式錯誤；
- label 時間配錯；
- 模型沒有打敗 baseline；
- API 或前端部署問題。

如果全部混在一個 Notebook 裡，可能只看到最後一格報錯，卻不知道資料早在哪一步就壞了。

## 4. 資料從哪裡來？

### 台北 YouBike

一次取得台北全部站點的即時 JSON，包含站點名稱、行政區、座標、容量、可借車、可還空位與更新時間。

### 新北 YouBike

資料是分頁的，而且很多數字以字串回傳。Collector 會一直翻頁，直到最後一頁筆數小於 page size；同時檢查跨頁站點 ID 是否重複，並設安全頁數上限。

### Open-Meteo

每小時保存三個雙北代表位置的 48 小時預報，包含溫度、體感溫度、濕度、降雨、降雨機率、天氣代碼、風速與陣風。

最重要的是保存 `issued_at`。因為模型只能使用預測當下已經發布的天氣預報，不能在事後拿實際天氣回去幫過去的模型作弊。

### 參考資料

- 台灣國定假日；
- 雙北捷運站座標；
- YouBike 站點位置與行政區。

活動資料第一版沒有加入，因為要證明「某個歷史時間點之前是否已經知道這場活動」並不容易。不能只因為今天知道活動發生過，就當作當時模型也知道。

## 5. Collector 如何確保資料可靠？

Cloudflare Worker 每五分鐘執行一次。台北、新北和天氣是獨立工作：如果新北暫時失敗，台北成功的資料仍然會保存，不會整批丟掉。

每份原始資料都會：

1. 保存 collector 的 fetch timestamp；
2. 計算 SHA-256 checksum；
3. gzip 壓縮；
4. 依 source、日期、時段分區；
5. 寫入 R2；
6. 在 manifest 記錄成功或失敗。

Object key 類似：

```text
source=taipei/date=2026-11-10/hour=08/
  20261110T080000Z-abcdef123456.json.gz
```

原始資料不會被下游修改。同一份資料日後可以重新建立 dataset，這就是可重現性。

### 為什麼不能只靠筆電？

筆電關機、睡眠或斷網時，本地排程就不會執行。Cloudflare Worker 在雲端執行，因此正式完整率以 R2 為準。本地 LaunchAgent 只是額外備份，不會拿來把雲端缺口補成看似完整。

### 如何避免 Cloudflare 意外花錢？

程式內有保守停止條件：固定結束時間、單一 object 最多 1 MB、最多預留 10,000 次 writes、最多預留 8 GB，以及 80% warning。

這些是程式層的 fail-closed 防線：接近上限就停止抓取或寫入。但仍要理解，它不是 Cloudflare 合約層的「絕對不計費保證」，帳戶通知與平台用量頁仍需保留。

## 6. Raw data 怎麼變成模型資料？

第一步是 normalization，把台北和新北不同欄位整理成共同 schema：

- `source`
- `station_id`
- `station_name`
- `district`
- `latitude`、`longitude`
- `capacity`
- `available_bikes`
- `available_docks`
- `is_active`
- `source_updated_at`
- `fetched_at`

台北和新北可能剛好有相同數字的 station ID，所以所有 join 都使用 `(source, station_id)`，不能只用 station ID。

資料路徑也刻意隔離：

- `data/cloud_raw`：正式 R2 證據；
- `data/formal_processed`：正式 normalized Parquet；
- `data/formal_features`：正式 features；
- `data/practice_*`：第三方公開歷史的練習資料；
- `artifacts/practice`：練習結果。

因此公開舊資料不可能不小心被算進正式五天。

## 7. 一小時後的答案怎麼建立？

假設某站在 10:00 有 12 台車，理想 target 是同一站 11:00 的車數。

但即時 API 可能在 10:59、11:02 或 11:05 才更新，所以系統尋找最接近 `t + 60 minutes` 的觀測，接受範圍是前後七分鐘。

如果找不到合格觀測，就把這列排除，而不是硬拿 11:20 或另一站資料當答案。

### Purge gap 為什麼必要？

例如 training 最後一列是 09:30，但它的答案是 10:30。若 validation 從 10:00 開始，training label 已經跨進 validation 的未來範圍。

因此 training 和 validation 中間空出 60 分鐘，避免標籤偷偷碰到驗證期間。

## 8. 模型看到哪些特徵？

目前共 35 個結構化輸入，大致分成六組。

### 8.1 現在狀態

- 現在可借車數；
- 現在可還空位；
- 站點容量；
- 車數占容量比例。

這通常是短期預測最重要的資訊。

### 8.2 最近變化

- 5、15、30、60 分鐘前車數；
- 與這些時間點相比增加或減少多少；
- 最近 60 分鐘平均與標準差。

如果現在有 20 台，但過去半小時每五分鐘都在下降，與一直維持 20 台是不同情況。

### 8.3 時間

- 小時；
- 星期幾；
- 平日或週末；
- 國定假日；
- `sin`、`cos` 形式的小時週期。

使用 `sin/cos` 是因為 23:00 與 00:00 實際很接近，普通數字卻會看起來差 23。

### 8.4 天氣

使用當時已發布、對應一小時後的天氣預報，包括溫度、體感溫度、濕度、降雨、降雨機率與風。

### 8.5 空間資訊

- 最近捷運站距離；
- 一公里內鄰站數；
- 最多五個鄰站的平均車數與車輛比例。

鄰近站可能互相替代。某站沒車時，使用者可能走到附近站點，因此只看單站會漏掉空間互動。

### 8.6 身分資訊

站點、行政區和來源會轉成 code，讓同一個 global model 保留地方差異。

## 9. 什麼叫「未來資料洩漏」？

資料洩漏是模型在訓練或驗證時，看到了真正上線時不可能知道的資訊。

常見錯誤包括：

- 隨機切分相隔五分鐘、幾乎相同的資料；
- 使用一小時後實際觀測到的天氣；
- rolling average 不小心包含未來資料列；
- 先用 final test 選模型，再宣稱它是獨立測試；
- 在所有資料上做 normalization 或 tuning 後才切分。

本專案的原則是：**每個 feature 都必須能回答「在預測時間 t，系統當時真的知道嗎？」**

## 10. 為什麼要比較這些模型？

### 三個 baselines

1. Persistence：一小時後等於現在。
2. Linear trend：依最近 30 分鐘變化往前推。
3. Previous hour：使用一小時前的車數。

### 七個 learned models

- Ridge：線性參考，容易解釋；
- Random Forest：傳統 bagging trees；
- Extra Trees：加入更多隨機性的 trees；
- Histogram Gradient Boosting：適合大量表格資料；
- LightGBM：高效率 boosting；
- XGBoost：成熟且可正規化的 boosting；
- CatBoost：另一種 tree construction 與 regularization。

所有模型必須使用完全相同的 features、folds、purge gap 與 final holdout，不能讓某一種模型獲得比較簡單的考題。

### 為什麼不是每站一個模型？

五天對單一站點而言很短，每站分開訓練容易過度擬合。Global model 可以一起學所有站共同的上下班、天氣和近期變化，再透過 station、district、source codes 表示地方差異。

### ARIMA、LSTM、TFT、N-HiTS、GMAN 呢？

不是不好，而是現在資料證據不夠：

- ARIMA/SARIMAX 若每站訓練，需要數千個模型反覆 rolling fit；
- 深度序列模型需要更多星期、天氣與事件型態；
- Graph model 需要較長歷史，才能證明它真的比簡單鄰站特徵更好。

滿一個月後，適合加入一個 global sequence model 和一個 graph challenger，但仍必須接受同一套時間驗證。

## 11. 如何公平選出模型？

正式資料最後 24 小時先鎖起來，剩下的 development data 做三個 expanding folds：

```text
Fold 1: [training------------][60m gap][12h validation]
Fold 2: [training 擴大----------------][gap][validation]
Fold 3: [training 再擴大--------------------][gap][validation]
Final : [全部 development-------------------][最後 24h]
```

每個模型先計算三折平均 MAE。平均 MAE 最低者勝出；若接近，再看 RMSE、fold 穩定性與運算成本。選完後才允許在 final holdout 評估一次。

如果 final holdout 沒打敗 persistence，即使它是七個 learned models 中最好的，也不能發布。

## 12. 評估指標代表什麼？

### MAE

平均每次差幾台車。例如 MAE = 3.2，可白話說成「平均預測差約 3.2 台」。這是主要指標。

### RMSE

對少數很大的錯誤處罰比較重，可看出模型是否偶爾失控。

### WAPE

把總絕對誤差除以總實際車數，方便理解整體相對誤差。

### Empty recall

實際發生 `<=2 台車` 的情況中，模型提前警告了多少。

### Full recall

實際只剩 `<=2 個空位` 的情況中，模型提前警告了多少。

只看整體 MAE 可能掩蓋真正重要的風險，所以還要分城市、行政區、時段、平假日、雨天、容量和風險類別檢查。

## 13. 模型怎麼解釋？

### Permutation importance

把某個 feature 打亂，看 holdout 分數惡化多少。惡化越多，代表模型越依賴它。

### SHAP

Global SHAP 說明整體最常影響預測的 features；local SHAP 解釋某一站這一次為何預測增加或減少。

### 雨天 what-if

保持站點、時間與現在車數不變，只改變 precipitation 和 rain probability，再比較預測差異。

這些結果只能說明「模型如何反應」，不能說「下雨必然造成精確幾台車的因果變化」。

## 14. 預測區間怎麼來？

只顯示一個數字容易讓使用者以為模型非常確定。系統會從 rolling validation 的 out-of-fold absolute errors 取第 90 百分位，建立容量範圍內的 prediction interval。

它不使用 final holdout 校準，避免最後測試資料又被拿回模型設計。

## 15. API 和前端怎麼運作？

React 產品目前會顯示雙北站點地圖、一小時預測、prediction interval、final metrics、global drivers 與天氣 what-if。使用者可先選捷運線，再選捷運站；地圖會自動縮放，並列出一公里內最近的 YouBike 站、目前可借數與 +60 分鐘預測。捷運站支援中文與英文搜尋，呈現格式固定為「中文站名（English Name）」。

FastAPI 會驗證 model bundle 與 evaluation report，保留作為原生 Python reference runtime。免費公開部署則由離線 publisher 執行 CatBoost，把 `control/latest-forecasts.json` 寫入 R2；Worker 只提供這份版本化快照。畫面顯示 forecast origin，不會拿 live inventory 冒充預測，也不宣稱 Worker 內直接跑 CatBoost。

## 16. 現在到底完成到哪裡？

正式 quality report 顯示 121.2 小時、1,228 次成功、4 次 partial、0 次 failure。最終資料有 4,858,440 筆 labelled rows、3,401 個站點；untouched final holdout 有 976,209 筆。

CatBoost 在三個 expanding folds 勝出；final MAE 2.026、RMSE 3.500，Persistence 為 MAE 2.056、RMSE 3.701。平均誤差 gate 已通過，但 CatBoost 的 empty/full recall 仍比 persistence 低，這是產品限制，不會隱藏。

### 已經能證明的事

- 台北、新北和天氣能穩定收集並保存；
- R2 collector 不依賴筆電持續開機；
- Raw data 能重建 dataset 和 features；
- 七模型競賽、時間 folds、final holdout 和 serving gates 已有測試；
- Docker、FastAPI、React、文件站、GitHub Actions 都能運作；
- CatBoost 沒有用 final holdout 選模，仍能在 final MAE 打敗 persistence；
- 公開 R2 snapshot 已提供逐站預測、區間與受控天氣情境。

### 還不能宣稱的事

- 跨多週、季節、連假或大型活動的穩定性；
- 獨立風險分類器能否改善 empty/full recall；
- request-time inference 是否值得新增付費 Python runtime。

## 17. 已經跑過的舊資料練習代表什麼？

Practice pipeline 使用公開台北歷史中的四天與 120 站：

- 30,257 筆 feature rows；
- 15,634 筆 training rows；
- 2,211 筆第三日 untouched test rows。

結果是：

- 最佳 learned model：CatBoost，MAE 4.210；
- Persistence：MAE 4.142；
- Learned model 比 persistence 差 1.63%。

這不是失敗，反而證明 gate 有作用。系統沒有因為 CatBoost 是複雜模型，就宣稱它比較好。

但這也不是正式成果，因為 practice data：

- 只有台北；
- 不是本專案 collector 的 fetch time；
- 沒有當時 archived issue-time weather；
- 不符合雙北五日正式資料範圍。

## 18. 現在還需要做什麼優化？

正式流程已完成，可用以下命令重建並重新發布：

```bash
make sync-r2
make dataset
make features
make train
make test
youbike-publish-forecasts
```

現階段優先事項是監控 snapshot freshness、API schema、empty/full risk recall，以及模型與 snapshot 的版本連結。不要反覆用 final holdout 調參；風險預警應建立獨立分類目標。

每次重新訓練仍要檢查完整率、fold stability、final gate、empty/full recall、subgroup errors、drivers 與 what-if；只有新版本完整通過相同規則，才可以取代目前發布版本。

## 19. 短期與一個月後的優化方向

### 短期

- 針對冠軍模型做小範圍、事先合理的 hyperparameter search；
- 找出誤差最大的行政區、時段與站點類型；
- 調整 empty/full 警示 threshold；
- 檢查 prediction interval coverage；
- 持續監控公開 snapshot 的 freshness 與 schema。

所有 tuning 仍只能使用 development folds，不能反覆使用 final holdout。

### 一個月後

- 加入 previous-day 和 previous-week baselines；
- 加入一個 global sequence model，例如 TFT 或 N-HiTS；
- 加入一個 graph challenger，例如 GMAN 類模型；
- 依容量與需求 regime 分開校準 prediction interval；
- 若能取得可靠發布時間，再加入活動資料；
- 把 forecast 接到獨立的 rebalancing optimization，而不是把兩者混成一個分數。

## 20. 面試時的一分鐘說法

> 我做的是一套雙北 YouBike 站點庫存預測系統，預測每站一小時後有幾台車。因為官方只有即時狀態，沒有完整的雙北五分鐘歷史，所以我先做雲端 collector，把台北、新北和 issue-time 天氣保存成不可覆寫的 R2 歷史。七個模型和三個 baselines 在三個向前時間 folds 競賽，最後一天完全 untouched。CatBoost 的 final MAE 是 2.026 輛，優於 persistence 的 2.056 輛，因此通過預先定義的 gate。公開 App 現在提供版本化逐站預測、不確定區間、天氣 what-if，以及中英雙語捷運線與站點導覽。

## 21. 你最需要記住的五句話

1. 這不是只做模型，而是從「沒有歷史」開始建立完整資料產品。
2. 最重要的技術原則是預測當下不能偷看未來。
3. 複雜模型必須打敗「一小時後跟現在一樣」才有價值。
4. 舊公開資料只能驗證流程，正式結果一定來自自己的雙北五日 R2 歷史。
5. 正式五日結果已發布，但跨週期與空／滿站風險仍是下一階段限制。

