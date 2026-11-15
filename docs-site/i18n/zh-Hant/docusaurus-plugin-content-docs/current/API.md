# API 合約

後端啟動後，FastAPI OpenAPI 文件可於 `/docs` 查看。

## `GET /health`

回報服務時間、健康狀態與模型 serving 狀態。正式 publication gate 通過後，公開部署目前回傳 `model: ready` 與 `forecast_serving: snapshot`。

## `GET /api/v1/stations/live`

查詢參數：

- `source`：`all`、`taipei` 或 `new_taipei`。

回應欄位：

```json
{
  "as_of": "UTC timestamp",
  "count": 3446,
  "model_status": "ready",
  "stations": [
    {
      "source": "taipei",
      "station_id": "500101001",
      "station_name": "捷運科技大樓站",
      "station_name_en": "MRT Technology Bldg. Sta.",
      "district": "大安區",
      "district_en": "Daan Dist.",
      "latitude": 25.02605,
      "longitude": 121.5436,
      "capacity": 28,
      "available_bikes": 1,
      "available_docks": 27
    }
  ]
}
```

官方上游來源無法使用時，端點回傳 HTTP 502 與一般化訊息；上游細節僅保留在伺服器日誌。

英文站名與行政區直接使用官方 `snaen`、`sareaen`。前端可搜尋兩種語言，兩者都有時以「中文站名（English Name）」呈現。

## 受證據門檻保護的模型端點

- `GET /api/v1/forecasts/latest`：所有站點的最新預測與有界不確定區間，並含模型 ID、家族、訓練時間、程式版本與區間校準方法。
- `GET /api/v1/model/metrics`：所有滾動驗證 fold、模型比較、baseline 與未觸碰的最終 holdout。
- `GET /api/v1/model/drivers`：permutation importance、全域 SHAP 與單筆局部 SHAP 範例。
- `POST /api/v1/stations/{station_id}/what-if`：控制降雨、降雨機率或氣溫情境。JSON body 必須提供 `source`，避免站點識別混淆。
- `GET /api/v1/data/quality`：收集完整率、新鮮度、排程結果與 120 小時證據門檻。

模型 `catboost-20261115T150527Z` 已通過 publication gate。公開 Worker 從 R2 讀取 `control/latest-forecasts.json`，不在 edge isolate 內載入 Python 模型；只有該發布物件遺失或格式錯誤時，`GET /api/v1/forecasts/latest` 才會回傳 HTTP 503。評估與 drivers 報告仍可獨立稽核。服務絕不以合成或示範預測取代真實結果；what-if 會明確標示為模型行為，不是因果估計。

`GET /api/v1/data/quality` 只報告官方證據期間。開發快照獨立呈現，且永遠不會推進已完成的正式門檻。
