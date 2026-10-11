export type OptionsPayload = {
  scenario_controls: string[];
  origins: string[];
  markets: string[];
  unserved_markets: string[];
  minimum_date: string;
  maximum_date: string;
  default_origin: string;
  default_market: string;
  route_baselines: Record<string, {
    weekly_flights: number;
    load_factor: number;
    transfer_share: number;
    transit_share: number;
  }>;
  default_scenario: {
    baseline_weekly_flights: number;
    scenario_weekly_flights: number;
    transfer_share: number;
    transit_share: number;
    visitor_share: number;
    hotel_capture_rate: number;
    nationality_allocation_share: number;
  };
};

export type SensitivityPayload = {
  base: number;
  drivers: Array<{
    driver: string;
    perturbation: string;
    low: number;
    base: number;
    high: number;
    downside: number;
    upside: number;
    swing: number;
  }>;
};

export type GlobalSensitivityPayload = {
  method: string;
  output: string;
  trajectories: number;
  evaluations: number;
  interpretation: string;
  drivers: Array<{
    rank: number;
    driver: string;
    parameter: string;
    bounds: [number, number];
    mu: number;
    mu_star: number;
    mu_star_conf: number;
    sigma: number;
    relative_importance: number;
  }>;
};

export type ChainStage = {
  stage: string;
  baseline: number;
  scenario: number;
  change: number;
  source: string;
};

export type SimulationPayload = {
  mode: "Existing route" | "New route";
  origin_country: string;
  target_nationality: string;
  start_date: string;
  end_date: string;
  baseline_weekly_flights: number;
  scenario_weekly_flights: number;
  baseline_predicted_guests: number;
  scenario_predicted_guests: number;
  baseline_guest_nights: number;
  scenario_guest_nights: number;
  selected_market_baseline_nights: number;
  selected_market_scenario_nights: number;
  planning_range_low: number;
  planning_range_high: number;
  scenario_load_factor: number;
  transfer_share: number;
  transit_share: number;
  visitor_share: number;
  hotel_capture_rate: number;
  nationality_allocation_share: number;
  chain: ChainStage[];
  monthly: Array<{ month: string; baseline: number; scenario: number }>;
  checks: Array<{ level: string; message: string }>;
  metrics: Record<string, { wmape: number; bias_pct: number; rmse: number }>;
  model_version: string;
};
