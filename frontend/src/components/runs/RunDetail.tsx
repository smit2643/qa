'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  CheckCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Video,
  AlertTriangle,
  Terminal,
  ChevronRight,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { TestResult, TestCase } from '@/lib/types';
import { formatDuration } from '@/lib/utils';

interface RunDetailProps {
  results: TestResult[];
  testMap?: Record<string, TestCase>;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'passed':
      return <CheckCircle className="h-4 w-4 text-green-400 flex-shrink-0" />;
    case 'failed':
    case 'error':
      return <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />;
    default:
      return (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
        >
          <Clock className="h-4 w-4 text-yellow-400 flex-shrink-0" />
        </motion.div>
      );
  }
}

function StatusBadge({ status }: { status: string }) {
  const variantMap: Record<string, 'success' | 'destructive' | 'running' | 'warning' | 'default'> = {
    passed: 'success',
    failed: 'destructive',
    error: 'destructive',
    running: 'running',
    pending: 'warning',
  };
  return (
    <Badge variant={variantMap[status] ?? 'default'} className="capitalize text-xs">
      {status}
    </Badge>
  );
}

/** Pull the first meaningful error line — skip generic Python traceback boilerplate. */
function parseError(raw: string): { headline: string; detail: string } {
  const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean);

  // Find the last line that looks like an actual error (ExcType: message)
  const errorLine = [...lines].reverse().find(
    (l) => /^[A-Z][\w]+Error:|^Exception:|^TimeoutError:|^Could not|^Auth failed/i.test(l)
  );

  // Find the specific playwright/executor action that failed
  const actionLine = lines.find(
    (l) => l.startsWith('Could not') || l.startsWith('Auth failed') || l.startsWith('Login')
  );

  const headline = actionLine || errorLine || lines[lines.length - 1] || raw;

  // Full detail = everything after the headline for the collapsible section
  const detail = raw;

  return { headline, detail };
}

interface ResultRowProps {
  result: TestResult;
  testName?: string;
  index: number;
  total: number;
}

