# 研究文獻與設計啟示

這份文件記錄公開 repository 與原始研究如何改變本系統的設計。只有實際影響預測目標、特徵契約、驗證、模型競賽或營運 roadmap 的來源才會納入。只預測租借需求、而非站點庫存的研究會明確標示，避免混淆。

## 文獻回顧後改變的決策

| 文獻證據 | 本專案決策 | 狀態 |
|---|---|---|
| 站點庫存有容量上下界，而且無車與無空位是不同的服務失敗。 | 直接預測 `available_bikes(t+60)`，將結果限制在 `[0, capacity]`，並分開報告 empty/full risk。 | 已採用 |
| 60 分鐘仍保有站點層級精度，同時給營運人員足夠時間安排調度車。 | 固定一個直接的 60 分鐘目標，不在看到結果後才選較容易的 horizon。 | 已採用 |
| 現在庫存通常是很強的短期預測因子，簡單動態模型可能與複雜模型相當。 | Persistence 是正式發布門檻，不只是用來陪襯複雜模型的弱 baseline。 | 已採用 |
| 時間、天氣、站點身分與近期流量反覆被證明重要；鄰近站互動時，空間模型可能帶來額外價值。 | 在同一套資訊可用性契約下使用 issue-time 天氣、日曆、lags、rolling statistics、捷運距離與鄰站庫存。 | 已採用 |
| 預測 arrivals 與 departures 後可以用淨流量推回未來庫存，但需要可靠的 trip 或 flow observations。 | 第一版維持直接庫存預測，因為雙北公開來源是 snapshots，不是完整 trips。 | 延後 |
| Graph attention 與 recurrent model 可學習時空依賴，但需要更多重複週期與較長歷史。 | 五日門檻先使用輕量鄰站特徵；滿一個月後再加入一個 global graph 或 sequence challenger。 | 延後 |
| 預測準確度與實際調度價值是不同的評估層。 | 目前以 forecasting 為範圍；routing、incentive 與 inventory optimization 列為下游工作。 | 延後 |

## Repository 評估

### 公開資料可用性判定

| 來源 | Repository 內實際找到的內容 | 能否使用 | 本專案決策 |
|---|---|---|---|
| `tses89214/youbike-historical-data` | 以發布時間標記的台北每日 snapshot CSV。 | 可以，但只限開發練習。 | 已隔離在 practice pipeline，可測試特徵工程與早期第三日測試，但不能取代正式 collector window。 |
| `aaron1aaron2/GMAN-based-Forecasting-of-YouBike-Shortages-in-Taiwan` | 2021-12-04 至 2022-01-08 共 5,181 份十分鐘 raw JSON，另有站點矩陣、站點對照與 graph edges；樣本是舊版台北 YouBike schema。 | 可以作 legacy benchmark 或 graph-model sandbox。 | 不併入正式資料：僅涵蓋台北、年代較舊、站網不同，沒有新北與本系統 collector receive time。若散布其程式或封裝內容，需保留 MIT notice。 |
| `joeycyhuang/bss-inventory-rebalancing` | 少量衍生檔；station condition 約涵蓋 2023-04-01 至 2023-04-05，另有 trip aggregates 與 optimization outputs。README 描述的則是另一份 2024 年 5--8 月政府資料。 | 只能當方法範例。 | Repository 內檔案無法重現 README 所述四個月資料，而且未找到 repository license，因此不匯入訓練。 |
| `taipei-doit/YouBike-Optimization` | 模型程式與交通、土地、人口、交易資料的空白輸入目錄。 | 沒有可直接訓練的歷史資料。 | 只採用特徵與模型概念；repository 未發布重現研究所需的 raw operational inputs。 |

這些來源可用於正式上線前的實驗，但無法取代作業要求的五日自有收集。正式 metrics 仍只使用宣告起始時間後，由本專案 collector 實際收到的 snapshots。

### 直接相關的 YouBike 專案

