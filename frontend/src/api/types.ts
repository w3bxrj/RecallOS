// Shared API Data Transfer Objects and Error Types

export interface ApiErrorPayload {
  code: string;
  message: string;
  deck_id?: number;
  job_id?: number;
  [key: string]: unknown;
}

export class ApiClientError extends Error {
  status: number;
  code: string;
  details?: ApiErrorPayload;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message || `Request failed with HTTP status ${status}`);
    this.name = 'ApiClientError';
    this.status = status;
    this.code = payload.code || 'UNKNOWN_ERROR';
    this.details = payload;
  }
}

export interface User {
  id: number;
  email: string;
  display_name: string;
  exam_date: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface DeckListItem {
  id: number;
  title: string;
  source_filename: string;
  card_count: number;
  created_at: string;
}

export interface Card {
  id: number;
  deck_id: number;
  topic: string;
  question: string;
  answer: string;
  distractors?: string[];
  created_at: string;
}

export type JobStatus = 'queued' | 'processing' | 'ready' | 'failed';

export interface JobResponse {
  id: number;
  deck_id: number;
  status: JobStatus;
  total_chunks: number;
  done_chunks: number;
  cards_created: number;
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface UploadResponse {
  job_id: number;
  deck_id: number;
  status: string;
  message: string;
}

export interface PredictedIntervals {
  again: number;
  hard: number;
  good: number;
  easy: number;
}

export interface QueueCardItem {
  card_id: number;
  deck_id: number;
  topic: string;
  question: string;
  answer: string;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
  due_date: string;
  lapses: number;
  predicted_intervals: PredictedIntervals;
  priority_score?: number | null;
}

export interface QueueResponse {
  cards: QueueCardItem[];
  total_due: number;
  remaining_count: number;
}

export interface ReviewSubmitRequest {
  card_id: number;
  rating: 1 | 2 | 3 | 4;
  request_id?: string;
}

export interface ReviewSubmitResponse {
  card_id: number;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
  due_date: string;
  last_reviewed_at?: string;
  lapses: number;
  prev_interval: number;
  new_interval: number;
}

export interface DailyReviewCount {
  date: string;
  count: number;
}

export interface StatsOverviewResponse {
  due_today: number;
  queue_size_today: number;
  daily_limit: number;
  total_cards: number;
  reviews_last_7_days: DailyReviewCount[];
  streak_days: number;
  expected_retention_on_exam: number | null;
  exam_date: string | null;
  days_to_exam: number | null;
}

export interface TopicAccuracyItem {
  topic: string;
  accuracy: number | null;
  reviews_count: number;
  is_weak: boolean;
}

export interface ForecastItem {
  date: string;
  due_count: number;
}

export interface ForecastResponse {
  forecast: ForecastItem[];
}

