'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ChevronRight,
  PlayCircle,
  Clock,
  Monitor,
  RefreshCw,
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RunDetail } from '@/components/runs/RunDetail';
import { LiveStream } from '@/components/runs/LiveStream';
import { runs, tests } from '@/lib/api';
import type { TestRun, TestCase, WsEvent } from '@/lib/types';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';

function RunStatusBadge({ status }: { status: string }) {
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
    <Badge
      variant={variantMap[status] ?? 'default'}
      className="capitalize px-3 py-1 text-sm"
    >
      {status}
    </Badge>
  );
}

export default function RunDetailPage() {
  const params = useParams<{ runId: string }>();
  const { toast } = useToast();

  const [run, setRun] = useState<TestRun | null>(null);
  const [testMap, setTestMap] = useState<Record<string, TestCase>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);

  // Fetch run status (and build test map on first load)
  const loadRun = useCallback(async (buildTestMap = false) => {
    if (!params.runId) return;
    try {
      const runData = await runs.get(params.runId);
      setRun(runData);

      const alive = runData.status === 'running' || runData.status === 'queued';
      setIsLive(alive);

      if (buildTestMap) {
        const testIds = [...new Set(runData.results.map((r) => r.test_id))];
        const testEntries = await Promise.allSettled(
          testIds.map((id) => tests.get(id))
        );
        const map: Record<string, TestCase> = {};
        testEntries.forEach((entry, i) => {
          if (entry.status === 'fulfilled') {
            map[testIds[i]] = entry.value;
          }
        });
        setTestMap(map);
      }
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Failed to load run',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsLoading(false);
    }
  }, [params.runId, toast]);

  // Initial load (with test map)
  useEffect(() => {
    loadRun(true);
  }, [loadRun]);

  // Poll every 2s while the run is active — reliable fallback if WS closes early
  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(() => loadRun(false), 2000);
    return () => clearInterval(interval);
  }, [isLive, loadRun]);

  // WS events: backend sends "event" field — also available as "type" via the hook normalisation
  const handleWsEvent = useCallback(
    (event: WsEvent) => {
      const ev = event.event ?? event.type ?? '';
      if (ev === 'run_passed' || ev === 'run_failed' || ev === 'finished') {
        loadRun(false);
      }
    },
    [loadRun]
  );

  return (
    <AppLayout title="Run Details">
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/dashboard" className="hover:text-white">
            Dashboard
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-white">
            Run {params.runId?.slice(0, 8)}...
          </span>
        </div>

        {/* Run header */}
        {isLoading ? (
          <div className="h-24 animate-pulse rounded-xl bg-white/[0.03]" />
        ) : run ? (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="border-white/[0.06]">
              <CardContent className="flex flex-wrap items-center gap-4 p-5">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-600/15 flex-shrink-0">
                  <PlayCircle className="h-6 w-6 text-violet-400" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold text-white">
                      Test Run
                    </h2>
                    <RunStatusBadge status={run.status} />
                  </div>
                  <div className="mt-1 flex flex-wrap gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Monitor className="h-3.5 w-3.5" />
                      {run.browser}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {formatDate(run.created_at)}
                    </span>
                    <span>
                      {run.results.length} test
                      {run.results.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadRun}
                  className="gap-1.5 border-white/10 text-gray-400"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Refresh
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ) : null}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          {/* Results */}
          <div className="lg:col-span-3">
            <Card className="border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold text-white">
                  Test Results
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-2">
                    {[...Array(3)].map((_, i) => (
                      <div
                        key={i}
                        className="h-16 animate-pulse rounded-lg bg-white/5"
                      />
                    ))}
                  </div>
                ) : (
                  <RunDetail
                    results={run?.results ?? []}
                    testMap={testMap}
                  />
                )}
              </CardContent>
            </Card>
          </div>

          {/* Live stream */}
          <div className="lg:col-span-2">
            <Card className="border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                  Live Stream
                  {isLive && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 px-2 py-0.5 text-[11px] text-green-400">
                      <motion.span
                        animate={{ opacity: [1, 0, 1] }}
                        transition={{ repeat: Infinity, duration: 1 }}
                        className="inline-block h-1.5 w-1.5 rounded-full bg-green-400"
                      />
                      LIVE
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 pb-4 px-4">
                {params.runId && (
                  <LiveStream
                    runId={params.runId}
                    onEvent={handleWsEvent}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
