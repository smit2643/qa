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
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { TestResult, TestCase } from '@/lib/types';
import { formatDuration, formatDate } from '@/lib/utils';

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
  const variantMap: Record<
    string,
    'success' | 'destructive' | 'running' | 'warning' | 'default'
  > = {
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

interface ResultRowProps {
  result: TestResult;
  testName?: string;
}

function ResultRow({ result, testName }: ResultRowProps) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = result.error_message || result.video_url;

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02]">
      <div
        className={`flex items-center gap-3 p-4 ${hasDetail ? 'cursor-pointer' : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        <StatusIcon status={result.status} />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-white text-sm truncate">
            {testName ?? `Test ${result.test_id.slice(0, 8)}...`}
          </p>
          <p className="text-xs text-gray-500">
            Duration: {formatDuration(result.duration_ms)}
          </p>
        </div>
        <StatusBadge status={result.status} />
        {hasDetail && (
          <button className="text-gray-500 hover:text-gray-300">
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
        )}
      </div>

      {expanded && hasDetail && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="border-t border-white/[0.06] p-4 space-y-3"
        >
          {result.error_message && (
            <div className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/5 p-3">
              <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-medium text-red-400 mb-1">Error</p>
                <pre className="text-xs text-red-300/80 whitespace-pre-wrap font-mono leading-relaxed">
                  {result.error_message}
                </pre>
              </div>
            </div>
          )}

          {result.video_url && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                <Video className="h-3.5 w-3.5" />
                Test Recording
              </div>
              <video
                src={result.video_url}
                controls
                className="w-full max-h-64 rounded-lg border border-white/10 bg-black"
              />
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
        <p className="mt-1 text-xs text-gray-600">
          Tests are still running...
        </p>
      </div>
    );
  }

  const passed = results.filter((r) => r.status === 'passed').length;
  const failed = results.filter(
    (r) => r.status === 'failed' || r.status === 'error'
  ).length;
  const pending = results.filter(
    (r) => r.status === 'pending' || r.status === 'running'
  ).length;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center gap-4 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
        <div className="flex items-center gap-1.5 text-sm">
          <CheckCircle className="h-4 w-4 text-green-400" />
          <span className="text-green-400 font-medium">{passed}</span>
          <span className="text-gray-500">passed</span>
        </div>
        <div className="flex items-center gap-1.5 text-sm">
          <XCircle className="h-4 w-4 text-red-400" />
          <span className="text-red-400 font-medium">{failed}</span>
          <span className="text-gray-500">failed</span>
        </div>
        {pending > 0 && (
          <div className="flex items-center gap-1.5 text-sm">
            <Clock className="h-4 w-4 text-yellow-400" />
            <span className="text-yellow-400 font-medium">{pending}</span>
            <span className="text-gray-500">pending</span>
          </div>
        )}
        <div className="ml-auto">
          {results.length > 0 && (
            <div className="flex h-2 w-32 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full bg-green-500 transition-all"
                style={{ width: `${(passed / results.length) * 100}%` }}
              />
              <div
                className="h-full bg-red-500 transition-all"
                style={{ width: `${(failed / results.length) * 100}%` }}
              />
            </div>
          )}
        </div>
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
            />
          </motion.div>
        ))}
      </div>
    </div>
  );
}
