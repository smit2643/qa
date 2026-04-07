'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Wand2, Mic, Film, Loader2, Sparkles, Code2, ChevronDown } from 'lucide-react';
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
import { ai, imports } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import { useRouter } from 'next/navigation';
import type { GenerateResponse, RecordingUploadResponse, VideoUploadResponse } from '@/lib/types';
import { cn } from '@/lib/utils';

type Tab = 'describe' | 'record' | 'upload' | 'import';

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
    label: 'Record',
    icon: Mic,
    description: 'Record your screen interactions',
  },
  {
    id: 'upload',
    label: 'Video',
    icon: Film,
    description: 'Upload an mp4/webm video',
  },
  {
    id: 'import',
    label: 'Import Code',
    icon: Code2,
    description: 'Import existing test code (any language)',
  },
];

const LANGUAGE_OPTIONS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'cypress', label: 'Cypress (JS/TS)' },
  { value: 'selenium-python', label: 'Selenium Python' },
  { value: 'selenium-java', label: 'Selenium Java' },
  { value: 'selenium-csharp', label: 'Selenium C#' },
  { value: 'selenium-ruby', label: 'Selenium Ruby (Capybara)' },
  { value: 'playwright-js', label: 'Playwright JS/TS' },
  { value: 'pytest', label: 'Pytest' },
  { value: 'jest', label: 'Jest' },
  { value: 'plain-english', label: 'Plain English test cases' },
  { value: 'other', label: 'Other' },
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

  // Import code state
  const [importCode, setImportCode] = useState('');
  const [importTestName, setImportTestName] = useState('');
  const [importLanguage, setImportLanguage] = useState('auto');
  const [isImporting, setIsImporting] = useState(false);

  const handleDescribeGenerate = async () => {
    if (!description.trim()) {
      toast({ variant: 'destructive', title: 'Enter a description first' });
      return;
    }
    if (isGenerating) return;

    setIsGenerating(true);
    try {
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

  const handleImport = async () => {
    if (!importCode.trim()) {
      toast({ variant: 'destructive', title: 'Paste your test code first' });
      return;
    }
    if (!importTestName.trim()) {
      toast({ variant: 'destructive', title: 'Enter a test name' });
      return;
    }

    setIsImporting(true);
    try {
      const result = await imports.fromCode({
        suite_id: suiteId,
        test_name: importTestName.trim(),
        source_code: importCode.trim(),
        source_language: importLanguage,
      });

      onOpenChange(false);
      setImportCode('');
      setImportTestName('');
      setImportLanguage('auto');

      toast({
        title: 'Code imported',
        description: `${result.message} Detected: ${result.source_language}.`,
      });

      router.push(`/projects/${projectId}/suites/${suiteId}/tests/${result.test_id}`);
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Import failed',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsImporting(false);
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
                  'flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-2 text-xs font-medium transition-all',
                  activeTab === tab.id
                    ? 'bg-violet-600 text-white shadow-sm'
                    : 'text-gray-400 hover:text-white'
                )}
              >
                <Icon className="h-3.5 w-3.5 flex-shrink-0" />
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

            {activeTab === 'import' && (
              <div className="space-y-4">
                {/* Info banner */}
                <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 px-3 py-2.5">
                  <p className="text-xs text-violet-300 leading-relaxed">
                    Paste test code in <span className="font-semibold">any language</span> — Selenium, Cypress, Playwright JS, Pytest, Jest, Capybara, or plain English test cases. The AI reads the intent and converts it to Playwright Python.
                  </p>
                  {/* Language hints */}
                  <div className="mt-2 flex flex-wrap gap-1">
                    {['Selenium', 'Cypress', 'Playwright JS', 'Pytest', 'Jest', 'Ruby', 'C#', 'Java'].map(l => (
                      <span key={l} className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-gray-400">{l}</span>
                    ))}
                  </div>
                </div>

                {/* Test name */}
                <div className="space-y-1.5">
                  <Label className="text-gray-300 text-xs">Test Name</Label>
                  <input
                    type="text"
                    value={importTestName}
                    onChange={(e) => setImportTestName(e.target.value)}
                    placeholder="e.g. Customer login flow"
                    className="w-full rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>

                {/* Language selector */}
                <div className="space-y-1.5">
                  <Label className="text-gray-300 text-xs">Source Language (optional)</Label>
                  <div className="relative">
                    <select
                      value={importLanguage}
                      onChange={(e) => setImportLanguage(e.target.value)}
                      className="w-full appearance-none rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 pr-8 text-sm text-white focus:outline-none focus:ring-1 focus:ring-violet-500"
                    >
                      {LANGUAGE_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value} className="bg-[#111]">
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-gray-500" />
                  </div>
                </div>

                {/* Code textarea */}
                <div className="space-y-1.5">
                  <Label className="text-gray-300 text-xs">Paste Test Code</Label>
                  <Textarea
                    placeholder={`// Cypress example:\ncy.visit('/login')\ncy.get('[name=email]').type('user@example.com')\ncy.get('[name=password]').type('password123')\ncy.contains('Sign in').click()\ncy.url().should('include', '/dashboard')\n\n// Or Selenium Python:\ndriver.get("https://app.example.com/login")\ndriver.find_element(By.NAME, "email").send_keys("user@example.com")\ndriver.find_element(By.NAME, "password").send_keys("password123")\ndriver.find_element(By.XPATH, "//button[text()='Sign in']").click()`}
                    value={importCode}
                    onChange={(e) => setImportCode(e.target.value)}
                    rows={8}
                    className="resize-none border-white/10 bg-white/[0.04] font-mono text-xs text-white placeholder:text-gray-700 focus-visible:ring-violet-500"
                  />
                </div>

                <Button
                  onClick={handleImport}
                  disabled={isImporting || !importCode.trim() || !importTestName.trim()}
                  className="w-full gap-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-40"
                >
                  {isImporting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Converting with AI...
                    </>
                  ) : (
                    <>
                      <Code2 className="h-4 w-4" />
                      Import & Convert
                    </>
                  )}
                </Button>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </DialogContent>
    </Dialog>
  );
}
