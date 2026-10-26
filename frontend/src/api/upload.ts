import { apiClient } from './client';
import { JobResponse, UploadResponse } from './types';

export async function apiUploadDocument(file: File, title?: string): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (title && title.trim()) {
    formData.append('title', title.trim());
  }

  return apiClient<UploadResponse>('/api/uploads', {
    method: 'POST',
    body: formData,
  });
}

export async function apiGetJobStatus(jobId: number): Promise<JobResponse> {
  return apiClient<JobResponse>(`/api/jobs/${jobId}`);
}
