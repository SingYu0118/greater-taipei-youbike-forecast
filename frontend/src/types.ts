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
  observation_time?: string;
};

export type LiveResponse = {
  as_of: string;
  count: number;
  model_status: string;
  model?: {
    model_id: string;
    model_name: string;
    trained_at: string;
    code_version: string;
    uncertainty_calibration: string;
  };
  stations: Station[];
};

export type HealthResponse = {
  status: string;
  time: string;
  model: "ready" | "validated-results-ready" | "collecting-training-data";
  forecast_serving?: "ready" | "pending";
};

export type QualityResponse = {
  generated_at: string;
  sources: Record<
    string,
    {
      objects: number;
      coverage_hours?: number;
      freshness_minutes?: number;
      collection_completeness?: number;
    }
  >;
  scheduler_runs: {
    success: number;
    partial_failure: number;
    failure: number;
    malformed: number;
  };
  minimum_requirement: {
    official_start_at: string | null;
    required_hours: number;
    observed_station_hours: number;
    minimum_completeness: number;
    observed_station_completeness: number;
    five_days_met: boolean;
    collection_quality_met: boolean;
  };
};

export type MetricSet = {
  mae: number;
  rmse: number;
  wape: number;
  empty_recall: number;
  full_recall: number;
};

export type ModelMetricsResponse = {
  model_id?: string;
  created_at?: string;
  winner: string;
  selection_rule: string;
  coverage: { start: string; end: string; rows: number; stations: number; final_holdout_rows?: number };
  validation?: { folds: number; validation_hours: number; purge_minutes: number; final_holdout_hours: number };
  cross_validation?: Record<string, { mae: number; rmse: number }>;
  final_holdout: Record<string, MetricSet>;
  publication_gate?: { beats_persistence_mae: boolean; passed: boolean };
  serving_status?: string;
};

export type DriverResponse = {
  model: string;
  sample_rows: number;
  global_shap: { feature: string; mean_absolute_shap: number }[];
  permutation_importance: { feature: string; importance_mean: number; importance_std: number }[];
  caution: string;
};

export type WhatIfResponse = {
  station_id: string;
  baseline_prediction: number;
  scenario_prediction: number;
  difference: number;
  interpretation: string;
};

