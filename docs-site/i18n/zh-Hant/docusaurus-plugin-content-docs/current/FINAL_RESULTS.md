# 五日正式模型結果

## 先說結論

正式模型競賽已在 2026-11-15 完成，只使用正式起始時間後保存在 R2 的不可變觀測。資料涵蓋台北與新北 **3,401 站**、共 **4,858,440 筆**有標籤資料。

CatBoost 在完全未參與選模的最後 24 小時 holdout 上，MAE 為 **2.026 輛**，優於 Persistence 的 **2.056 輛**，相對改善 **1.48%**，因此通過事先定義的 publication gate。

這裡的「正式」是指模型評估已完成且通過門檻。公開 App 現在會讀取版本化的 R2 批次預測快照，顯示每個合格站點的一小時後預測、經驗不確定區間與天氣 what-if。畫面會明確顯示預測起算時間；系統不會宣稱免費 Cloudflare Worker 內直接執行 CatBoost。

## 如何避免偷看到未來

1. 在任何模型比較前，先拿掉最後 24 小時。
2. 七個 learned models 在三個 expanding folds 上公平競賽。
3. 每個 fold 都有 12 小時未來 validation 與 60 分鐘 purge gap。
4. 依平均 CV MAE 選模型，MAE 同分才看 RMSE。
5. 選定 CatBoost 後，才重新使用完整 development period 訓練並評估一次 final holdout。

Final holdout 有 **976,209 筆**。它沒有參與 CatBoost 的選擇。

## 七模型交叉驗證排名

| 排名 | 模型 | 平均 CV MAE | 平均 CV RMSE |
|---:|---|---:|---:|
| 1 | CatBoost | **2.609** | 4.357 |
| 2 | XGBoost | 2.611 | **4.270** |
| 3 | LightGBM | 2.628 | 4.389 |
| 4 | Histogram Gradient Boosting | 2.641 | 4.418 |
| 5 | Extra Trees | 2.753 | 4.311 |
| 6 | Random Forest | 2.769 | 4.317 |
| 7 | Ridge | 2.938 | 4.581 |

CatBoost 與 XGBoost 很接近，平均 MAE 只差 0.0017 輛。CatBoost 依預先固定規則勝出，但不能因此宣稱它永遠明顯優於 XGBoost；資料累積數週後應重新檢查排名穩定性。

## 最終 holdout

| 指標 | CatBoost | Persistence | 相對改善 |
|---|---:|---:|---:|
| MAE | **2.026 輛** | 2.056 輛 | **1.48%** |
| RMSE | **3.500 輛** | 3.701 輛 | **5.41%** |
| WAPE | **18.24%** | 18.51% | **1.48%** |
| 空站風險 recall | 35.24% | **62.76%** | 較低 |
| 滿站風險 recall | 20.66% | **53.84%** | 較低 |

白話來說，CatBoost 平均車數預測比較準，也減少較大的誤差，但對「快沒車」或「快沒車位」的警示仍不如 Persistence。正確結論是：CatBoost 通過 regression gate，但風險警示還需要獨立 threshold 或分類目標。

## 分群檢查

- 新北 MAE：**1.889 輛**，459,648 筆。
- 台北 MAE：**2.148 輛**，516,561 筆。
- 雨天 MAE：**1.915 輛**；乾燥時段 MAE：**2.167 輛**。
- 大型站 MAE：**3.256 輛**；小型站為 1.432 輛。大型站的絕對誤差較大，但因庫存規模較大，WAPE 反而較低。
- Final holdout 落在週末，因此 weekday 泛化主要依 rolling folds 支持，仍需後續監測。

## 模型主要看什麼

固定 holdout sample 的 global SHAP 排名前十為：

1. 目前可借車數
2. 鄰近站點車輛比例
3. 五分鐘前車數
4. 站點容量
5. 十五分鐘前車數
6. 最近 60 分鐘波動
7. 時段
8. 最近 60 分鐘平均
9. 可還車位
10. 最近捷運站距離

在這五天內，天氣的重要性低於目前庫存與近期流動。這只是在短資料窗中對模型行為的解釋，不是因果結論，也不代表長期一定如此。

## Artifact 與重現方式

- Model ID：`catboost-20261115T150527Z`
- Code version：`d2ce8c27f02cc59a128d824b93bffd2d26a4254e`
- 模型：`artifacts/models/model.joblib`
- 評估：`artifacts/models/evaluation.json`
- Drivers：`artifacts/models/drivers.json`
- 區間校準：rolling validation 的 out-of-fold absolute error 第 90 百分位

```bash
make sync-r2
make dataset
make features
make train
```

## 如果再多一個月

五天符合題目，但仍沒有重複週期、重大活動、學校行程與多種天氣。下一階段應加入 day/week seasonal baselines、獨立 empty/full risk model、依站點規模與時段重做 interval calibration；等累積多個完整週期後，再公平比較 sequence 或 graph models。
