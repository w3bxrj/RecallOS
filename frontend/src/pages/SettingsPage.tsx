import React, { useState, useEffect } from 'react';
import { User, Calendar, Save, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiUpdateMe } from '../api/auth';
import { useToast } from '../context/ToastContext';
import { Spinner } from '../components/common/Spinner';

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
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Account Settings
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Manage your personal details and exam schedule to calibrate the SM-2 engine.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs p-6 sm:p-8">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Email (Read-Only) */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Account Email
            </label>
            <input
              type="email"
              disabled
              value={user?.email || ''}
              className="block w-full px-3.5 py-2.5 sm:text-sm rounded-xl border border-slate-200 bg-slate-50 text-slate-500 cursor-not-allowed"
            />
            <p className="mt-1 text-xs text-slate-400">
              Email address cannot be changed once registered.
            </p>
          </div>

          {/* Display Name */}
          <div>
            <label htmlFor="displayName" className="block text-sm font-medium text-slate-700 mb-1">
              Display Name
            </label>
            <div className="relative rounded-xl shadow-xs">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <User className="w-4 h-4" />
              </div>
              <input
                id="displayName"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="block w-full pl-10 pr-3.5 py-2.5 sm:text-sm rounded-xl border border-slate-300 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                placeholder="Your full name"
                required
              />
            </div>
          </div>

          {/* Exam Date */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label htmlFor="examDate" className="block text-sm font-medium text-slate-700">
                Target Exam Date (Optional)
              </label>
              {examDate && (
                <button
                  type="button"
                  onClick={clearExamDate}
                  className="text-xs text-rose-600 hover:text-rose-700 font-medium"
                >
                  Clear exam date
                </button>
              )}
            </div>
            <div className="relative rounded-xl shadow-xs">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <Calendar className="w-4 h-4" />
              </div>
              <input
                id="examDate"
                type="date"
                value={examDate}
                onChange={(e) => setExamDate(e.target.value)}
                className="block w-full pl-10 pr-3.5 py-2.5 sm:text-sm rounded-xl border border-slate-300 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
              />
            </div>
            <p className="mt-1 text-xs text-slate-500 leading-relaxed">
              When an exam date is set, RecallOS activates <strong>Exam Mode</strong>: intervals are capped so all cards are reviewed before your exam, and weak topics receive higher daily priority.
            </p>
          </div>

          {/* Save Button */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm shadow-sm transition-colors disabled:opacity-60"
            >
              {isSaving ? (
                <>
                  <Spinner size="sm" className="text-white" />
                  <span>Saving...</span>
                </>
              ) : isSaved ? (
                <>
                  <Check className="w-4 h-4" />
                  <span>Saved</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Save changes</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
