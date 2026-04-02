'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { FolderKanban, TestTube2, PlayCircle, TrendingUp, ArrowRight, CheckCircle, XCircle, Clock } from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { projects, suites, tests, runs } from '@/lib/api';
import type { Project, TestRun } from '@/lib/types';
import { formatDate, formatDuration } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'passed':
      return <CheckCircle className="h-4 w-4 text-green-400" />;
    case 'failed':
    case 'error':
      return <XCircle className="h-4 w-4 text-red-400" />;
    default:
      return <Clock className="h-4 w-4 text-yellow-400" />;
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
    <Badge variant={variantMap[status] ?? 'default'} className="capitalize">
      {status}
    </Badge>
  );
}

export default function DashboardPage() {
  const { toast } = useToast();
  const [projectList, setProjectList] = useState<Project[]>([]);
  const [totalTests, setTotalTests] = useState(0);
  const [recentRuns, setRecentRuns] = useState<(TestRun & { projectName?: string; suiteName?: string })[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const projs = await projects.list();
        setProjectList(projs);

        // Count total tests across all suites
        let testCount = 0;
        const allRuns: (TestRun & { projectName?: string; suiteName?: string })[] = [];

        for (const proj of projs) {
          const projSuites = await suites.list(proj.id);
          for (const suite of projSuites) {
            const suiteTests = await tests.list(suite.id);
            testCount += suiteTests.length;

            const suiteRuns = await suites.runs(suite.id);
            for (const run of suiteRuns) {
              allRuns.push({ ...run, projectName: proj.name, suiteName: suite.name });
            }
          }
        }

        setTotalTests(testCount);
        allRuns.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setRecentRuns(allRuns.slice(0, 10));
      } catch (err) {
        toast({
          variant: 'destructive',
          title: 'Failed to load dashboard',
          description: err instanceof Error ? err.message : 'Unknown error',
        });
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [toast]);

  const passedRuns = recentRuns.filter((r) => r.status === 'passed').length;
  const failedRuns = recentRuns.filter(
    (r) => r.status === 'failed' || r.status === 'error'
  ).length;

  const stats = [
    {
      label: 'Total Projects',
      value: projectList.length,
      icon: FolderKanban,
      color: 'text-violet-400',
      bg: 'bg-violet-600/10',
    },
    {
      label: 'Total Tests',
      value: totalTests,
      icon: TestTube2,
      color: 'text-blue-400',
      bg: 'bg-blue-600/10',
    },
    {
      label: 'Recent Runs',
      value: recentRuns.length,
      icon: PlayCircle,
      color: 'text-green-400',
      bg: 'bg-green-600/10',
    },
    {
      label: 'Pass Rate',
      value:
        recentRuns.length > 0
          ? `${Math.round((passedRuns / recentRuns.length) * 100)}%`
          : '—',
      icon: TrendingUp,
      color: 'text-yellow-400',
      bg: 'bg-yellow-600/10',
    },
  ];

  return (
    <AppLayout title="Dashboard">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat, i) => {
            const Icon = stat.icon;
            return (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card className="border-white/[0.06]">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-500">{stat.label}</p>
                        <p className="mt-1 text-3xl font-bold text-white">
                          {isLoading ? (
                            <span className="inline-block h-8 w-12 animate-pulse rounded bg-white/10" />
                          ) : (
                            stat.value
                          )}
                        </p>
                      </div>
                      <div className={`rounded-xl p-3 ${stat.bg}`}>
                        <Icon className={`h-5 w-5 ${stat.color}`} />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Recent Runs */}
          <div className="lg:col-span-2">
            <Card className="border-white/[0.06]">
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-base font-semibold text-white">
                  Recent Test Runs
                </CardTitle>
                <Link href="/projects">
                  <Button variant="ghost" size="sm" className="gap-1 text-xs text-gray-400">
                    View all <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {[...Array(5)].map((_, i) => (
                      <div
                        key={i}
                        className="h-12 animate-pulse rounded-lg bg-white/5"
                      />
                    ))}
                  </div>
                ) : recentRuns.length === 0 ? (
                  <div className="py-8 text-center">
                    <PlayCircle className="mx-auto h-10 w-10 text-gray-700" />
                    <p className="mt-2 text-sm text-gray-500">No runs yet</p>
                    <p className="mt-1 text-xs text-gray-600">
                      Create a project and run your first test
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {recentRuns.map((run) => (
                      <Link key={run.id} href={`/runs/${run.id}`}>
                        <div className="flex items-center gap-3 rounded-lg p-3 transition-colors hover:bg-white/[0.03]">
                          <StatusIcon status={run.status} />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-white">
                              {run.suiteName ?? 'Suite'}
                            </p>
                            <p className="truncate text-xs text-gray-500">
                              {run.projectName} · {run.browser} ·{' '}
                              {formatDate(run.created_at)}
                            </p>
                          </div>
                          <StatusBadge status={run.status} />
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Projects list */}
          <div>
            <Card className="border-white/[0.06]">
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-base font-semibold text-white">
                  Projects
                </CardTitle>
                <Link href="/projects">
                  <Button variant="ghost" size="sm" className="gap-1 text-xs text-gray-400">
                    All <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-2">
                    {[...Array(4)].map((_, i) => (
                      <div
                        key={i}
                        className="h-10 animate-pulse rounded-lg bg-white/5"
                      />
                    ))}
                  </div>
                ) : projectList.length === 0 ? (
                  <div className="py-6 text-center">
                    <FolderKanban className="mx-auto h-8 w-8 text-gray-700" />
                    <p className="mt-2 text-xs text-gray-500">
                      No projects yet
                    </p>
                    <Link href="/projects">
                      <Button
                        size="sm"
                        className="mt-3 text-xs"
                        variant="outline"
                      >
                        Create project
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {projectList.slice(0, 8).map((proj) => (
                      <Link key={proj.id} href={`/projects/${proj.id}`}>
                        <div className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-white/[0.03]">
                          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-violet-600/20">
                            <FolderKanban className="h-3.5 w-3.5 text-violet-400" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm text-white">
                              {proj.name}
                            </p>
                            <p className="truncate text-xs text-gray-600">
                              {proj.target_url}
                            </p>
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
