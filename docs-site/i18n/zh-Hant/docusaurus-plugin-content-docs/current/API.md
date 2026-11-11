# API 合約

後端啟動後，FastAPI OpenAPI 文件可於 `/docs` 查看。

## `GET /health`

回報服務時間、健康狀態與已載入的模型狀態。在強制收集期間，`collecting-training-data` 是預期狀態，不可將它呈現為預測結果。

## `GET /api/v1/stations/live`

查詢參數：

- `source`：`all`、`taipei` 或 `new_taipei`。

回應欄位：

```json
{
  "as_of": "UTC timestamp",
  "count": 3446,
  "model_status": "collecting-training-data",
  "stations": [
    {
      "source": "taipei",
      "station_id": "500101001",
      "station_name": "MRT Technology Bldg. Sta.",
      "district": "Daan Dist.",
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

## 受證據門檻保護的模型端點

- `GET /api/v1/forecasts/latest`：所有站點的最新預測與有界不確定區間，並含模型 ID、家族、訓練時間、程式版本與區間校準方法。
- `GET /api/v1/model/metrics`：所有滾動驗證 fold、模型比較、baseline 與未觸碰的最終 holdout。
- `GET /api/v1/model/drivers`：permutation importance、全域 SHAP 與單筆局部 SHAP 範例。
- `POST /api/v1/stations/{station_id}/what-if`：控制降雨、降雨機率或氣溫情境。JSON body 必須提供 `source`，避免站點識別混淆。
- `GET /api/v1/data/quality`：收集完整率、新鮮度、排程結果與 120 小時證據門檻。

預測與 what-if 端點在所有發佈條件通過前回傳 HTTP 503：必須存在產物、最終 holdout MAE 優於 persistence、官方收集達 120 小時且快照完整率達 95%。訓練後的評估與驅動因子報告可獨立稽核。服務絕不以合成或示範預測取代真實結果；what-if 會明確標示為模型行為，不是因果估計。

`GET /api/v1/data/quality` 只報告官方證據期間。未設定 `COLLECTION_START_AT` 前，官方覆蓋與排程計數均為零；開發快照獨立呈現，不推進門檻。
