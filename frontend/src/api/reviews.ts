import { apiClient } from './client';
import type { QueueResponse, ReviewSubmitRequest, ReviewSubmitResponse } from './types';

export async function apiGetReviewQueue(): Promise<QueueResponse> {
  return apiClient<QueueResponse>('/api/reviews/queue');
}

export async function apiSubmitReview(payload: ReviewSubmitRequest): Promise<ReviewSubmitResponse> {
  return apiClient<ReviewSubmitResponse>('/api/reviews', {
    method: 'POST',
    body: JSON.stringify(payload),
    isReviewSubmit: true, // safe to retry on wake-up because it contains request_id
  });
}
