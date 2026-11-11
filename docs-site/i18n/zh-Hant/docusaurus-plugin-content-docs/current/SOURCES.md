# 資料來源與溯源

目前實作的所有外部輸入都是公開且無需金鑰。Raw response 會連同 fetch time 與 SHA-256 保留，使 processed row 可稽核回 source object。

| 輸入 | 用途 | 官方來源 | 收集政策 |
|---|---|---|---|
| 台北 YouBike 即時可用狀態 | 站點狀態與 metadata | [台北即時 JSON](https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json) | 每五分鐘 |
| 新北 YouBike 即時可用狀態 | 站點狀態、metadata、一般／電動車數 | [新北資料集](https://data.ntpc.gov.tw/datasets/010e5b15-3823-4b20-b401-b1cf000550c5) | 每五分鐘，取得所有頁 |
| Open-Meteo forecast | 預測當時可知的 issue-time weather | [Forecast API](https://open-meteo.com/en/docs) | 三個代表網格每小時一次 |
| 台北捷運站座標 | 最近捷運距離 | [台北市資料大平台](https://data.taipei/dataset/detail?id=1eefa68d-7c8d-491b-8e75-66a161947426) | 版本化參考快照 |
| 台灣國定假日 | 假日日曆特徵 | Python `holidays` 台灣日曆 | 依日期決定性產生 |

## 已知溯源限制

- Live feed 只提供當下狀態，歷史只能從 collector 啟動後開始。
- 官方 source update timestamp 與 collector fetch timestamp 分開保留。
- 三個天氣網格近似空間差異，不是站點級感測器。
- 目前捷運參考覆蓋官方台北捷運資料；未來應以獨立版本來源對齊新北輕軌系統。
- 活動資料因難以可靠取得歷史發布時間而刻意排除；沒有該時間就加入可能導致未來洩漏。
