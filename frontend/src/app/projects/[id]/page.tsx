'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Plus,
  TestTube2,
  ChevronRight,
  ArrowLeft,
  Loader2,
  PlayCircle,
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { projects, suites, tests } from '@/lib/api';
import type { Project, TestSuite, TestCase } from '@/lib/types';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';

const schema = z.object({
  name: z.string().min(1, 'Suite name is required'),
});
type FormData = z.infer<typeof schema>;

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const { toast } = useToast();

  const [project, setProject] = useState<Project | null>(null);
  const [suiteList, setSuiteList] = useState<TestSuite[]>([]);
  const [testCounts, setTestCounts] = useState<Record<string, number>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  useEffect(() => {
    async function load() {
      if (!params.id) return;
      try {
        const [proj, suitesData] = await Promise.all([
          projects.get(params.id),
          suites.list(params.id),
        ]);
        setProject(proj);
        setSuiteList(suitesData);

        // load test counts
        const counts: Record<string, number> = {};
        await Promise.all(
          suitesData.map(async (s) => {
            const ts = await tests.list(s.id);
            counts[s.id] = ts.length;
          })
        );
        setTestCounts(counts);
      } catch (err) {
        toast({
          variant: 'destructive',
          title: 'Failed to load project',
          description: err instanceof Error ? err.message : 'Unknown error',
        });
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [params.id, toast]);

  const onSubmit = async (data: FormData) => {
    if (!params.id) return;
    setCreating(true);
    try {
      const suite = await suites.create({
        name: data.name,
        project_id: params.id,
      });
      setSuiteList((prev) => [suite, ...prev]);
      setTestCounts((prev) => ({ ...prev, [suite.id]: 0 }));
      setShowCreate(false);
      reset();
      toast({ title: 'Suite created', description: suite.name });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Failed to create suite',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setCreating(false);
    }
  };

  return (
    <AppLayout title={project?.name ?? 'Project'}>
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link
            href="/projects"
            className="flex items-center gap-1 hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Projects
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-white">{project?.name}</span>
        </div>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">
              {project?.name ?? '...'}
            </h2>
            {project?.target_url && (
              <a
                href={project.target_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-0.5 text-sm text-violet-400 hover:text-violet-300"
              >
                {project.target_url}
              </a>
            )}
          </div>
          <Button
            onClick={() => setShowCreate(true)}
            className="gap-2 bg-violet-600 hover:bg-violet-700"
          >
            <Plus className="h-4 w-4" />
            New Suite
          </Button>
        </div>

        {/* Suites */}
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-20 animate-pulse rounded-xl bg-white/[0.03]"
              />
            ))}
          </div>
        ) : suiteList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <TestTube2 className="h-14 w-14 text-gray-700" />
            <h3 className="mt-4 text-base font-medium text-gray-400">
              No test suites yet
            </h3>
            <p className="mt-1 text-sm text-gray-600">
              Create a suite to organize your tests
            </p>
            <Button
              className="mt-4 gap-2 bg-violet-600 hover:bg-violet-700"
              onClick={() => setShowCreate(true)}
            >
              <Plus className="h-4 w-4" />
              Create suite
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {suiteList.map((suite, i) => (
              <motion.div
                key={suite.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Link
                  href={`/projects/${params.id}/suites/${suite.id}`}
                >
                  <Card className="border-white/[0.06] transition-all hover:border-violet-600/30 hover:shadow-lg hover:shadow-violet-600/5">
                    <CardContent className="flex items-center gap-4 p-5">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600/15 flex-shrink-0">
                        <TestTube2 className="h-5 w-5 text-violet-400" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-white">{suite.name}</p>
                        <p className="mt-0.5 text-xs text-gray-500">
                          Created {formatDate(suite.created_at)}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge variant="outline" className="gap-1.5">
                          <PlayCircle className="h-3 w-3" />
                          {testCounts[suite.id] ?? 0} tests
                        </Badge>
                        <ChevronRight className="h-4 w-4 text-gray-600" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Create suite dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Create Test Suite</DialogTitle>
            <DialogDescription>
              Group related tests into a suite.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-300">Suite Name</Label>
              <Input
                placeholder="Authentication Tests"
                className="border-white/10 bg-white/[0.04] text-white placeholder:text-gray-600"
                {...register('name')}
              />
              {errors.name && (
                <p className="text-xs text-red-400">{errors.name.message}</p>
              )}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreate(false)}
                className="border-white/10"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={creating}
                className="bg-violet-600 hover:bg-violet-700"
              >
                {creating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  'Create Suite'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
