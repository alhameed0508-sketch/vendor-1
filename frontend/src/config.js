// API
export const API_ALERTS_LIMIT = 100;
export const API_ALERTS_QUEUE_LIMIT = 50;
export const API_AUDIT_LIMIT = 20;
export const API_STR_LIMIT = 100;

// Polling & reconnection
export const ALERT_POLL_INTERVAL_MS = 10000;
export const SSE_INITIAL_RECONNECT_MS = 5000;
export const SSE_MAX_RECONNECT_MS = 60000;
export const SSE_BACKOFF_MULTIPLIER = 2;

// Auth
export const TOKEN_REFRESH_BUFFER_MS = 60000;
export const TOKEN_MIN_REFRESH_INTERVAL_MS = 30000;

// File upload
export const MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024;

// Score thresholds for UI
export const RISK_CRITICAL_THRESHOLD = 0.80;
export const RISK_HIGH_THRESHOLD = 0.60;
export const PRIORITY_CRITICAL_THRESHOLD = 0.75;
export const PRIORITY_HIGH_THRESHOLD = 0.50;
export const SCORE_BAR_CRITICAL = 0.70;
export const SCORE_BAR_HIGH = 0.40;
export const SAR_PROBABILITY_THRESHOLD = 0.60;
export const RISK_FILTER_THRESHOLD = 0.60;

// Priority calculation weights
export const PRIORITY_WEIGHT_RISK = 0.30;
export const PRIORITY_WEIGHT_AMOUNT = 0.20;
export const PRIORITY_WEIGHT_CENTRALITY = 0.20;
export const PRIORITY_WEIGHT_EVIDENCE = 0.15;
export const PRIORITY_WEIGHT_TIME = 0.15;

// Severity-to-priority mapping
export const SEVERITY_PRIORITY = {
  CRITICAL: 0.9,
  HIGH: 0.6,
  MEDIUM: 0.3,
  LOW: 0.1,
};

// Amount formatting
export const AMOUNT_DIVISOR_LAKHS = 100000;

// Animation
export const FLASH_ANIMATION_MS = 4000;
export const DEBOUNCE_MS = 500;
export const AMOUNT_NORMALIZATION_BASE = 1000000;
