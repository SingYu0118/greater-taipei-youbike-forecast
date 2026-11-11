# 模型與時間驗證

## 1. 目標

預測每個營運站點的 `available_bikes(t + 60 minutes)`，預測值會被限制在零到站點容量的物理範圍。

## 2. 為什麼不能隨機切分

相隔五分鐘的列具有幾乎相同的庫存與 rolling features。隨機切分會讓近乎重複的未來觀測同時出現在 training 與 validation，嚴重高估真實部署表現。所有切分因此使用所有站點共享的完整時間區間。

## 3. 最終 holdout

最後 24 小時在任何模型比較與調參前完全移除。選定勝出模型家族與設定後，只評估一次，模擬新的生產日。

## 4. Expanding-window 回測

開發期使用三個 folds，每個 validation window 為 12 小時。Training set 依時間擴張，最後訓練觀測與第一個驗證觀測間保留 60 分鐘間隔。

```text
Fold 1: [ training ---------------- ] [60m gap] [12h validation]
Fold 2: [ training expands ------------------ ] [gap] [12h validation]
Fold 3: [ training expands further ------------------- ] [gap] [12h validation]
Final : [ all development data ----------------------- ] [24h untouched test]
```

Purge gap 防止訓練尾端 label 跨入驗證期間。

### 72 小時早期診斷

正式資料累積滿 72 小時後，`make early-diagnostic` 會同步不可變更的雲端歷史、重建
正式資料集，再執行事先固定的早期檢查：前 48
小時作為訓練期，保留 60 分鐘 purge 避免 target 重疊，第三天則是所有七個模型與
三個 baseline 共用、完全未參與訓練的測試期。指令只會寫出
`artifacts/preliminary/early-72h-evaluation.json`，刻意不產生可供 API 發布的模型。
這能提早確認系統是否學到訊號，但必須標示為 preliminary，不能取代五日 rolling
validation 與 final holdout。

`make train-early` 則只針對已建好的 feature file 重跑 benchmark。舊觀測可透過
`--features` 明確傳入，用於 pipeline 開發、預訓練實驗與除錯，報告會
標示為 `development-only preliminary`。只有正式起始時間後、時間戳可信的資料，才能
計入正式成績與 production gate。

## 5. 競爭模型

### Baselines

- Persistence：未來車數等於當前車數。
- Linear trend：將最近 30 分鐘變化向前外推。
- Previous hour：使用一小時前觀測到的站點數。
- Previous day/week 僅在歷史足夠時啟用。

### 學習模型

- Ridge：中位數插補與縮放的可解釋線性對照。
- Random Forest：傳統 bootstrap-aggregated tree 對照。
- Extra Trees：非線性隨機 bagged-tree。
- Histogram Gradient Boosting：為大型表格資料設計、依賴較輕的 histogram booster。
- LightGBM：針對結構化資料優化的 gradient boosting。
- XGBoost：成熟的 histogram-based gradient boosting。
- CatBoost：具有不同正則化與樹建立方式的 boosting。

七個候選者涵蓋一個線性對照、兩種 bagged trees 與四種 boosting 實作。傳統 Gradient Boosting 的 exact split search 不適合目前列數，因此由 histogram 版本取代。ARIMA/ARIMAX 不納入五日全域競賽：公平的 rolling-origin 比較需數千個站點模型與重複擬合，但目前需要能跨站點共享資訊且使用空間特徵的單一可部署模型。LSTM、TFT、N-HiTS 等延後至至少一個月歷史。

調參僅允許使用 development folds。選擇先看平均 CV MAE，再以 RMSE 破同分；同時報告 fold 穩定性、推論延遲與空／滿站召回率。Bagged trees 使用有界深度與最小 leaf size，以控制數百萬列的記憶體。每個 fold 記錄 fit time、predict time 與 throughput，但不改變預先宣告的 MAE/RMSE 規則。

## 6. 指標

| 指標 | 用途 |
|---|---|
| MAE | 主指標，可直觀解釋平均差幾輛車。 |
| RMSE | 對少數大誤差施加較大懲罰。 |
| WAPE | 根據觀測需求標準化總絕對誤差。 |
| Empty recall | 實際 `<=2 bikes` 事件被警示的比例。 |
| Full recall | 實際 `<=2 docks` 事件被警示的比例。 |

結果會依城市、行政區、站容量、小時、平日／週末、雨勢與風險類別分群，避免強勢整體平均遮蔽營運弱點。

## 7. 預測區間

模型 bundle 保留勝出模型 out-of-fold 絕對誤差的第 90 百分位，不使用 final holdout。App 顯示受容量限制的區間，不只給虛假精確的點預測。歷史增加後，應依 horizon、capacity band 與 demand regime 分開校準。

## 8. 可解釋性

- Permutation importance：打亂特徵後的 out-of-time holdout 分數變化。
- Global SHAP：識別樣本 holdout 預測的全域驅動因子。
- Local SHAP：解釋單一站點預測。
- ALE 或受限 partial dependence：呈現非線性反應。
- 降雨 what-if：固定站點狀態與時間，只改變預報天氣輸入。

這些解釋模型行為，不主張因果關係。

## 9. 最低證據門檻

模型只在同時滿足以下條件時標示為 production-ready：

1. 使用至少五個完整日的站點歷史；
2. final-holdout MAE 優於 persistence；
3. 報告所有 folds 與未觸碰最終測試；
4. 通過特徵可用性與 target alignment 檢查；
5. API 暴露訓練覆蓋與模型版本。

服務層會強制這些條件。單有 model artifact 不足夠；必須 final-holdout MAE 較低、官方收集達 120 小時且快照完整率至少 95%，否則 forecast route 回傳 HTTP 503。
