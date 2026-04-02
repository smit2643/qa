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

function getEventColor(type: string): string {
  switch (type) {
    case 'test_passed':
    case 'run_passed':
    case 'success':
      return 'text-green-400';
    case 'test_failed':
    case 'run_failed':
    case 'error':
      return 'text-red-400';
    case 'test_started':
    case 'run_started':
      return 'text-blue-400';
    case 'log':
    case 'info':
      return 'text-gray-400';
    default:
      return 'text-gray-500';
  }
}

function getEventPrefix(type: string): string {
  switch (type) {
    case 'test_passed':
    case 'run_passed':
      return '[PASS]';
    case 'test_failed':
    case 'run_failed':
    case 'error':
      return '[FAIL]';
    case 'test_started':
    case 'run_started':
      return '[START]';
    default:
      return '[LOG]';
  }
}

export function LiveStream({ runId, onEvent }: LiveStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { events, connected, error } = useWebSocket(runId, { onEvent });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0a] overflow-hidden">
      {/* Terminal header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-gray-500" />
          <span className="text-xs font-medium text-gray-400">Live Log</span>
        </div>
        <div className="flex items-center gap-1.5">
          {connected ? (
            <>
              <motion.div
                animate={{ opacity: [1, 0.4, 1] }}
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
              <span className="text-[11px] text-gray-500">Connecting...</span>
            </>
          )}
        </div>
      </div>

      {/* Log output */}
      <div className="h-56 overflow-y-auto p-4 font-mono text-xs">
        {events.length === 0 ? (
          <p className="text-gray-700">Waiting for events...</p>
        ) : (
          events.map((event, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex gap-2 leading-relaxed"
            >
              <span className="text-gray-700 flex-shrink-0">
                {event.timestamp
                  ? new Date(event.timestamp).toLocaleTimeString()
                  : new Date().toLocaleTimeString()}
              </span>
              <span className={`flex-shrink-0 ${getEventColor(event.type)}`}>
                {getEventPrefix(event.type)}
              </span>
              <span className="text-gray-300">
                {event.message ??
                  (event.data ? JSON.stringify(event.data) : event.type)}
              </span>
            </motion.div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
