import { apiClient } from './client';
import type { TokenResponse, User } from './types';

export interface RegisterPayload {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UpdateUserPayload {
  display_name?: string;
  exam_date?: string | null;
}

export async function apiRegister(payload: RegisterPayload): Promise<User> {
  return apiClient<User>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true,
  });
}

export async function apiLogin(payload: LoginPayload): Promise<TokenResponse> {
  return apiClient<TokenResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true,
  });
}

export async function apiGetMe(): Promise<User> {
  return apiClient<User>('/api/me');
}

export async function apiUpdateMe(payload: UpdateUserPayload): Promise<User> {
  return apiClient<User>('/api/me', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
