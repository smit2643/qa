export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  name: string;
  target_url: string;
  organization_id: string;
  api_key: string;
  created_at: string;
  updated_at: string;
}

export interface TestSuite {
  id: string;
  name: string;
  project_id: string;
  created_at: string;
  updated_at: string;
}

export interface TestCase {
  id: string;
  name: string;
  suite_id: string;
  code: string | null;
  version: number;
  input_method: string | null;
  created_at: string;
  updated_at: string;
}

export interface TestStep {
  id: string;
  test_id: string;
  action: string;
  selector: string | null;
  value: string | null;
  description: string | null;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface TestRun {
  id: string;
  suite_id: string;
  status: 'pending' | 'running' | 'passed' | 'failed' | 'error';
  browser: string;
  created_at: string;
  updated_at: string;
  results: TestResult[];
}

export interface TestResult {
  id: string;
  run_id: string;
  test_id: string;
  status: 'pending' | 'running' | 'passed' | 'failed' | 'error';
  video_url: string | null;
  error_message: string | null;
  duration_ms: number | null;
  created_at: string;
  updated_at: string;
}

export interface GenerateResponse {
  test_id: string;
  code: string;
  version: number;
  steps: TestStep[];
}

export interface RecordingUploadResponse {
  test_id: string;
  steps: TestStep[];
}

export interface VideoUploadResponse {
  test_id: string;
  steps: TestStep[];
  frame_count: number;
}

export interface StepInput {
  action: string;
  selector: string;
  value: string;
  description: string;
}

export type RunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error';
export type TestStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error';

export interface WsEvent {
  type: string;
  message?: string;
  test_id?: string;
  result_id?: string;
  status?: string;
  data?: unknown;
  timestamp?: string;
}
