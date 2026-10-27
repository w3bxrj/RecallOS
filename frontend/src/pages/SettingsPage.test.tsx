import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import {
  SettingsPage,
  normalizeExamDate,
  getTomorrowIST,
  isPastDate,
  saveSettingsAction,
  clearExamDateAction,
} from './SettingsPage';

let mockUser: {
  id: number;
  email: string;
  display_name: string;
  exam_date: string | null;
  created_at: string;
} | null = null;

const mockRefreshUser = vi.fn().mockResolvedValue(undefined);

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    refreshUser: mockRefreshUser,
  }),
}));

vi.mock('../context/ToastContext', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

describe('SettingsPage - Exam Date and User Profile', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = null;
  });

  describe('normalizeExamDate helper', () => {
    it('preserves clean YYYY-MM-DD string without UTC shift', () => {
      expect(normalizeExamDate('2026-11-15')).toBe('2026-11-15');
    });

    it('extracts plain YYYY-MM-DD from API ISO datetime strings without Date UTC conversion', () => {
      expect(normalizeExamDate('2026-11-15T09:30:00Z')).toBe('2026-11-15');
      expect(normalizeExamDate('2026-11-15T00:00:00')).toBe('2026-11-15');
    });

    it('returns empty string for null, undefined, or empty values', () => {
      expect(normalizeExamDate(null)).toBe('');
      expect(normalizeExamDate(undefined)).toBe('');
      expect(normalizeExamDate('')).toBe('');
    });
  });

  describe('getTomorrowIST and isPastDate helpers', () => {
    it('calculates tomorrow in IST formatted as YYYY-MM-DD', () => {
      const tomorrow = getTomorrowIST();
      expect(tomorrow).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('identifies past dates correctly against minDate', () => {
      const minDate = '2026-10-28';
      expect(isPastDate('2026-10-27', minDate)).toBe(true);
      expect(isPastDate('2020-01-01', minDate)).toBe(true);
      expect(isPastDate('2026-10-28', minDate)).toBe(false);
      expect(isPastDate('2026-11-15', minDate)).toBe(false);
      expect(isPastDate('', minDate)).toBe(false);
    });
  });

  describe('HTML Rendering from user object', () => {
    it('initialises the input from user.exam_date (plain string)', () => {
      mockUser = {
        id: 1,
        email: 'student@example.com',
        display_name: 'Alex Student',
        exam_date: '2026-11-20',
        created_at: '2026-01-01T00:00:00Z',
      };

      const html = renderToString(<SettingsPage />);

      // The input should render value="2026-11-20"
      expect(html).toContain('value="2026-11-20"');
      // The input should have min set to tomorrow in IST
      const tomorrow = getTomorrowIST();
      expect(html).toContain(`min="${tomorrow}"`);
      // Clear exam date button should be visible when date is set
      expect(html).toContain('Clear exam date');
    });

    it('normalizes ISO datetime string to YYYY-MM-DD in the input value', () => {
      mockUser = {
        id: 2,
        email: 'scholar@example.com',
        display_name: 'Sam Scholar',
        exam_date: '2026-12-25T14:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
      };

      const html = renderToString(<SettingsPage />);
      expect(html).toContain('value="2026-12-25"');
    });

    it('renders empty input value and hides clear button when exam_date is null', () => {
      mockUser = {
        id: 3,
        email: 'noexam@example.com',
        display_name: 'No Exam User',
        exam_date: null,
        created_at: '2026-01-01T00:00:00Z',
      };

      const html = renderToString(<SettingsPage />);
      expect(html).toContain('id="examDate"');
      expect(html).toContain('value=""');
      expect(html).not.toContain('Clear exam date');
    });

    it('shows inline error message when user exam date is in the past', () => {
      mockUser = {
        id: 4,
        email: 'past@example.com',
        display_name: 'Past Exam User',
        exam_date: '2020-05-10',
        created_at: '2026-01-01T00:00:00Z',
      };

      const html = renderToString(<SettingsPage />);
      expect(html).toContain('Target exam date is in the past. Please select tomorrow or a future date.');
      expect(html).toContain('aria-invalid="true"');
    });
  });

  describe('Saving and Clearing API calls', () => {
    it('saving a date sends the plain YYYY-MM-DD string and refreshes user', async () => {
      const mockApiUpdate = vi.fn().mockResolvedValue({
        id: 1,
        email: 'student@example.com',
        display_name: 'Alex Student',
        exam_date: '2026-11-20',
        created_at: '2026-01-01T00:00:00Z',
      });
      const refreshFn = vi.fn().mockResolvedValue(undefined);
      const toastSuccess = vi.fn();
      const toastError = vi.fn();

      const success = await saveSettingsAction({
        displayName: 'Alex Student',
        examDate: '2026-11-20',
        minDate: '2026-10-28',
        apiUpdate: mockApiUpdate,
        refreshUser: refreshFn,
        toast: { success: toastSuccess, error: toastError },
      });

      expect(success).toBe(true);
      expect(mockApiUpdate).toHaveBeenCalledTimes(1);
      expect(mockApiUpdate).toHaveBeenCalledWith({
        display_name: 'Alex Student',
        exam_date: '2026-11-20',
      });
      expect(refreshFn).toHaveBeenCalledTimes(1);
      expect(toastSuccess).toHaveBeenCalledWith('Settings updated successfully');
    });

    it('clearing exam date sends null and refreshes user', async () => {
      const mockApiUpdate = vi.fn().mockResolvedValue({
        id: 1,
        email: 'student@example.com',
        display_name: 'Alex Student',
        exam_date: null,
        created_at: '2026-01-01T00:00:00Z',
      });
      const refreshFn = vi.fn().mockResolvedValue(undefined);
      const toastSuccess = vi.fn();
      const toastError = vi.fn();

      const success = await clearExamDateAction({
        displayName: 'Alex Student',
        apiUpdate: mockApiUpdate,
        refreshUser: refreshFn,
        toast: { success: toastSuccess, error: toastError },
      });

      expect(success).toBe(true);
      expect(mockApiUpdate).toHaveBeenCalledTimes(1);
      expect(mockApiUpdate).toHaveBeenCalledWith({
        display_name: 'Alex Student',
        exam_date: null,
      });
      expect(refreshFn).toHaveBeenCalledTimes(1);
      expect(toastSuccess).toHaveBeenCalledWith('Exam date cleared');
    });

    it('saving with an empty examDate string sends null and refreshes user', async () => {
      const mockApiUpdate = vi.fn().mockResolvedValue({
        id: 1,
        email: 'student@example.com',
        display_name: 'Alex Student',
        exam_date: null,
        created_at: '2026-01-01T00:00:00Z',
      });
      const refreshFn = vi.fn().mockResolvedValue(undefined);

      const success = await saveSettingsAction({
        displayName: 'Alex Student',
        examDate: '',
        minDate: '2026-10-28',
        apiUpdate: mockApiUpdate,
        refreshUser: refreshFn,
      });

      expect(success).toBe(true);
      expect(mockApiUpdate).toHaveBeenCalledWith({
        display_name: 'Alex Student',
        exam_date: null,
      });
      expect(refreshFn).toHaveBeenCalledTimes(1);
    });

    it('blocks saving and alerts when exam date is in the past', async () => {
      const mockApiUpdate = vi.fn();
      const refreshFn = vi.fn();
      const toastError = vi.fn();

      const success = await saveSettingsAction({
        displayName: 'Alex Student',
        examDate: '2025-01-01',
        minDate: '2026-10-28',
        apiUpdate: mockApiUpdate,
        refreshUser: refreshFn,
        toast: { success: vi.fn(), error: toastError },
      });

      expect(success).toBe(false);
      expect(mockApiUpdate).not.toHaveBeenCalled();
      expect(refreshFn).not.toHaveBeenCalled();
      expect(toastError).toHaveBeenCalledWith(
        'Target exam date is in the past. Please select tomorrow or a future date.'
      );
    });
  });
});
