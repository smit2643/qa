'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Plus,
  TestTube2,
  ChevronRight,
  ArrowLeft,
  Trash2,
  Code2,
  PlayCircle,
  Sparkles,
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { GenerateModal } from '@/components/tests/GenerateModal';
import { suites, tests, projects } from '@/lib/api';
import type { TestSuite, TestCase, Project } from '@/lib/types';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';

export default function SuiteDetailPage() {
  const params = useParams<{ id: string; suiteId: string }>();
  const { toast } = useToast();

  const [project, setProject] = useState<Project | null>(null);
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [testList, setTestList] = useState<TestCase[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showGenerate, setShowGenerate] = useState(false);

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

  const handleNewTestAdded = () => {
    // Reload test list
    if (params.suiteId) {
      tests.list(params.suiteId).then(setTestList).catch(console.error);
    }
  };

  return (
    <AppLayout title={suite?.name ?? 'Suite'}>
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link href="/projects" className="hover:text-white">
            Projects
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <Link href={`/projects/${params.id}`} className="hover:text-white">
            {project?.name ?? '...'}
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-white">{suite?.name}</span>
        </div>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">
              {suite?.name ?? '...'}
            </h2>
            <p className="mt-0.5 text-sm text-gray-500">
              {testList.length} test{testList.length !== 1 ? 's' : ''}
            </p>
          </div>
          <Button
            onClick={() => setShowGenerate(true)}
            className="gap-2 bg-violet-600 hover:bg-violet-700"
          >
            <Sparkles className="h-4 w-4" />
            New Test
          </Button>
        </div>

        {/* Tests */}
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-20 animate-pulse rounded-xl bg-white/[0.03]"
              />
            ))}
          </div>
        ) : testList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <TestTube2 className="h-14 w-14 text-gray-700" />
            <h3 className="mt-4 text-base font-medium text-gray-400">
              No tests yet
            </h3>
            <p className="mt-1 text-sm text-gray-600">
              Generate your first test with AI
            </p>
            <Button
              className="mt-4 gap-2 bg-violet-600 hover:bg-violet-700"
              onClick={() => setShowGenerate(true)}
            >
              <Sparkles className="h-4 w-4" />
              Generate test
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            {testList.map((test, i) => (
              <motion.div
                key={test.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Card className="group border-white/[0.06] transition-all hover:border-violet-600/30">
                  <CardContent className="flex items-center gap-4 p-4">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-600/15 flex-shrink-0">
                      <TestTube2 className="h-4 w-4 text-violet-400" />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-white truncate">{test.name}</p>
                        {test.input_method && (
                          <Badge variant="outline" className="text-[10px] capitalize">
                            {test.input_method}
                          </Badge>
                        )}
                        {test.code && (
                          <Badge variant="default" className="text-[10px]">
                            <Code2 className="h-2.5 w-2.5 mr-1" />
                            v{test.version}
                          </Badge>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-gray-500">
                        {formatDate(test.created_at)}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Link
                        href={`/projects/${params.id}/suites/${params.suiteId}/tests/${test.id}`}
                      >
                        <Button
                          size="sm"
                          variant="ghost"
                          className="gap-1.5 text-gray-400 hover:text-white"
                        >
                          <Code2 className="h-3.5 w-3.5" />
                          View
                        </Button>
                      </Link>
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
            ))}
          </div>
        )}
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
