# 72 小時早期模型結果

## 先說結論

第一份使用正式 R2 歷史的模型診斷已在 2026-11-13 完成。XGBoost 在第三天測試的 MAE 是 **2.547 台**，Persistence 是 **2.777 台**，平均誤差改善 **8.30%**。

這是好訊號，但仍然是 `preliminary_not_for_production`，不能取代五日 rolling validation 與 final holdout。

## 測試範圍

- 前 48 小時訓練；
- 60 分鐘 purge gap；
- 第三天作為所有模型共用的 untouched test；
- 1,919,352 列 training rows；
- 971,474 列 test rows；
- 3,401 個站點。

## 完整排名

| 排名 | 模型 | MAE | RMSE | WAPE | 空站 recall | 滿站 recall |
|---:|---|---:|---:|---:|---:|---:|
| 1 | XGBoost | 2.547 | 4.314 | 27.40% | 34.82% | 6.96% |
| 2 | CatBoost | 2.559 | 4.444 | 27.53% | 45.91% | 11.67% |
| 3 | LightGBM | 2.567 | 4.452 | 27.62% | 46.14% | 10.88% |
| 4 | Histogram Gradient Boosting | 2.569 | 4.460 | 27.64% | 45.51% | 11.87% |
| 5 | Random Forest | 2.663 | 4.304 | 28.66% | 15.45% | 5.29% |
| 6 | Extra Trees | 2.666 | 4.324 | 28.69% | 13.60% | 3.82% |
| 7 | Persistence baseline | 2.777 | 4.976 | 29.88% | 65.26% | 43.39% |
| 8 | Ridge | 2.916 | 4.713 | 31.37% | 26.09% | 1.87% |
| 9 | Linear-trend baseline | 3.995 | 6.714 | 42.99% | 67.42% | 60.70% |
| 10 | Previous-hour baseline | 4.133 | 6.985 | 44.48% | 52.39% | 27.53% |

## 怎麼解讀？

XGBoost 的 MAE 比 Persistence 低 0.231 台，改善 8.30%。這代表模型從 lag、時間、天氣、站點與鄰站資訊中學到了一些對第三天有效的訊號。XGBoost 訓練約 22.99 秒，預測 971,474 列約 0.83 秒。

但前四名 boosting 模型只差約 0.02 MAE。只有一天測試，不能證明 XGBoost 在其他日期一定勝出。

最明顯的弱點是風險 recall。XGBoost 空站／滿站 recall 只有 34.82%／6.96%，Persistence 則有 65.26%／43.39%。因此目前只能說：

> XGBoost 在第三天的平均車數誤差最好，但缺車與滿站警示仍需要改善。

不能說 XGBoost 已全面勝過 baseline。原因是 MAE 主要獎勵一般車數準確，沒有直接優化少見的 0--2 台或 0--2 空位事件。

## 下一步

正式五日流程仍使用三個 expanding-window folds、60 分鐘 purge 與最後 24 小時 holdout。Final MAE 必須打敗 Persistence，也必須同時報告 empty/full recall 與 subgroup errors。

若正式結果仍有風險 recall 問題，可以只在 development folds 上研究 threshold calibration 或獨立 risk classifier；不能反覆使用 final holdout 調整。

原始結果：`artifacts/preliminary/early-72h-evaluation.json`。Publication gate 目前仍為 false。

