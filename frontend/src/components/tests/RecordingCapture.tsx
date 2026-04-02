'use client';

import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Mic, Square, Upload, Timer, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { recordings } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import type { RecordingUploadResponse } from '@/lib/types';

interface RecordingCaptureProps {
  suiteId: string;
  onSuccess: (result: RecordingUploadResponse) => void;
}

export function RecordingCapture({ suiteId, onSuccess }: RecordingCaptureProps) {
  const { toast } = useToast();
  const [testName, setTestName] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [duration, setDuration] = useState(0);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const startRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true,
      });

      chunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
          ? 'video/webm;codecs=vp9'
          : 'video/webm',
      });

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const recordedBlob = new Blob(chunksRef.current, { type: 'video/webm' });
        const url = URL.createObjectURL(recordedBlob);
        setBlobUrl(url);
        setBlob(recordedBlob);
        stream.getTracks().forEach((t) => t.stop());
        if (timerRef.current) clearInterval(timerRef.current);
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(1000);
      setIsRecording(true);
      setDuration(0);

      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);

      // Stop if user stops screen share
      stream.getVideoTracks()[0].onended = () => {
        stopRecording();
      };
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Could not start screen recording';
      setError(msg);
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const handleUpload = async () => {
    if (!blob) return;
    if (!testName.trim()) {
      toast({ variant: 'destructive', title: 'Enter a test name first' });
      return;
    }

    setIsUploading(true);
    try {
      const result = await recordings.upload(blob, suiteId, testName.trim());
      toast({ title: 'Recording uploaded', description: `${result.steps.length} steps extracted` });
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

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label className="text-gray-300">Test Name</Label>
        <Input
          placeholder="e.g. User login flow"
          value={testName}
          onChange={(e) => setTestName(e.target.value)}
          disabled={isRecording || isUploading}
          className="border-white/10 bg-white/[0.04] text-white placeholder:text-gray-600"
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {!isRecording && !blob && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] py-10"
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-white/[0.04]">
            <Mic className="h-6 w-6 text-violet-400" />
          </div>
          <div className="text-center">
            <p className="font-medium text-white">Record your screen</p>
            <p className="mt-1 text-xs text-gray-500">
              Interact with your app — every click and input will be captured
            </p>
          </div>
          <Button
            onClick={startRecording}
            className="gap-2 bg-violet-600 hover:bg-violet-700"
          >
            <Mic className="h-4 w-4" />
            Start Recording
          </Button>
        </motion.div>
      )}

      {isRecording && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center gap-4 rounded-xl border border-red-500/20 bg-red-500/5 py-10"
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-red-500/30 bg-red-500/10">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, duration: 1 }}
            >
              <div className="h-4 w-4 rounded-full bg-red-500" />
            </motion.div>
          </div>
          <div className="text-center">
            <p className="font-medium text-white">Recording in progress</p>
            <div className="mt-1 flex items-center justify-center gap-1.5 text-red-400">
              <Timer className="h-3.5 w-3.5" />
              <span className="font-mono text-sm">{formatTime(duration)}</span>
            </div>
          </div>
          <Button
            onClick={stopRecording}
            variant="destructive"
            className="gap-2"
          >
            <Square className="h-4 w-4 fill-current" />
            Stop Recording
          </Button>
        </motion.div>
      )}

      {blob && blobUrl && !isRecording && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-3"
        >
          <video
            src={blobUrl}
            controls
            className="w-full rounded-lg border border-white/10"
            style={{ maxHeight: 200 }}
          />
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 border-white/10"
              onClick={() => {
                setBlob(null);
                setBlobUrl(null);
                setDuration(0);
              }}
            >
              Re-record
            </Button>
            <Button
              className="flex-1 gap-2 bg-violet-600 hover:bg-violet-700"
              onClick={handleUpload}
              disabled={isUploading}
            >
              {isUploading ? (
                <>
                  <Upload className="h-4 w-4 animate-bounce" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  Upload & Generate
                </>
              )}
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  );
}