function ResultRow({ result, testName, index, total }: ResultRowProps) {
  const [expanded, setExpanded] = useState(result.status === 'failed' || result.status === 'error');
  const [showTrace, setShowTrace] = useState(false);
  const [showVideo, setShowVideo] = useState(false);

  const hasDetail = result.error_message || result.video_url;
  const error = result.error_message ? parseError(result.error_message) : null;

  return (
    <div className={`rounded-lg border transition-all ${
      result.status === 'passed'
        ? 'border-green-500/20 bg-green-500/[0.03]'
        : result.status === 'failed' || result.status === 'error'
        ? 'border-red-500/20 bg-red-500/[0.03]'
        : 'border-white/[0.06] bg-white/[0.02]'
    }`}>
      {/* Row header */}
      <div
        className={`flex items-center gap-3 p-4 ${hasDetail ? 'cursor-pointer' : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        {/* Step number badge */}
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[10px] font-bold text-gray-400">
          {index + 1}
        </div>

        <StatusIcon status={result.status} />

        <div className="min-w-0 flex-1">
          <p className="font-medium text-white text-sm truncate">
            {testName ?? `Test ${result.test_id.slice(0, 8)}…`}
          </p>
          <div className="flex items-center gap-3 mt-0.5">
            <span className="text-xs text-gray-500">{formatDuration(result.duration_ms)}</span>
            {total > 1 && (
              <span className="text-xs text-gray-600">
                Test {index + 1} of {total}
              </span>
            )}
            {/* Inline error headline — shown without expanding */}
            {error && !expanded && (
              <span className="text-xs text-red-400 truncate max-w-[280px]">
                {error.headline}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge status={result.status} />
          {result.video_url && !expanded && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(true); setShowVideo(true); }}
              className="flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-gray-300 hover:bg-white/[0.08] hover:text-white transition-all"
            >
              <Video className="h-3 w-3 text-violet-400" />
              Video
            </button>
          )}
          {hasDetail && (
            <button className="text-gray-500 hover:text-gray-300 transition-colors">
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && hasDetail && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="border-t border-white/[0.06] p-4 space-y-3"
        >
          {/* Error section */}
          {error && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/5 overflow-hidden">
              {/* Headline — always visible */}
              <div className="flex items-start gap-2 p-3">
                <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-red-400 mb-1">What went wrong</p>
                  <p className="text-sm text-red-300 leading-relaxed break-words">
                    {error.headline}
                  </p>
                </div>
              </div>

              {/* Full trace — collapsed by default */}
              <div className="border-t border-red-500/10">
                <button
                  onClick={() => setShowTrace(!showTrace)}
                  className="flex items-center gap-1.5 w-full px-3 py-2 text-xs text-gray-500 hover:text-gray-400 transition-colors"
                >
                  <Terminal className="h-3 w-3" />
                  {showTrace ? 'Hide' : 'Show'} full stack trace
                  <ChevronRight className={`h-3 w-3 ml-auto transition-transform ${showTrace ? 'rotate-90' : ''}`} />
                </button>
                {showTrace && (
                  <pre className="px-3 pb-3 text-xs text-red-300/70 whitespace-pre-wrap font-mono leading-relaxed max-h-64 overflow-y-auto">
                    {error.detail}
                  </pre>
                )}
              </div>
            </div>
          )}

          {/* Video section */}
          {result.video_url && (
            <div className="space-y-2">
              {!showVideo ? (
                <button
                  onClick={() => setShowVideo(true)}
                  className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-gray-300 hover:bg-white/[0.08] hover:text-white transition-all"
                >
                  <Video className="h-3.5 w-3.5 text-violet-400" />
                  Watch Recording
                </button>
              ) : (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs text-gray-400">
                      <Video className="h-3.5 w-3.5" />
                      Test Recording
                    </div>
                    <button
                      onClick={() => setShowVideo(false)}
                      className="text-xs text-gray-600 hover:text-gray-400"
                    >
                      Hide
                    </button>
                  </div>
                  <video
                    src={result.video_url}
                    controls
                    autoPlay
                    className="w-full max-h-72 rounded-lg border border-white/10 bg-black"
                  />
                </div>
              )}
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

export function RunDetail({ results, testMap = {} }: RunDetailProps) {
  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <Clock className="h-10 w-10 text-gray-700" />
        <p className="mt-3 text-sm text-gray-500">No results yet</p>
        <p className="mt-1 text-xs text-gray-600">Tests are queued and will appear here…</p>
      </div>
    );
  }

  const passed = results.filter((r) => r.status === 'passed').length;
  const failed = results.filter((r) => r.status === 'failed' || r.status === 'error').length;
  const pending = results.filter((r) => r.status === 'pending' || r.status === 'running').length;
  const passRate = results.length > 0 ? Math.round((passed / results.length) * 100) : 0;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 space-y-3">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-1.5 text-sm">
            <CheckCircle className="h-4 w-4 text-green-400" />
            <span className="text-green-400 font-semibold">{passed}</span>
            <span className="text-gray-500">passed</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm">
            <XCircle className="h-4 w-4 text-red-400" />
            <span className="text-red-400 font-semibold">{failed}</span>
            <span className="text-gray-500">failed</span>
          </div>
          {pending > 0 && (
            <div className="flex items-center gap-1.5 text-sm">
              <Clock className="h-4 w-4 text-yellow-400" />
              <span className="text-yellow-400 font-semibold">{pending}</span>
              <span className="text-gray-500">running</span>
            </div>
          )}
          <div className="ml-auto text-sm font-semibold text-gray-300">
            {passRate}% pass
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex h-2 w-full overflow-hidden rounded-full bg-white/10 gap-px">
          {results.map((r) => (
            <div
              key={r.id}
              className={`flex-1 h-full transition-all rounded-sm ${
                r.status === 'passed'
                  ? 'bg-green-500'
                  : r.status === 'failed' || r.status === 'error'
                  ? 'bg-red-500'
                  : r.status === 'running'
                  ? 'bg-yellow-400 animate-pulse'
                  : 'bg-white/20'
              }`}
              title={testMap[r.test_id]?.name ?? r.test_id}
            />
          ))}
        </div>

        {/* Sequential flow label */}
        {results.length > 1 && (
          <p className="text-xs text-gray-600">
            Tests run sequentially — each test shares the browser session from the previous test (no repeated logins).
          </p>
        )}
      </div>

      {/* Results list */}
      <div className="space-y-2">
        {results.map((result, i) => (
          <motion.div
            key={result.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
          >
            <ResultRow
              result={result}
              testName={testMap[result.test_id]?.name}
              index={i}
              total={results.length}
            />
          </motion.div>
        ))}
      </div>
    </div>
  );
}
