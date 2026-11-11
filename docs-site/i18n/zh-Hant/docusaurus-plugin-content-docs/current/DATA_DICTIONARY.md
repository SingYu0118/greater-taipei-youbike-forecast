# 資料字典

## 標準化站點快照

| 欄位 | 型別 | 意義 |
|---|---|---|
| `source` | string | `taipei` 或 `new_taipei`。 |
| `station_id` | string | 來源內穩定的站點識別碼。 |
| `station_name` | string | 移除 `YouBike2.0_` 前綴的中文站名。 |
| `district` | string | 來源提供的行政區。 |
| `address` | string | 來源提供的中文地址。 |
| `latitude` / `longitude` | float | WGS84 緯度／經度。 |
| `capacity` | integer | 回報的站點總容量。 |
| `available_bikes` | integer | 可借車輛；也是 `t+60m` 預測目標。 |
| `available_docks` | integer | 可還車柱數。 |
| `mechanical_bikes` | nullable integer | 一般自行車；台北目前僅提供總數，因此使用總可借車數。 |
| `electric_bikes` | nullable integer | 新北有提供時的電動輔助車數。 |
| `is_active` | boolean | 站點是否營運中。 |
| `source_updated_at` | UTC timestamp | 上游 feed 回報的時間。 |
| `fetched_at` | UTC timestamp | 本系統收到回應的時間。 |

## 核心模型特徵

| 特徵 | 定義 |
|---|---|
| `bike_ratio` | `available_bikes / capacity`。 |
| `hour_sin`, `hour_cos` | 本地小時的循環編碼。 |
| `day_of_week` | 本地星期，保留每週結構。 |
| `is_weekend` | 週六或週日旗標。 |
| `bikes_lag_{5,15,30,60}m` | 不晚於指定 lag 的最新已知站點庫存。 |
| `bikes_delta_{5,15,30,60}m` | 當前車數減對應 lag。 |
| `bikes_rolling_mean_60m` | 過去一小時平均庫存。 |
| `bikes_rolling_std_60m` | 過去一小時庫存波動。 |
| `station_code` | 訓練時為 `source:station_id` 複合 key 產生的類別碼。 |
| `district_code` / `source_code` | 行政區／城市來源類別碼。 |
| `is_holiday` | 觀測日期的台灣國定假日旗標。 |
| `nearest_mrt_distance_m` | 到最近官方台北捷運站座標的估計直線公尺數。 |
| `neighbor_count_1km` | 一公里內最多五個有對應快照的近鄰站數。 |
| `neighbor_bikes_mean` | 這些近鄰站可借車平均數。 |
| `neighbor_bike_ratio_mean` | 這些近鄰站可借車比率平均。 |
| `forecast_temperature_2m` | 由不晚於 `t` 發布的預報取得一小時後氣溫。 |
| `forecast_precipitation` | issue-time-safe 預報的一小時後降雨量。 |
| `forecast_precipitation_probability` | 一小時後降雨機率。 |
| `forecast_wind_speed_10m` | 一小時後風速預報。 |
