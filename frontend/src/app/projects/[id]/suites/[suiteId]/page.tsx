'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TestTube2,
  ChevronRight,
  Trash2,
  Code2,
  PlayCircle,
  Sparkles,
  CheckCircle,
  XCircle,
  Loader2,
  ExternalLink,
  KeyRound,
  ShieldCheck,
  ShieldOff,
  RefreshCw,
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { GenerateModal } from '@/components/tests/GenerateModal';
import { suites, tests, projects, runs } from '@/lib/api';
import type { TestSuite, TestCase, Project } from '@/lib/types';
import { useRouter } from 'next/navigation';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';

// ── Background run tracker ────────────────────────────────────────────────
interface BgRun {
  runId: string;
  testName: string;
  status: 'running' | 'passed' | 'failed';
}

function useBackgroundRuns() {
  const [bgRuns, setBgRuns] = useState<BgRun[]>([]);
  const timers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const startPolling = useCallback((runId: string, testName: string) => {
    setBgRuns((prev) => [...prev, { runId, testName, status: 'running' }]);

    // Poll every 4 seconds until run is complete
    timers.current[runId] = setInterval(async () => {
      try {
        const run = await runs.get(runId);
        if (run.status === 'passed' || run.status === 'failed') {
          clearInterval(timers.current[runId]);
          delete timers.current[runId];
          setBgRuns((prev) =>
            prev.map((r) =>
              r.runId === runId ? { ...r, status: run.status as 'passed' | 'failed' } : r
            )
          );
        }
      } catch {
        // silently ignore poll errors
      }
    }, 4000);
  }, []);

  const dismiss = useCallback((runId: string) => {
    clearInterval(timers.current[runId]);
    delete timers.current[runId];
    setBgRuns((prev) => prev.filter((r) => r.runId !== runId));
  }, []);

  // cleanup on unmount
  useEffect(() => {
    return () => {
      Object.values(timers.current).forEach(clearInterval);
    };
  }, []);

  return { bgRuns, startPolling, dismiss };
}

