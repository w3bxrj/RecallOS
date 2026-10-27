import React, { useState, useEffect } from 'react';
import { User, Calendar, Save, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiUpdateMe } from '../api/auth';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/ui/Button';

/**
 * Normalizes an exam_date from the API into a clean "YYYY-MM-DD" string.
 * Never uses new Date().toISOString() or UTC conversions to prevent day shifting.
 */
export function normalizeExamDate(raw?: string | null): string {
  if (!raw) return '';
  const match = String(raw).trim().match(/^\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : '';
}

/**
 * Returns tomorrow's date formatted as "YYYY-MM-DD" in Indian Standard Time (Asia/Kolkata).
 */
export function getTomorrowIST(): string {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  const todayStr = formatter.format(new Date());
  const [y, m, d] = todayStr.split('-').map(Number);
  const nextDay = new Date(Date.UTC(y, m - 1, d + 1));
  const yyyy = nextDay.getUTCFullYear();
  const mm = String(nextDay.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(nextDay.getUTCDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * Checks if a given YYYY-MM-DD date is strictly before minDate (tomorrow in IST).
 */
export function isPastDate(dateStr: string, minDate: string): boolean {
  if (!dateStr || !minDate) return false;
  return dateStr < minDate;
}

export interface SaveSettingsParams {
  displayName: string;
  examDate: string;
  minDate: string;
  apiUpdate?: typeof apiUpdateMe;
  refreshUser?: () => Promise<void>;
  toast?: {
    success: (msg: string) => void;
    error: (msg: string) => void;
  };
}

export async function saveSettingsAction({
  displayName,
  examDate,
  minDate,
  apiUpdate = apiUpdateMe,
  refreshUser,
  toast,
}: SaveSettingsParams): Promise<boolean> {
  if (!displayName.trim()) {
    toast?.error('Display name cannot be empty');
    return false;
  }

  if (examDate && isPastDate(examDate, minDate)) {
    toast?.error('Target exam date is in the past. Please select tomorrow or a future date.');
    return false;
  }

  try {
    await apiUpdate({
      display_name: displayName.trim(),
      exam_date: examDate ? examDate : null,
    });
    if (refreshUser) {
      await refreshUser();
    }
    toast?.success('Settings updated successfully');
    return true;
  } catch {
    toast?.error('Failed to update settings. Please try again.');
    return false;
  }
}

export interface ClearExamDateParams {
  displayName: string;
  apiUpdate?: typeof apiUpdateMe;
  refreshUser?: () => Promise<void>;
  toast?: {
    success: (msg: string) => void;
    error: (msg: string) => void;
  };
}

export async function clearExamDateAction({
  displayName,
  apiUpdate = apiUpdateMe,
  refreshUser,
  toast,
}: ClearExamDateParams): Promise<boolean> {
  try {
    await apiUpdate({
      display_name: displayName.trim(),
      exam_date: null,
    });
    if (refreshUser) {
      await refreshUser();
    }
    toast?.success('Exam date cleared');
    return true;
  } catch {
    toast?.error('Failed to clear exam date. Please try again.');
    return false;
  }
}

export const SettingsPage: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const toast = useToast();

  const [displayName, setDisplayName] = useState(() => user?.display_name || '');
  const [examDate, setExamDate] = useState(() => normalizeExamDate(user?.exam_date));
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

  // Set min to tomorrow in IST
  const minDate = getTomorrowIST();
  const hasPastDate = Boolean(examDate && isPastDate(examDate, minDate));

  // Re-initialise when user arrives or changes
  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name || '');
      setExamDate(normalizeExamDate(user.exam_date));
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setIsSaved(false);

    try {
      const ok = await saveSettingsAction({
        displayName,
        examDate,
        minDate,
        refreshUser,
        toast,
      });
      if (ok) {
        setIsSaved(true);
        setTimeout(() => setIsSaved(false), 3000);
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearExamDate = async () => {
    setExamDate('');
    setIsSaving(true);
    try {
      await clearExamDateAction({
        displayName: displayName || user?.display_name || '',
        refreshUser,
        toast,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in pb-12">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-txt-primary">
          Account Settings
        </h1>
        <p className="text-sm text-txt-muted mt-1">
          Manage your personal details and exam schedule to calibrate the SM-2 engine.
        </p>
      </div>

      <div className="bg-surface rounded-2xl border border-border-subtle shadow-card p-6 sm:p-8">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Email (Read-Only) */}
          <div>
            <label className="block text-xs font-semibold text-txt-secondary uppercase tracking-wide mb-1.5">
              Account Email
            </label>
            <input
              type="email"
              disabled
              value={user?.email || ''}
              className="block w-full px-3.5 py-2.5 text-sm rounded-xl border border-border-subtle bg-surface-muted text-txt-muted cursor-not-allowed"
            />
            <p className="mt-1 text-xs text-txt-muted">
              Email address cannot be changed once registered.
            </p>
          </div>

          {/* Display Name */}
          <div>
            <label
              htmlFor="displayName"
              className="block text-xs font-semibold text-txt-secondary uppercase tracking-wide mb-1.5"
            >
              Display Name
            </label>
            <div className="relative rounded-xl shadow-xs">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-txt-muted">
                <User className="w-4 h-4" />
              </div>
              <input
                id="displayName"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="block w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border border-border-subtle bg-surface text-txt-primary placeholder:text-txt-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand transition-colors"
                placeholder="Your full name"
                required
              />
            </div>
          </div>

          {/* Exam Date */}
          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label
                htmlFor="examDate"
                className="block text-xs font-semibold text-txt-secondary uppercase tracking-wide"
              >
                Target Exam Date (Optional)
              </label>
              {examDate && (
                <button
                  type="button"
                  onClick={handleClearExamDate}
                  disabled={isSaving}
                  className="text-xs text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer disabled:opacity-50"
                  aria-label="Clear target exam date"
                >
                  Clear exam date
                </button>
              )}
            </div>
            <div className="relative rounded-xl shadow-xs">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-txt-muted">
                <Calendar className="w-4 h-4" />
              </div>
              <input
                id="examDate"
                type="date"
                min={minDate}
                value={examDate}
                onChange={(e) => setExamDate(e.target.value)}
                aria-invalid={hasPastDate}
                className={`block w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border bg-surface text-txt-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand transition-colors [color-scheme:light] dark:[color-scheme:dark] ${
                  hasPastDate
                    ? 'border-rose-400 dark:border-rose-600 focus-visible:ring-rose-400'
                    : 'border-border-subtle'
                }`}
              />
            </div>
            {hasPastDate && (
              <p
                id="examDateError"
                className="mt-1.5 text-xs text-rose-600 dark:text-rose-400 font-medium flex items-center gap-1.5"
                role="alert"
              >
                <span>Target exam date is in the past. Please select tomorrow or a future date.</span>
              </p>
            )}
            <p className="mt-1.5 text-xs text-txt-muted leading-relaxed">
              When an exam date is set, RecallOS activates <strong>Exam Mode</strong>: intervals are capped so all cards are reviewed before your exam, and weak topics receive higher daily priority.
            </p>
          </div>

          {/* Save Button */}
          <div className="pt-4 border-t border-border-subtle flex items-center justify-end gap-3">
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isSaving}
              leftIcon={isSaved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            >
              {isSaved ? 'Saved' : 'Save changes'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
