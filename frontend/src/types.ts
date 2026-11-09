export type Station = {
  source: "taipei" | "new_taipei";
  station_id: string;
  station_name: string;
  district: string;
  latitude: number;
  longitude: number;
  capacity: number;
  available_bikes: number;
  available_docks: number;
  predicted_bikes?: number;
  prediction_low?: number;
  prediction_high?: number;
};

export type LiveResponse = {
  as_of: string;
  count: number;
  model_status: string;
  stations: Station[];
};

