import { apiClient } from './client';
import type { StatsOverviewResponse, TopicAccuracyItem, ForecastResponse } from './types';

export async function apiGetStatsOverview(): Promise<StatsOverviewResponse> {
  return apiClient<StatsOverviewResponse>('/api/stats/overview');
}

export async function apiGetStatsTopics(): Promise<TopicAccuracyItem[]> {
  return apiClient<TopicAccuracyItem[]>('/api/stats/topics');
}

export async function apiGetStatsForecast(): Promise<ForecastResponse> {
  return apiClient<ForecastResponse>('/api/stats/forecast');
}
