import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(ms: number | null | undefined): string {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'passed':
    case 'success':
      return 'text-green-400 bg-green-400/10';
    case 'failed':
    case 'error':
      return 'text-red-400 bg-red-400/10';
    case 'running':
    case 'pending':
      return 'text-yellow-400 bg-yellow-400/10';
    case 'skipped':
      return 'text-gray-400 bg-gray-400/10';
    default:
      return 'text-gray-400 bg-gray-400/10';
  }
}
