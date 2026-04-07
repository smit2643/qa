'use client';

import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Terminal, Wifi, WifiOff, Circle } from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { WsEvent } from '@/lib/types';

interface LiveStreamProps {
  runId: string;
  onEvent?: (event: WsEvent) => void;
}

// ── Convert raw WebSocket event → readable log line ───────────────────────

interface LogLine {
  time: string;
  level: 'info' | 'success' | 'error' | 'warn' | 'dim';
  icon: string;
  text: string;
}

function toLogLine(event: WsEvent): LogLine {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  const ev = (event.event ?? event.type ?? '') as string;
  const testName = (event as Record<string, unknown>).test_name as string | undefined;
  const status   = (event as Record<string, unknown>).status   as string | undefined;
  const line     = (event as Record<string, unknown>).line     as string | undefined;
  const message  = (event as Record<string, unknown>).message  as string | undefined;
  const idx      = (event as Record<string, unknown>).test_index as number | undefined;
  const count    = (event as Record<string, unknown>).test_count as number | undefined;
  const hasAuth  = (event as Record<string, unknown>).has_auth as boolean | undefined;

  switch (ev) {
    case 'started':
    case 'test_start':
      return {
        time, level: 'info', icon: '▶',
        text: testName
          ? `Starting test: "${testName}"${idx !== undefined ? ` (${idx + 1} of ${count})` : ''}${hasAuth ? ' — reusing login session' : ''}`
          : 'Test run starting…',
      };

    case 'finished':
      if (status === 'passed') return { time, level: 'success', icon: '✓', text: testName ? `"${testName}" passed` : 'Test passed' };
      if (status === 'failed') return { time, level: 'error',   icon: '✗', text: testName ? `"${testName}" failed` : 'Test failed' };
      return { time, level: 'info', icon: '—', text: `Finished (${status})` };

    case 'run_finished':
    case 'run_passed':
      return { time, level: 'success', icon: '✓✓', text: `All tests complete — suite ${status ?? 'passed'}` };

    case 'run_failed':
      return { time, level: 'error', icon: '✗✗', text: 'Suite finished with failures' };

    case 'error':
      return { time, level: 'error', icon: '!', text: message ?? 'An error occurred' };

    case 'log': {
      if (!line) return { time, level: 'dim', icon: '·', text: '(empty log line)' };
      // Browser console logs — make them readable
      const clean = line
        .replace(/^\[info\]\s*/i, '')
        .replace(/^\[log\]\s*/i, '')
        .replace(/^\[warning\]\s*/i, '⚠ ')
        .replace(/^\[error\]\s*/i, '✗ ')
        .replace(/^\[pageerror\]\s*/i, '✗ Page error: ');
      const isError = line.startsWith('[error]') || line.startsWith('[pageerror]');
      const isWarn  = line.startsWith('[warning]');
      return {
        time,
        level: isError ? 'error' : isWarn ? 'warn' : 'dim',
        icon: isError ? '!' : isWarn ? '⚠' : '·',
        text: clean,
      };
    }

    default:
      // Fallback — show something sensible instead of raw JSON
      if (message) return { time, level: 'dim', icon: '·', text: message };
      if (testName) return { time, level: 'dim', icon: '·', text: `${ev}: ${testName}` };
      return { time, level: 'dim', icon: '·', text: ev };
  }
}

const LEVEL_COLORS: Record<LogLine['level'], string> = {
  success: 'text-green-400',
  error:   'text-red-400',
  warn:    'text-yellow-400',
  info:    'text-violet-400',
  dim:     'text-gray-500',
};

const ICON_COLORS: Record<LogLine['level'], string> = {
  success: 'text-green-500',
  error:   'text-red-500',
  warn:    'text-yellow-500',
  info:    'text-violet-500',
  dim:     'text-gray-700',
};

// ── Component ─────────────────────────────────────────────────────────────

export function LiveStream({ runId, onEvent }: LiveStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { events, connected, error } = useWebSocket(runId, { onEvent });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  const lines = events.map(toLogLine);

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#080808] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-gray-500" />
          <span className="text-xs font-medium text-gray-400">Live Log</span>
        </div>
        <div className="flex items-center gap-1.5">
          {connected ? (
            <>
              <motion.div
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
              >
                <Circle className="h-2 w-2 fill-green-400 text-green-400" />
              </motion.div>
              <span className="text-[11px] text-green-400">Live</span>
            </>
          ) : error ? (
            <>
              <WifiOff className="h-3 w-3 text-red-400" />
              <span className="text-[11px] text-red-400">Disconnected</span>
            </>
          ) : (
            <>
              <Wifi className="h-3 w-3 text-gray-500" />
              <span className="text-[11px] text-gray-500">Connecting…</span>
            </>
          )}
        </div>
      </div>

      {/* Log lines */}
      <div className="h-64 overflow-y-auto p-4 space-y-1 font-mono text-xs">
        {lines.length === 0 ? (
          <p className="text-gray-700">Waiting for test to start…</p>
        ) : (
          lines.map((line, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.1 }}
              className="flex items-baseline gap-2 leading-relaxed"
            >
              {/* Timestamp */}
              <span className="text-gray-700 flex-shrink-0 tabular-nums">{line.time}</span>

              {/* Icon */}
              <span className={`flex-shrink-0 w-4 text-center font-bold ${ICON_COLORS[line.level]}`}>
                {line.icon}
              </span>

              {/* Message */}
              <span className={`${LEVEL_COLORS[line.level]} break-all`}>
                {line.text}
              </span>
            </motion.div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
