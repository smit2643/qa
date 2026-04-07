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
  login_url: string | null;
  login_email: string | null;
  has_auth_state: boolean;
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
  order: number;
  action: string;
  selector: string;
  value: string;
  description: string;
}

export type RunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error';
export type TestStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error';

export interface WsEvent {
  // Backend sends "event" field (started/finished/run_passed/run_failed/log/error)
  event?: string;
  // Keep "type" as alias so existing code that checks event.type still works
  type?: string;
  message?: string;
  line?: string;
  test_name?: string;
  test_id?: string;
  result_id?: string;
  status?: string;
  data?: unknown;
  timestamp?: string;
}
