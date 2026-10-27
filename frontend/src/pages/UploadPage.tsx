import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  RotateCcw,
  BookOpen,
  Layers,
  Sparkles,
  WifiOff,
} from 'lucide-react';
import { apiUploadDocument } from '../api/upload';
import { ApiClientError } from '../api/types';
import { useGenerationJob } from '../hooks/useGenerationJob';
import { calculateProgress } from '../hooks/generationJobState';
import { Spinner } from '../components/common/Spinner';

export const UploadPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const jobParam = searchParams.get('job');
  const activeJobId = jobParam ? parseInt(jobParam, 10) : null;

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<{
    code?: string;
    message: string;
    deck_id?: number;
    job_id?: number;
  } | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Hook for tracking the live generation job
  const generation = useGenerationJob(activeJobId);

  // Clear upload errors when file changes
  useEffect(() => {
    setUploadError(null);
  }, [file]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    const name = selectedFile.name.toLowerCase();
    if (!name.endsWith('.pdf') && !name.endsWith('.txt')) {
      setUploadError({
        message: 'Invalid file type. Only PDF (.pdf) and Text (.txt) files are supported.',
      });
      return;
    }

    const maxBytes = 10 * 1024 * 1024; // 10MB limit
    if (selectedFile.size > maxBytes) {
      setUploadError({
        message: 'File exceeds maximum upload size of 10 MB.',
      });
      return;
    }

    if (selectedFile.size === 0) {
      setUploadError({
        message: 'The selected file is empty. Please choose a valid document.',
      });
      return;
    }

    setFile(selectedFile);
    setUploadError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setUploadError({ message: 'Please select or drop a file to upload.' });
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      const res = await apiUploadDocument(file, title);
      // Persist job id in URL query params
      setSearchParams({ job: String(res.job_id) });
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setUploadError({
          code: err.code,
          message: err.message,
          deck_id: err.details?.deck_id,
          job_id: err.details?.job_id,
        });
      } else {
        setUploadError({
          message: 'Failed to upload document. Please try again.',
        });
      }
    } finally {
      setIsUploading(false);
    }
  };

  const resetUpload = () => {
    setFile(null);
    setTitle('');
    setUploadError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setSearchParams({});
    navigate('/upload', { replace: true });
  };

  // -------------------------------------------------------------
  // Live Generation View (when activeJobId is set)
  // -------------------------------------------------------------
  if (activeJobId) {
    const isReady = generation.status === 'ready';
    const isFailed = generation.status === 'failed';
    const { percent, chunkText, isValid: hasValidChunks } = calculateProgress(
      generation.doneChunks,
      generation.totalChunks,
      isReady
    );
    const safeCardsCreated = Number.isFinite(generation.cardsCreated) ? generation.cardsCreated : 0;

    return (
      <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
        {/* Header Status Card */}
        <div className="bg-white rounded-3xl border border-slate-200/80 shadow-md p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                  <span>Job #{activeJobId}</span>
                </div>
                {generation.isVision && (
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                    <span>Reading scanned pages...</span>
                  </div>
                )}
              </div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {isReady
                  ? 'Flashcards Generated!'
                  : isFailed
                  ? 'Generation Encountered an Error'
                  : 'Generating Flashcards with AI...'}
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                {isReady
                  ? `Completed! Created ${safeCardsCreated} cards ready for spaced repetition.`
                  : isFailed
                  ? generation.errorMessage || 'The generation job could not be completed.'
                  : hasValidChunks
                  ? (generation.isVision
                      ? `Reading scanned pages (${chunkText.toLowerCase()})...`
                      : `Processing ${chunkText.toLowerCase()}...`)
                  : 'Starting...'}
              </p>
            </div>

            {generation.isPollingFallback && !isReady && !isFailed && (
              <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-50 text-amber-800 text-xs font-medium border border-amber-200/60 shrink-0">
                <WifiOff className="w-3.5 h-3.5 text-amber-600" />
                <span>Live stream paused — syncing via polling</span>
              </div>
            )}
          </div>

          {/* Page Cap / Processing Notice */}
          {generation.notice && (
            <div className="mb-6 p-4 bg-amber-50/90 rounded-2xl border border-amber-200 text-xs text-amber-900 flex items-center gap-2.5 shadow-xs">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
              <span className="font-medium">{generation.notice}</span>
            </div>
          )}

          {/* Progress Bar */}
          {!isFailed && (
            <div className="space-y-2 mb-6">
              <div className="flex justify-between text-xs font-semibold text-slate-600">
                <span>{chunkText}</span>
                <span>{safeCardsCreated} cards created</span>
              </div>
              <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden p-0.5 border border-slate-200">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    isReady ? 'bg-emerald-500' : 'bg-indigo-600'
                  }`}
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
          )}

          {/* Action Buttons on Ready / Failed */}
          {isReady && (
            <div className="pt-4 border-t border-slate-100 flex flex-wrap gap-3">
              <Link
                to="/review"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm shadow-md shadow-indigo-100 transition-colors"
              >
                <BookOpen className="w-4 h-4" />
                <span>Start reviewing</span>
              </Link>
              <Link
                to="/decks"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm transition-colors"
              >
                <Layers className="w-4 h-4" />
                <span>View deck</span>
              </Link>
              <button
                type="button"
                onClick={resetUpload}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-slate-500 hover:text-slate-700 text-sm font-medium transition-colors ml-auto"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Upload Another</span>
              </button>
            </div>
          )}

          {isFailed && (
            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <p className="text-sm text-rose-600 font-medium">
                {generation.errorMessage || 'Generation failed. You may retry uploading.'}
              </p>
              <button
                type="button"
                onClick={resetUpload}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-sm font-semibold transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Retry</span>
              </button>
            </div>
          )}
        </div>

        {/* Chunk Warning Banners */}
        {generation.warnings.length > 0 && (
          <div className="bg-amber-50 rounded-2xl p-4 border border-amber-200 space-y-1.5 text-xs text-amber-900">
            <div className="flex items-center gap-2 font-semibold text-amber-800">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span>Some chunks could not produce valid cards:</span>
            </div>
            {generation.warnings.map((warn, i) => (
              <div key={i} className="pl-6 text-amber-700">
                • {warn}
              </div>
            ))}
          </div>
        )}

        {/* Live Streaming Cards List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-800">
              Live Flashcards Feed ({generation.cards.length})
            </h2>
            {!isReady && !isFailed && (
              <div className="flex items-center gap-2 text-xs text-indigo-600 font-medium">
                <Spinner size="sm" />
                <span>Streaming live cards...</span>
              </div>
            )}
          </div>

          {generation.cards.length === 0 ? (
            <div className="p-8 text-center bg-white rounded-2xl border border-slate-200 text-slate-400 text-sm">
              Waiting for first card chunk to finish processing...
            </div>
          ) : (
            <div className="space-y-3">
              {generation.cards.map((card, idx) => (
                <div
                  key={card.id || idx}
                  className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs transition-all hover:shadow-sm animate-slide-up"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100">
                      {card.topic}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">#{idx + 1}</span>
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900 mb-1.5">
                    {card.question}
                  </h3>
                  <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                    <span className="font-semibold text-slate-700">Answer: </span>
                    {card.answer}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // Initial Upload Form View
  // -------------------------------------------------------------
  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Upload Study Material
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Upload scanned PDFs, textbook notes, or TXT study guides. RecallOS will generate spaced repetition flashcards automatically.
        </p>
      </div>

      {/* 409 DUPLICATE_FILE Error Callout */}
      {uploadError?.code === 'DUPLICATE_FILE' && (
        <div className="bg-amber-50 rounded-2xl p-5 border border-amber-200 text-amber-900 text-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Document Already Uploaded</p>
              <p className="text-xs text-amber-700 mt-0.5">
                You have already generated flashcards for this exact file.
              </p>
            </div>
          </div>
          <Link
            to="/decks"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs shadow-xs shrink-0 transition-colors"
          >
            <span>View existing deck</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* 409 JOB_IN_PROGRESS Error Callout */}
      {uploadError?.code === 'JOB_IN_PROGRESS' && (
        <div className="bg-indigo-50 rounded-2xl p-5 border border-indigo-200 text-indigo-900 text-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Generation Job Already Running</p>
              <p className="text-xs text-indigo-700 mt-0.5">
                You currently have a document generation job in progress.
              </p>
            </div>
          </div>
          {uploadError.job_id && (
            <button
              onClick={() => setSearchParams({ job: String(uploadError.job_id) })}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-xs shrink-0 transition-colors"
            >
              <span>Resume live view</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}

      {/* Standard Error Notice */}
      {uploadError &&
        uploadError.code !== 'DUPLICATE_FILE' &&
        uploadError.code !== 'JOB_IN_PROGRESS' && (
          <div className="bg-rose-50 rounded-2xl p-4 border border-rose-200 text-rose-900 text-sm flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <span>{uploadError.message}</span>
          </div>
        )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Drag and Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`relative border-2 border-dashed rounded-3xl p-8 sm:p-12 text-center cursor-pointer transition-all duration-200 ${
            isDragging
              ? 'border-indigo-500 bg-indigo-50/60 scale-[1.01]'
              : file
              ? 'border-emerald-300 bg-emerald-50/30'
              : 'border-slate-300 hover:border-indigo-400 bg-white hover:bg-slate-50/50'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt"
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="flex flex-col items-center justify-center">
            {file ? (
              <div className="flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mb-3 shadow-xs">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <p className="text-base font-semibold text-slate-800">{file.name}</p>
                <p className="text-xs text-slate-500 mt-1">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB • Click to replace file
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3 shadow-xs">
                  <UploadCloud className="w-8 h-8" />
                </div>
                <p className="text-base font-semibold text-slate-800">
                  Drag and drop your document here
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  or <span className="text-indigo-600 font-medium">browse files</span> from your device
                </p>
                <p className="text-xs text-slate-500 mt-3 font-medium max-w-md">
                  Text-based and scanned PDFs are both supported (scanned ones take longer, about 10 to 20 seconds per 4 pages). UTF-8 Text (.txt) also supported • Max 10 MB
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Optional Title Field */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-4">
          <div>
            <label htmlFor="deckTitle" className="block text-sm font-medium text-slate-700 mb-1">
              Deck Title (Optional)
            </label>
            <div className="relative rounded-xl shadow-xs">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <FileText className="w-4 h-4" />
              </div>
              <input
                id="deckTitle"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={file ? file.name.replace(/\.[^/.]+$/, '') : 'e.g. Distributed Systems Chapter 4'}
                className="block w-full pl-10 pr-3.5 py-2.5 sm:text-sm rounded-xl border border-slate-300 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
              />
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Leave blank to automatically use the file's original name.
            </p>
          </div>

          <div className="pt-2 flex justify-end">
            <button
              type="submit"
              disabled={!file || isUploading}
              className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm shadow-md shadow-indigo-100 transition-all disabled:opacity-50"
            >
              {isUploading ? (
                <>
                  <Spinner size="sm" className="text-white" />
                  <span>Uploading & Enqueuing...</span>
                </>
              ) : (
                <>
                  <span>Generate Flashcards</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};
