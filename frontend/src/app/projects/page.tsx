'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Plus,
  FolderKanban,
  ExternalLink,
  Trash2,
  Loader2,
  Search,
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
import { projects, organizations } from '@/lib/api';
import type { Project, Organization } from '@/lib/types';
import { formatDate } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  target_url: z.string().url('Must be a valid URL'),
  organization_id: z.string().min(1, 'Organization is required'),
});

type FormData = z.infer<typeof schema>;

export default function ProjectsPage() {
  const { toast } = useToast();
  const [projectList, setProjectList] = useState<Project[]>([]);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState('');

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  useEffect(() => {
    async function load() {
      try {
        const [projs, orgList] = await Promise.all([
          projects.list(),
          organizations.list(),
        ]);
        setProjectList(projs);
        setOrgs(orgList);
        if (orgList.length > 0) {
          setValue('organization_id', orgList[0].id);
        }
      } catch (err) {
        toast({
          variant: 'destructive',
          title: 'Failed to load projects',
          description: err instanceof Error ? err.message : 'Unknown error',
        });
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [toast, setValue]);

  const onSubmit = async (data: FormData) => {
    setCreating(true);
    try {
      const proj = await projects.create(data);
      setProjectList((prev) => [proj, ...prev]);
      setShowCreate(false);
      reset();
      toast({ title: 'Project created', description: proj.name });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Failed to create project',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete project "${name}"? This cannot be undone.`)) return;
    try {
      await projects.delete(id);
      setProjectList((prev) => prev.filter((p) => p.id !== id));
      toast({ title: 'Project deleted' });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Failed to delete project',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const filtered = projectList.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.target_url.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <AppLayout title="Projects">
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">Projects</h2>
            <p className="mt-0.5 text-sm text-gray-500">
              Manage your testing projects
            </p>
          </div>
          <Button
            onClick={() => setShowCreate(true)}
            className="gap-2 bg-violet-600 hover:bg-violet-700"
          >
            <Plus className="h-4 w-4" />
            New Project
          </Button>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          <Input
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 border-white/10 bg-white/[0.03] text-white placeholder:text-gray-600"
          />
        </div>

        {/* Project grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="h-40 animate-pulse rounded-xl bg-white/[0.03]"
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <FolderKanban className="h-14 w-14 text-gray-700" />
            <h3 className="mt-4 text-base font-medium text-gray-400">
              {search ? 'No projects match your search' : 'No projects yet'}
            </h3>
            <p className="mt-1 text-sm text-gray-600">
              {!search && 'Create your first project to get started'}
            </p>
            {!search && (
              <Button
                className="mt-4 gap-2 bg-violet-600 hover:bg-violet-700"
                onClick={() => setShowCreate(true)}
              >
                <Plus className="h-4 w-4" />
                Create project
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((proj, i) => (
              <motion.div
                key={proj.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Card className="group cursor-pointer border-white/[0.06] transition-all hover:border-violet-600/30 hover:shadow-lg hover:shadow-violet-600/5">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600/15">
                        <FolderKanban className="h-5 w-5 text-violet-400" />
                      </div>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          handleDelete(proj.id, proj.name);
                        }}
                        className="opacity-0 group-hover:opacity-100 rounded-md p-1.5 text-gray-600 transition-all hover:bg-red-500/10 hover:text-red-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    <Link href={`/projects/${proj.id}`}>
                      <div className="mt-3">
                        <h3 className="font-semibold text-white group-hover:text-violet-300 transition-colors">
                          {proj.name}
                        </h3>
                        <a
                          href={proj.target_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="mt-1 flex items-center gap-1 text-xs text-gray-500 hover:text-violet-400"
                        >
                          <ExternalLink className="h-3 w-3" />
                          <span className="truncate">{proj.target_url}</span>
                        </a>
                        <p className="mt-3 text-xs text-gray-600">
                          Created {formatDate(proj.created_at)}
                        </p>
                      </div>
                    </Link>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Create project dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Create Project</DialogTitle>
            <DialogDescription>
              Add a new testing project with a target URL.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-300">Project Name</Label>
              <Input
                placeholder="My Web App"
                className="border-white/10 bg-white/[0.04] text-white placeholder:text-gray-600"
                {...register('name')}
              />
              {errors.name && (
                <p className="text-xs text-red-400">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label className="text-gray-300">Target URL</Label>
              <Input
                placeholder="https://myapp.com"
                className="border-white/10 bg-white/[0.04] text-white placeholder:text-gray-600"
                {...register('target_url')}
              />
              {errors.target_url && (
                <p className="text-xs text-red-400">
                  {errors.target_url.message}
                </p>
              )}
            </div>

            {orgs.length > 0 && (
              <div className="space-y-1.5">
                <Label className="text-gray-300">Organization</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                  {...register('organization_id')}
                >
                  {orgs.map((org) => (
                    <option key={org.id} value={org.id} className="bg-[#111]">
                      {org.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {orgs.length === 0 && (
              <Input
                type="hidden"
                {...register('organization_id')}
                defaultValue="default"
              />
            )}

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
                  'Create Project'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
