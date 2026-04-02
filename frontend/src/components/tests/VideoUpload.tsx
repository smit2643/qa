'use client';

import { useState, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Upload, Film, X, CheckCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { videos } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import type { VideoUploadResponse } from '@/lib/types';

interface VideoUploadProps {
  suiteId: string;
  onSuccess: (result: VideoUploadResponse) => void;
}

export function VideoUpload({ suiteId, onSuccess }: VideoUploadProps) {
  const { toast } = useToast();
  const [testName, setTestName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [done, setDone] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    if (!f.type.startsWith('video/')) {
      toast({
        variant: 'destructive',
        title: 'Invalid file type',
        description: 'Please upload an mp4 or webm video file.',
      });
      return;
    }
    setFile(f);
    setDone(false);
    setProgress(0);
    if (!testName) {
      setTestName(f.name.replace(/\.[^.]+$/, ''));
    }
  };

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [testName]
  );

  const handleUpload = async () => {
    if (!file) return;
    if (!testName.trim()) {
      toast({ variant: 'destructive', title: 'Enter a test name first' });
      return;
    }

    setIsUploading(true);
    setProgress(0);
    try {
      const result = await videos.upload(file, suiteId, testName.trim(), (pct) =>
        setProgress(pct)
      );
      setDone(true);
      toast({
        title: 'Video processed',
        description: `${result.frame_count} frames · ${result.steps.length} steps extracted`,
      });
      onSuccess(result);
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Upload failed',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label className="text-gray-300">Test Name</Label>
        <Input
          placeholder="e.g. Checkout flow"
          value={testName}
          onChange={(e) => setTestName(e.target.value)}
          disabled={isUploading}
          className="border-white/10 bg-white/[0.04] text-white placeholder:text-gray-600"
        />
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative cursor-pointer rounded-xl border-2 border-dashed py-10 text-center transition-all ${
          isDragging
            ? 'border-violet-500 bg-violet-500/10'
            : file
            ? 'border-green-500/30 bg-green-500/5'
            : 'border-white/10 bg-white/[0.02] hover:border-violet-500/40 hover:bg-white/[0.04]'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/webm,video/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />

        {done ? (
          <div className="flex flex-col items-center gap-2">
            <CheckCircle className="h-10 w-10 text-green-400" />
            <p className="font-medium text-green-400">Upload complete!</p>
          </div>
        ) : file ? (
          <div className="flex flex-col items-center gap-2">
            <Film className="h-10 w-10 text-violet-400" />
            <p className="font-medium text-white">{file.name}</p>
            <p className="text-xs text-gray-500">
              {(file.size / 1024 / 1024).toFixed(1)} MB
            </p>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setFile(null);
                setProgress(0);
              }}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-400"
            >
              <X className="h-3 w-3" />
              Remove
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.04]">
              <Upload className="h-6 w-6 text-gray-400" />
            </div>
            <div>
              <p className="font-medium text-white">
                Drop your video here
              </p>
              <p className="mt-0.5 text-sm text-gray-500">
                or click to browse — mp4, webm supported
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Progress bar */}
      {isUploading && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-1.5"
        >
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Uploading & analyzing...</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <motion.div
              className="h-full rounded-full bg-violet-500"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </motion.div>
      )}

      <Button
        onClick={handleUpload}
        disabled={!file || isUploading || done}
        className="w-full gap-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-40"
      >
        {isUploading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Processing video...
          </>
        ) : (
          <>
            <Upload className="h-4 w-4" />
            Upload & Analyze
          </>
        )}
      </Button>
    </div>
  );
}
