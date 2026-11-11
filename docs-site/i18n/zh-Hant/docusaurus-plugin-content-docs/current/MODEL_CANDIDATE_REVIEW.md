# 模型候選評估

## 決策規則

模型只有在以下條件均成立時才進入正式五日競賽：

1. 由預測時可取得的資訊，直接預測 60 分鐘後；
2. 可跨約 3,400 個站點共享資訊；
3. 可使用日曆、天氣、位置與近鄰站特徵；
4. 能在一般硬體完成相同的 purged expanding-window 評估；
5. 可序列化並由現有 FastAPI 推論路徑服務。

加入無法滿足這些條件的演算法，只會增加數量，不會形成公平或可營運的比較。

## 正式納入

| 家族 | 候選模型 | 納入理由 |
|---|---|---|
| 線性 | Ridge | 穩定、可解釋的低變異對照。 |
| Bagging | Random Forest | 標準 bootstrap-aggregated tree benchmark。 |
| 隨機 bagging | Extra Trees | 測試額外 split 隨機性能否改善泛化與速度。 |
| Boosting | Histogram Gradient Boosting | 依賴較輕、專為大型表格資料設計，可原生導向缺值。 |
| Boosting | LightGBM | 高效 leaf-wise histogram boosting。 |
| Boosting | XGBoost | 成熟的正則化 histogram boosting，使用不同 tree builder。 |
| Boosting | CatBoost | 對稱樹 boosting 與不同正則化策略。 |

所有候選者使用相同 features、training timestamps、purge gap、validation timestamps 與最終 holdout。選擇依平均 CV MAE，再以平均 RMSE 破同分。勝出家族只在全部 development data 重新 fit 一次，並只對 final holdout 評分一次。

Linux 使用官方 CPU-only XGBoost distribution，macOS 使用標準 CPU-capable distribution，避免無 GPU 的 production container 拉取 GPU 與 collective-communication libraries。

## 已評估但延後

| 候選模型 | 目前決策 | 重新評估條件 |
|---|---|---|
| ARIMA | 延後 | 數週完整季節歷史後作為站點診斷。 |
| ARIMAX/SARIMAX | 延後 | 重複週期足以支持數千個 rolling station fits 時。 |
| LSTM/GRU | 延後 | 至少一個月，使用含 station embeddings 的 global model。 |
| TFT、N-HiTS、TiDE、PatchTST | 延後 | 更長歷史與另一套經洩漏稽核的 sequence pipeline。 |
| 圖神經網路 | 延後 | 更長歷史且有可辯護 station graph 或 OD trips。 |
| Prophet | 排除 | 適合長期趨勢與季節，不適合短期網路狀態。 |
| kNN | 當前規模排除 | 數百萬列下推論與記憶體擴展性差。 |
| kernel SVR | 當前規模排除 | 訓練複雜度不適合預期列數。 |
| exact Gradient Boosting | 排除 | Histogram boosting 以低得多的成本提供相關家族比較。 |
| AdaBoost | 排除 | 增加較弱 tree boosting，無明確營運優勢。 |
| Elastic Net/Lasso | 不進最終表格 | Ridge 已提供線性對照，station codes 不是有意義的稀疏係數。 |

## 機率預測

不確定性與點模型選擇分開處理。Production bundle 以 out-of-fold absolute residuals 校準受容量限制的區間。更多歷史後可比較 Quantile LightGBM 或 distributional model，但不應只為增加數量就當成額外 point-model family。

## 神經模型後續

一個月後，建議第二階段比較 global N-HiTS 或 TFT，而不是每站一個網路。它應使用 rolling-origin folds、known-future 日曆與天氣、observed-past 站點與近鄰狀態、station embeddings，以及和表格模型相同的 final holdout。只有改善幅度足以支持更大的訓練、推論與監控成本時才採用。
