# Data Dictionary

## Normalized station snapshots

| Column | Type | Meaning |
|---|---|---|
| `source` | string | `taipei` or `new_taipei`. |
| `station_id` | string | Stable source station identifier. |
| `station_name` | string | Chinese station name without the `YouBike2.0_` prefix. |
| `district` | string | Administrative district from the source. |
| `address` | string | Source-provided Chinese address. |
| `latitude` | float | WGS84 latitude. |
| `longitude` | float | WGS84 longitude. |
| `capacity` | integer | Reported total station capacity. |
| `available_bikes` | integer | Bikes available for rental. This is the prediction target at `t+60m`. |
| `available_docks` | integer | Docks available for return. |
| `mechanical_bikes` | nullable integer | Conventional bikes. Taipei currently exposes only the total and therefore uses total rentable bikes here. |
| `electric_bikes` | nullable integer | Electric-assist bikes when supplied by New Taipei. |
| `is_active` | boolean | Whether the station is currently operating. |
| `source_updated_at` | UTC timestamp | Timestamp reported by the upstream feed. |
| `fetched_at` | UTC timestamp | Time this system received the response. |

## Core model features

| Feature | Definition |
|---|---|
| `bike_ratio` | `available_bikes / capacity`. |
| `hour_sin`, `hour_cos` | Cyclical local-hour representation. |
| `day_of_week` | Local weekday, preserving weekly structure. |
| `is_weekend` | Saturday or Sunday flag. |
| `bikes_lag_{5,15,30,60}m` | Latest known station inventory no later than the requested lag. |
| `bikes_delta_{5,15,30,60}m` | Current bikes minus the corresponding lag. |
| `bikes_rolling_mean_60m` | Mean inventory over the trailing hour. |
| `bikes_rolling_std_60m` | Inventory variability over the trailing hour. |
| `station_code` | Training-time category code for the compound `source:station_id` key. |
| `district_code` | Training-time category code for administrative district. |
| `source_code` | Training-time category code for city source. |
| `is_holiday` | Taiwan public-holiday flag generated for the observation date. |
| `nearest_mrt_distance_m` | Approximate straight-line metres to the nearest official Taipei Metro station coordinate. |
| `neighbor_count_1km` | Number of up to five nearest stations within one kilometre with a matched snapshot. |
| `neighbor_bikes_mean` | Mean rentable bikes across those neighbours. |
| `neighbor_bike_ratio_mean` | Mean rentable-bike ratio across those neighbours. |
| `forecast_temperature_2m` | One-hour target-time temperature from a forecast issued no later than `t`. |
| `forecast_precipitation` | One-hour target-time precipitation from an issue-time-safe forecast. |
| `forecast_precipitation_probability` | One-hour target-time rain probability. |
| `forecast_wind_speed_10m` | One-hour target-time wind speed forecast. |

