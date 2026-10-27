import React, { useState, useEffect } from 'react';
import { User, Calendar, Save, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiUpdateMe } from '../api/auth';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/ui/Button';

export const SettingsPage: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const toast = useToast();

  const [displayName, setDisplayName] = useState('');
  const [examDate, setExamDate] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name || '');
      setExamDate(user.exam_date || '');
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName.trim()) {
      toast.error('Display name cannot be empty');
      return;
    }

    setIsSaving(true);
    setIsSaved(false);

    try {
      await apiUpdateMe({
        display_name: displayName.trim(),
        exam_date: examDate ? examDate : null,
      });
      await refreshUser();
      setIsSaved(true);
      toast.success('Settings updated successfully');
      setTimeout(() => setIsSaved(false), 3000);
    } catch {
      toast.error('Failed to update settings. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const clearExamDate = () => {
    setExamDate('');
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
                  onClick={clearExamDate}
                  className="text-xs text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer"
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
                value={examDate}
                onChange={(e) => setExamDate(e.target.value)}
                className="block w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border border-border-subtle bg-surface text-txt-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand transition-colors [color-scheme:light] dark:[color-scheme:dark]"
              />
            </div>
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