// ── Background run status bar ─────────────────────────────────────────────
function BgRunBar({ run, onDismiss }: { run: BgRun; onDismiss: () => void }) {
  const router = useRouter();
  const isPending = run.status === 'running';

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 text-sm ${
        isPending
          ? 'border-violet-500/30 bg-violet-500/10'
          : run.status === 'passed'
          ? 'border-green-500/30 bg-green-500/10'
          : 'border-red-500/30 bg-red-500/10'
      }`}
    >
      {isPending ? (
        <Loader2 className="h-4 w-4 animate-spin text-violet-400 flex-shrink-0" />
      ) : run.status === 'passed' ? (
        <CheckCircle className="h-4 w-4 text-green-400 flex-shrink-0" />
      ) : (
        <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
      )}

      <span className="flex-1 text-gray-200 truncate">
        <span className="font-medium">
          {isPending ? 'Running' : run.status === 'passed' ? 'Passed' : 'Failed'}:
        </span>{' '}
        {run.testName}
      </span>

      {!isPending && (
        <button
          onClick={() => router.push(`/runs/${run.runId}`)}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors flex-shrink-0"
        >
          View results
          <ExternalLink className="h-3 w-3" />
        </button>
      )}

      <button
        onClick={onDismiss}
        className="ml-1 text-gray-600 hover:text-gray-400 text-xs flex-shrink-0"
      >
        ✕
      </button>
    </motion.div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────
export default function SuiteDetailPage() {
  const params = useParams<{ id: string; suiteId: string }>();
  const { toast } = useToast();
  const router = useRouter();
  const { bgRuns, startPolling, dismiss } = useBackgroundRuns();

  const [project, setProject] = useState<Project | null>(null);
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [testList, setTestList] = useState<TestCase[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showGenerate, setShowGenerate] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runningTestId, setRunningTestId] = useState<string | null>(null);

  // Login config modal state
  const [showLoginConfig, setShowLoginConfig] = useState(false);
  const [loginUrl, setLoginUrl] = useState('');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [isSavingLogin, setIsSavingLogin] = useState(false);

  useEffect(() => {
    async function load() {
      if (!params.id || !params.suiteId) return;
      try {
        const [proj, suiteData, testData] = await Promise.all([
          projects.get(params.id),
          suites.get(params.suiteId),
          tests.list(params.suiteId),
        ]);
        setProject(proj);
        setSuite(suiteData);
        setTestList(testData);
        // Pre-fill login config form
        if (suiteData.login_url) setLoginUrl(suiteData.login_url);
        if (suiteData.login_email) setLoginEmail(suiteData.login_email);
      } catch (err) {
        toast({
          variant: 'destructive',
          title: 'Failed to load suite',
          description: err instanceof Error ? err.message : 'Unknown error',
        });
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [params.id, params.suiteId, toast]);

  const handleDeleteTest = async (id: string, name: string) => {
    if (!confirm(`Delete test "${name}"?`)) return;
    try {
      await tests.delete(id);
      setTestList((prev) => prev.filter((t) => t.id !== id));
      toast({ title: 'Test deleted' });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Failed to delete test',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleRunSuite = async () => {
    if (testList.length === 0) {
      toast({ variant: 'destructive', title: 'No tests to run' });
      return;
    }
    setIsRunning(true);
    try {
      const run = await runs.create({ suite_id: params.suiteId, browser: 'chromium' });
      router.push(`/runs/${run.id}`);
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Failed to start run',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
      setIsRunning(false);
    }
  };

  const handleRunTest = async (test: TestCase) => {
    if (!test.code?.trim()) {
      toast({ variant: 'destructive', title: 'No code yet', description: 'Generate code first.' });
      return;
    }
    setRunningTestId(test.id);
    try {
      const run = await runs.create({ suite_id: params.suiteId, browser: 'chromium', test_ids: [test.id] });
      router.push(`/runs/${run.id}`);
    } catch (err) {
      toast({ variant: 'destructive', title: 'Failed to start run', description: err instanceof Error ? err.message : 'Unknown error' });
      setRunningTestId(null);
    }
  };

  const handleNewTestAdded = () => {
    if (params.suiteId) {
      tests.list(params.suiteId).then(setTestList).catch(console.error);
    }
  };

  const handleBackgroundRunStarted = (runId: string, testName: string) => {
    startPolling(runId, testName);
    handleNewTestAdded();
  };

  const handleSaveLoginConfig = async () => {
    if (!loginUrl.trim() || !loginEmail.trim() || !loginPassword.trim()) {
      toast({ variant: 'destructive', title: 'All fields required' });
      return;
    }
    setIsSavingLogin(true);
    try {
      const updated = await suites.setLoginConfig(params.suiteId, {
        login_url: loginUrl.trim(),
        login_email: loginEmail.trim(),
        login_password: loginPassword,
      });
      setSuite(updated);
      setShowLoginConfig(false);
      toast({ title: 'Login config saved', description: 'Suite will auto-login before running tests.' });
    } catch (err) {
      toast({ variant: 'destructive', title: 'Failed to save', description: err instanceof Error ? err.message : 'Unknown error' });
    } finally {
      setIsSavingLogin(false);
    }
  };

  const handleClearAuthState = async () => {
    try {
      const updated = await suites.clearAuthState(params.suiteId);
      setSuite(updated);
      toast({ title: 'Auth state cleared', description: 'Suite will re-login on the next run.' });
    } catch (err) {
      toast({ variant: 'destructive', title: 'Failed to clear', description: err instanceof Error ? err.message : 'Unknown error' });
    }
  };

  const handleClearLoginConfig = async () => {
    if (!confirm('Remove login config and cached session from this suite?')) return;
    try {
      const updated = await suites.clearLoginConfig(params.suiteId);
      setSuite(updated);
      setLoginUrl('');
      setLoginEmail('');
      setLoginPassword('');
      toast({ title: 'Login config removed' });
    } catch (err) {
      toast({ variant: 'destructive', title: 'Failed to remove', description: err instanceof Error ? err.message : 'Unknown error' });
    }
  };

  return (
    <AppLayout title={suite?.name ?? 'Suite'}>
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/projects" className="hover:text-white">Projects</Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <Link href={`/projects/${params.id}`} className="hover:text-white">
            {project?.name ?? '...'}
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-white">{suite?.name}</span>
        </div>

        {/* Background run status bars */}
        <AnimatePresence>
          {bgRuns.map((run) => (
            <BgRunBar key={run.runId} run={run} onDismiss={() => dismiss(run.runId)} />
          ))}
        </AnimatePresence>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-semibold text-white">{suite?.name ?? '...'}</h2>
              {suite?.login_url ? (
                suite.has_auth_state ? (
                  <span className="flex items-center gap-1 rounded-full bg-green-500/10 border border-green-500/20 px-2 py-0.5 text-[11px] text-green-400">
                    <ShieldCheck className="h-3 w-3" /> Auth ready
                  </span>
                ) : (
                  <span className="flex items-center gap-1 rounded-full bg-yellow-500/10 border border-yellow-500/20 px-2 py-0.5 text-[11px] text-yellow-400">
                    <ShieldOff className="h-3 w-3" /> Login configured
                  </span>
                )
              ) : null}
            </div>
            <p className="mt-0.5 text-sm text-gray-500">
              {testList.length} test{testList.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => setShowLoginConfig(true)}
              variant="outline"
              size="sm"
              className="gap-1.5 border-white/10 text-gray-400 hover:text-white"
            >
              <KeyRound className="h-3.5 w-3.5" />
              {suite?.login_url ? 'Login Config' : 'Set Login'}
            </Button>
            <Button
              onClick={handleRunSuite}
              disabled={isRunning || testList.length === 0}
              variant="outline"
              className="gap-2 border-white/10 text-gray-300 hover:text-white hover:border-white/20"
            >
              <PlayCircle className="h-4 w-4" />
              {isRunning ? 'Starting...' : 'Run Suite'}
            </Button>
            <Button
              onClick={() => setShowGenerate(true)}
              className="gap-2 bg-violet-600 hover:bg-violet-700"
            >
              <Sparkles className="h-4 w-4" />
              New Test
            </Button>
          </div>
        </div>

        {/* Login Config Modal */}
        {showLoginConfig && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-xl border border-white/[0.08] bg-[#111] p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <KeyRound className="h-4 w-4 text-violet-400" />
                  <h3 className="text-base font-semibold text-white">Suite Login Config</h3>
                </div>
                <button onClick={() => setShowLoginConfig(false)} className="text-gray-600 hover:text-gray-300 text-sm">✕</button>
              </div>
              <p className="text-xs text-gray-500">
                The suite will log in once before running tests. All tests share the session — no login steps needed in individual tests.
              </p>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Login URL</label>
                  <input
                    type="url"
                    value={loginUrl}
                    onChange={(e) => setLoginUrl(e.target.value)}
                    placeholder="https://yourapp.com/login"
                    className="w-full rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Email / Username</label>
                  <input
                    type="text"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="user@example.com"
                    className="w-full rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 mb-1 block">Password</label>
                  <input
                    type="password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>
              </div>
              {suite?.has_auth_state && (
                <div className="flex items-center gap-2 rounded-lg bg-green-500/5 border border-green-500/20 px-3 py-2">
                  <ShieldCheck className="h-3.5 w-3.5 text-green-400 flex-shrink-0" />
                  <span className="text-xs text-green-300 flex-1">Session cached — next run will skip login</span>
                  <button
                    onClick={handleClearAuthState}
                    className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-300"
                  >
                    <RefreshCw className="h-3 w-3" /> Re-auth
                  </button>
                </div>
              )}
              <div className="flex gap-2 pt-1">
                <Button
                  size="sm"
                  onClick={handleSaveLoginConfig}
                  disabled={isSavingLogin}
                  className="flex-1 gap-1.5 bg-violet-600 hover:bg-violet-700"
                >
                  {isSavingLogin ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <KeyRound className="h-3.5 w-3.5" />}
                  Save
                </Button>
                {suite?.login_url && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleClearLoginConfig}
                    className="gap-1.5 border-red-500/20 text-red-400 hover:border-red-500/40 hover:text-red-300"
                  >
                    Remove
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tests */}
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-xl bg-white/[0.03]" />
            ))}
          </div>
        ) : testList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <TestTube2 className="h-14 w-14 text-gray-700" />
            <h3 className="mt-4 text-base font-medium text-gray-400">No tests yet</h3>
            <p className="mt-1 text-sm text-gray-600">Generate your first test with AI</p>
            <Button className="mt-4 gap-2 bg-violet-600 hover:bg-violet-700" onClick={() => setShowGenerate(true)}>
              <Sparkles className="h-4 w-4" />
              Generate test
            </Button>
          </div>
        ) : (() => {
          const generated = testList.filter(t => t.code && t.code.trim());
          const recordings = testList.filter(t => !t.code || !t.code.trim());

          const TestCard = ({ test, i }: { test: TestCase; i: number }) => {
            // Find if this test has a background run in progress
            const bgRun = bgRuns.find(r =>
              r.testName === test.name || r.testName.startsWith(test.name.slice(0, 30))
            );

            return (
              <motion.div
                key={test.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Card className={`group border-white/[0.06] transition-all hover:border-violet-600/30 ${
                  bgRun?.status === 'passed' ? 'border-green-500/20' :
                  bgRun?.status === 'failed' ? 'border-red-500/20' : ''
                }`}>
                  <CardContent className="flex items-center gap-4 p-4">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-600/15 flex-shrink-0">
                      <TestTube2 className="h-4 w-4 text-violet-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-white truncate">{test.name}</p>
                        {test.input_method && (
                          <Badge variant="outline" className="text-[10px] capitalize">{test.input_method}</Badge>
                        )}
                        {test.code ? (
                          <Badge variant="default" className="text-[10px]">
                            <Code2 className="h-2.5 w-2.5 mr-1" />v{test.version}
                          </Badge>
                        ) : (
                          <Badge variant="warning" className="text-[10px]">No code</Badge>
                        )}
                        {/* Background run status badge on the card */}
                        {bgRun && (
                          bgRun.status === 'running' ? (
                            <Badge variant="outline" className="text-[10px] border-violet-500/40 text-violet-400 gap-1">
                              <Loader2 className="h-2.5 w-2.5 animate-spin" />
                              Running…
                            </Badge>
                          ) : bgRun.status === 'passed' ? (
                            <Badge variant="outline" className="text-[10px] border-green-500/40 text-green-400">
                              ✓ Passed
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-[10px] border-red-500/40 text-red-400">
                              ✗ Failed
                            </Badge>
                          )
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-gray-500">{formatDate(test.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Link href={`/projects/${params.id}/suites/${params.suiteId}/tests/${test.id}`}>
                        <Button size="sm" variant="ghost" className="gap-1.5 text-gray-400 hover:text-white">
                          <Code2 className="h-3.5 w-3.5" />
                          View
                        </Button>
                      </Link>
                      {test.code?.trim() && (
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={runningTestId === test.id}
                          onClick={() => handleRunTest(test)}
                          className="gap-1.5 text-gray-400 hover:text-green-400 opacity-0 group-hover:opacity-100 transition-all"
                        >
                          <PlayCircle className="h-3.5 w-3.5" />
                          {runningTestId === test.id ? 'Starting…' : 'Run'}
                        </Button>
                      )}
                      <button
                        onClick={() => handleDeleteTest(test.id, test.name)}
                        className="rounded-md p-1.5 text-gray-700 opacity-0 group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-400 transition-all"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          };

          return (
            <div className="space-y-6">
              {generated.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
                    Generated Tests ({generated.length})
                  </p>
                  {generated.map((test, i) => <TestCard key={test.id} test={test} i={i} />)}
                </div>
              )}
              {recordings.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
                    Recordings — needs Generate ({recordings.length})
                  </p>
                  {recordings.map((test, i) => <TestCard key={test.id} test={test} i={i} />)}
                </div>
              )}
            </div>
          );
        })()}
      </div>

      <GenerateModal
        open={showGenerate}
        onOpenChange={setShowGenerate}
        suiteId={params.suiteId}
        projectId={params.id}
        onSuccess={handleNewTestAdded}
      />
    </AppLayout>
  );
}
