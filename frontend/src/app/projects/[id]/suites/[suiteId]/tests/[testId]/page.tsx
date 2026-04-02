'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ChevronRight,
  Code2,
  ListOrdered,
  Copy,
  Check,
  Sparkles,
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StepEditor } from '@/components/tests/StepEditor';
import { tests, steps, projects, suites } from '@/lib/api';
import type { TestCase, TestStep, Project, TestSuite } from '@/lib/types';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';

export default function TestDetailPage() {
  const params = useParams<{
    id: string;
    suiteId: string;
    testId: string;
  }>();
  const { toast } = useToast();

  const [project, setProject] = useState<Project | null>(null);
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [test, setTest] = useState<TestCase | null>(null);
  const [testSteps, setTestSteps] = useState<TestStep[]>([]);
  const [code, setCode] = useState<string>('');
  const [activeView, setActiveView] = useState<'steps' | 'code'>('steps');
  const [isLoading, setIsLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function load() {
      if (!params.id || !params.suiteId || !params.testId) return;
      try {
        const [proj, suiteData, testData, stepsData] = await Promise.all([
          projects.get(params.id),
          suites.get(params.suiteId),
          tests.get(params.testId),
          steps.list(params.testId),
        ]);
        setProject(proj);
        setSuite(suiteData);
        setTest(testData);
        setTestSteps(stepsData);
        setCode(testData.code ?? '');
      } catch (err) {
        toast({
          variant: 'destructive',
          title: 'Failed to load test',
          description: err instanceof Error ? err.message : 'Unknown error',
        });
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [params.id, params.suiteId, params.testId, toast]);

  const handleCopyCode = async () => {
    if (!code) return;
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCodeGenerated = (newCode: string) => {
    setCode(newCode);
    setActiveView('code');
  };

  return (
    <AppLayout title={test?.name ?? 'Test'}>
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Breadcrumb */}
        <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
          <Link href="/projects" className="hover:text-white">
            Projects
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <Link href={`/projects/${params.id}`} className="hover:text-white">
            {project?.name ?? '...'}
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <Link
            href={`/projects/${params.id}/suites/${params.suiteId}`}
            className="hover:text-white"
          >
            {suite?.name ?? '...'}
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-white">{test?.name}</span>
        </div>

        {/* Test info */}
        {test && (
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold text-white">{test.name}</h2>
                {test.input_method && (
                  <Badge variant="outline" className="capitalize text-xs">
                    {test.input_method}
                  </Badge>
                )}
                {test.code && (
                  <Badge variant="default" className="text-xs">
                    v{test.version}
                  </Badge>
                )}
              </div>
              <p className="mt-0.5 text-xs text-gray-500">
                Created {formatDate(test.created_at)}
              </p>
            </div>
          </div>
        )}

        {/* View toggle */}
        <div className="flex gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] p-1 w-fit">
          <button
            onClick={() => setActiveView('steps')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm font-medium transition-all',
              activeView === 'steps'
                ? 'bg-violet-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-white'
            )}
          >
            <ListOrdered className="h-3.5 w-3.5" />
            Steps
          </button>
          <button
            onClick={() => setActiveView('code')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm font-medium transition-all',
              activeView === 'code'
                ? 'bg-violet-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-white'
            )}
          >
            <Code2 className="h-3.5 w-3.5" />
            Code
            {!code && (
              <span className="ml-1 text-[10px] text-gray-600">empty</span>
            )}
          </button>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="h-64 animate-pulse rounded-xl bg-white/[0.03]" />
        ) : (
          <motion.div
            key={activeView}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
          >
            {activeView === 'steps' && (
              <Card className="border-white/[0.06]">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-semibold text-white">
                    Test Steps
                    <span className="ml-2 text-sm font-normal text-gray-500">
                      ({testSteps.length} steps)
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <StepEditor
                    testId={params.testId}
                    suiteId={params.suiteId}
                    initialSteps={testSteps}
                    onCodeGenerated={handleCodeGenerated}
                  />
                </CardContent>
              </Card>
            )}

            {activeView === 'code' && (
              <Card className="border-white/[0.06]">
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                    <Code2 className="h-4 w-4 text-violet-400" />
                    Generated Playwright Code
                  </CardTitle>
                  {code && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCopyCode}
                      className="gap-1.5 text-gray-400 hover:text-white"
                    >
                      {copied ? (
                        <>
                          <Check className="h-3.5 w-3.5 text-green-400" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5" />
                          Copy
                        </>
                      )}
                    </Button>
                  )}
                </CardHeader>
                <CardContent>
                  {code ? (
                    <pre className="overflow-auto rounded-lg bg-[#0d0d0d] p-4 text-[13px] leading-relaxed text-gray-300 font-mono border border-white/[0.06]">
                      <code>{code}</code>
                    </pre>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-10 text-center">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-violet-600/15">
                        <Sparkles className="h-5 w-5 text-violet-400" />
                      </div>
                      <p className="mt-3 text-sm text-gray-400">
                        No code generated yet
                      </p>
                      <p className="mt-1 text-xs text-gray-600">
                        Add steps and click &quot;Generate Code&quot;
                      </p>
                      <Button
                        size="sm"
                        className="mt-4 gap-2 bg-violet-600 hover:bg-violet-700"
                        onClick={() => setActiveView('steps')}
                      >
                        <ListOrdered className="h-3.5 w-3.5" />
                        Go to Steps
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </motion.div>
        )}
      </div>
    </AppLayout>
  );
}
