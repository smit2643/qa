'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Wand2, Mic, Film, Loader2, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { RecordingCapture } from './RecordingCapture';
import { VideoUpload } from './VideoUpload';
import { ai } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import { useRouter } from 'next/navigation';
import type { GenerateResponse, RecordingUploadResponse, VideoUploadResponse } from '@/lib/types';
import { cn } from '@/lib/utils';

type Tab = 'describe' | 'record' | 'upload';

interface GenerateModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  suiteId: string;
  projectId: string;
  onSuccess?: (result: GenerateResponse | RecordingUploadResponse | VideoUploadResponse) => void;
}

const tabs: { id: Tab; label: string; icon: React.ElementType; description: string }[] = [
  {
    id: 'describe',
    label: 'Describe',
    icon: Wand2,
    description: 'Write a plain-English description',
  },
  {
    id: 'record',
    label: 'Record Screen',
    icon: Mic,
    description: 'Record your screen interactions',
  },
  {
    id: 'upload',
    label: 'Upload Video',
    icon: Film,
    description: 'Upload an mp4/webm video',
  },
];

export function GenerateModal({
  open,
  onOpenChange,
  suiteId,
  projectId,
  onSuccess,
}: GenerateModalProps) {
  const { toast } = useToast();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>('describe');
  const [description, setDescription] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleDescribeGenerate = async () => {
    if (!description.trim()) {
      toast({ variant: 'destructive', title: 'Enter a description first' });
      return;
    }
    if (isGenerating) return;

    setIsGenerating(true);
    try {
      // AI agent navigates app, records steps, generates Playwright code
      const result = await ai.generate({
        description: description.trim(),
        suite_id: suiteId,
      });

      onSuccess?.(result);
      onOpenChange(false);
      setDescription('');

      toast({
        title: 'Test generated',
        description: 'Review the steps, edit if needed, then click Generate Code to run it.',
      });

      // Go to test detail page — user reviews steps before running
      router.push(`/projects/${projectId}/suites/${suiteId}/tests/${result.test_id}`);
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Generation failed',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRecordingSuccess = (result: RecordingUploadResponse) => {
    onSuccess?.(result);
    onOpenChange(false);
    router.push(`/projects/${projectId}/suites/${suiteId}/tests/${result.test_id}`);
  };

  const handleVideoSuccess = (result: VideoUploadResponse) => {
    onSuccess?.(result);
    onOpenChange(false);
    router.push(`/projects/${projectId}/suites/${suiteId}/tests/${result.test_id}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-violet-400" />
            Generate Test
          </DialogTitle>
          <DialogDescription>
            Choose how you want to create your test
          </DialogDescription>
        </DialogHeader>

        {/* Tab buttons */}
        <div className="flex gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] p-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-2 text-xs font-medium transition-all',
                  activeTab === tab.id
                    ? 'bg-violet-600 text-white shadow-sm'
                    : 'text-gray-400 hover:text-white'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
          >
            {activeTab === 'describe' && (
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-gray-300">Test Description</Label>
                  <Textarea
                    placeholder={`Describe what the test should do in plain English.\n\nExamples:\n- "Go to /login, enter email 'user@test.com' and password 'pass123', click Sign In, verify dashboard appears"\n- "Add item to cart, proceed to checkout, verify total"`}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={6}
                    className="resize-none border-white/10 bg-white/[0.04] text-white placeholder:text-gray-600 focus-visible:ring-violet-500"
                  />
                </div>

                <Button
                  onClick={handleDescribeGenerate}
                  disabled={isGenerating || !description.trim()}
                  className="w-full gap-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-40"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Generating with AI...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Generate Test
                    </>
                  )}
                </Button>
              </div>
            )}

            {activeTab === 'record' && (
              <RecordingCapture
                suiteId={suiteId}
                onSuccess={handleRecordingSuccess}
              />
            )}

            {activeTab === 'upload' && (
              <VideoUpload suiteId={suiteId} onSuccess={handleVideoSuccess} />
            )}
          </motion.div>
        </AnimatePresence>
      </DialogContent>
    </Dialog>
  );
}