| Repository | 證明了什麼 | 本專案採用內容 | 證據邊界 |
|---|---|---|---|
| [aaron1aaron2/GMAN-based-Forecasting-of-YouBike-Shortages-in-Taiwan](https://github.com/aaron1aaron2/GMAN-based-Forecasting-of-YouBike-Shortages-in-Taiwan) | 每十分鐘蒐集台北庫存並進行 graph-based inventory forecasting。 | 支持空間特徵與一個月後的 graph model roadmap。 | 預設只預測下一個十分鐘、使用較舊 PyTorch，且未文件化我們要求的 purged rolling validation。 |
| [tses89214/youbike-historical-data](https://github.com/tses89214/youbike-historical-data) | 由 live feed 累積成每日台北站點庫存 CSV。 | Development-only practice importer 與早期管線診斷。 | 僅台北；因沒有 collector fetch time 而使用 `infoTime`；不能當正式證據。 |
| [taipei-doit/YouBike-Optimization](https://github.com/taipei-doit/YouBike-Optimization) | 官方合作的每小時租借／歸還需求模型，使用 LightGBM、XGBoost 與 CatBoost。 | 支持 global tabular boosting 與交通、地理 context。 | 預測網格需求與潛在站點，不是精確的未來站點庫存。 |
| [joeycyhuang/bss-inventory-rebalancing](https://github.com/joeycyhuang/bss-inventory-rebalancing) | 使用站點、交易與調度資料研究台北庫存調度與 routing。 | 作為正式預測通過後的下游營運 roadmap。 | 其資料不能取代作業要求的公開 collector 證據。 |

### 可轉用的系統參考

| Repository | 可學習內容 | 本專案回應 |
|---|---|---|
| [dssg/bikeshare](https://github.com/dssg/bikeshare) | 預測 60 分鐘 arrivals 與 departures，再用淨流量推回庫存，且包含 collection、model、validation 與 map application。 | 保留 60 分鐘營運問題與端到端架構；在取得可靠 trip flows 前延後 net-flow target。 |
| [danielazamorah/citibike-stations-ml](https://github.com/danielazamorah/citibike-stations-ml) | 將 bike/dock availability 視為受容量限制的站點輸出，並以 cloud API 服務模型。 | 保留容量邊界與明確 serving contract；不複製其 calendar-only target 或 proof-of-concept 指標。 |
| [rishi-kumar0208/divvy-bike-rebalancing](https://github.com/rishi-kumar0208/divvy-bike-rebalancing) | 使用 chronological split、past-only lag features，並將 forecasting 與 network-flow optimization 分開。 | 支持只使用過去特徵、保留未碰觸的 future test，以及獨立 optimization layer。 |

## 原始研究

1. Almannaa、Elhenawy 與 Rakha（2020），[Dynamic linear models to predict bike availability in a bike sharing system](https://doi.org/10.1080/15568318.2019.1611976)。比較 15、30、45、60、120 分鐘 bike-count prediction，說明簡單動態模型仍是可信 challenger。
2. Zheng 等人（2020），[GMAN: A Graph Multi-Attention Network for Traffic Prediction](https://doi.org/10.1609/aaai.v34i01.5477)。支持未來加入時空 graph challenger，但不能取代共同且防洩漏的驗證方式。
3. Juan 等人（2024），[Enhancing Youbike Redistribution System](https://doi.org/10.3390/proceedings2024110035)。台北研究將需求預測、天氣、人流、站點 clustering 與調度串接；詳細資料需正式申請，無法由 live feed 公開重現。
4. Nejadshamsi 等人（2026），[Predicting Short-Term Bike-Sharing Demand at Station Level](https://doi.org/10.1016/j.knosys.2025.114986)。說明一小時 horizon 的營運意義，以及 check-in/check-out 關聯的重要性。
5. Hulot 等人（2024），[Dynamic Rebalancing for Bike-Sharing Systems under Inventory Interval and Target Predictions](https://doi.org/10.1016/j.ejtl.2024.100147)。清楚分開需求預測、庫存目標與調度決策。

## 解讀規則

- 不將其他 repository 的 metrics 複製到本專案結果表，因為資料、目標、horizon 與 split 不同。
- 文獻支持某個模型家族，不代表該模型自動符合五日正式競賽資格。
- 新 challenger 必須共用 issue-time features、purge gap、folds、final holdout 與 persistence gate。
- 公開第三方歷史資料的結果仍然只是 development evidence。
- 模型解釋只描述模型行為，不代表因果效果或保證營運節省。

最後檢視：2026-11-12。
