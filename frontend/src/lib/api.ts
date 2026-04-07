import type {
  User,
  Organization,
  Project,
  TestSuite,
  TestCase,
  TestStep,
  TestRun,
  GenerateResponse,
  RecordingUploadResponse,
  VideoUploadResponse,
  StepInput,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';
const API_URL = `${API_BASE}/api/v1`;

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('bug0_token');
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail ?? body.message ?? message;
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

async function uploadFile<T>(path: string, formData: FormData): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail ?? body.message ?? message;
    } catch {
      // ignore
    }
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export const auth = {
  signup: (data: { email: string; name: string; password: string }) =>
    request<{ access_token: string }>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  me: () => request<User>('/auth/me'),
};

// ─── Organizations ───────────────────────────────────────────────────────────

export const organizations = {
  list: () => request<Organization[]>('/organizations'),
};

// ─── Projects ────────────────────────────────────────────────────────────────

export const projects = {
  create: (data: { name: string; target_url: string; organization_id: string }) =>
    request<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  list: () => request<Project[]>('/projects'),

  get: (id: string) => request<Project>(`/projects/${id}`),

  delete: (id: string) =>
    request<void>(`/projects/${id}`, { method: 'DELETE' }),
};

// ─── Suites ──────────────────────────────────────────────────────────────────

export const suites = {
  create: (data: { name: string; project_id: string }) =>
    request<TestSuite>('/suites', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  list: (projectId: string) =>
    request<TestSuite[]>(`/projects/${projectId}/suites`),

  get: (id: string) => request<TestSuite>(`/suites/${id}`),

  runs: (suiteId: string) => request<TestRun[]>(`/suites/${suiteId}/runs`),

  setLoginConfig: (id: string, data: { login_url: string; login_email: string; login_password: string }) =>
    request<TestSuite>(`/suites/${id}/login-config`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  clearLoginConfig: (id: string) =>
    request<TestSuite>(`/suites/${id}/login-config`, { method: 'DELETE' }),

  clearAuthState: (id: string) =>
    request<TestSuite>(`/suites/${id}/auth-state`, { method: 'DELETE' }),
};

// ─── Tests ───────────────────────────────────────────────────────────────────

export const tests = {
  create: (data: { name: string; suite_id: string; code?: string }) =>
    request<TestCase>('/tests', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  list: (suiteId: string) =>
    request<TestCase[]>(`/suites/${suiteId}/tests`),

  get: (id: string) => request<TestCase>(`/tests/${id}`),

  delete: (id: string) =>
    request<void>(`/tests/${id}`, { method: 'DELETE' }),
};

// ─── Steps ───────────────────────────────────────────────────────────────────

export const steps = {
  list: (testId: string) =>
    request<TestStep[]>(`/tests/${testId}/steps`),

  bulkReplace: (testId: string, steps: StepInput[]) =>
    request<TestStep[]>(`/tests/${testId}/steps`, {
      method: 'PUT',
      body: JSON.stringify(steps),
    }),

  duplicate: (stepId: string) =>
    request<TestStep>(`/steps/${stepId}/duplicate`, { method: 'POST' }),

  insert: (
    testId: string,
    data: { at_order: number; action: string; selector: string; value: string }
  ) =>
    request<TestStep>(`/tests/${testId}/steps/insert`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ─── AI ──────────────────────────────────────────────────────────────────────

export const ai = {
  generate: (data: { description: string; suite_id: string; test_id?: string }) =>
    request<GenerateResponse>('/ai/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  generateFromSteps: (data: {
    suite_id: string;
    test_name: string;
    test_id?: string;
    steps: StepInput[];
    input_method: string;
  }) =>
    request<GenerateResponse>('/ai/generate-from-steps', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ─── Recordings ──────────────────────────────────────────────────────────────

export const recordings = {
  upload: (file: Blob, suiteId: string, testName: string) => {
    const formData = new FormData();
    formData.append('file', file, 'recording.webm');
    formData.append('suite_id', suiteId);
    formData.append('test_name', testName);
    return uploadFile<RecordingUploadResponse>('/recordings/upload', formData);
  },
};

// ─── Videos ──────────────────────────────────────────────────────────────────

export const videos = {
  upload: (
    file: File,
    suiteId: string,
    testName: string,
    onProgress?: (pct: number) => void
  ): Promise<VideoUploadResponse> => {
    return new Promise((resolve, reject) => {
      const token = getToken();
      const formData = new FormData();
      formData.append('file', file);
      formData.append('suite_id', suiteId);
      formData.append('test_name', testName);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_URL}/videos/upload`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          let message = `HTTP ${xhr.status}`;
          try {
            const body = JSON.parse(xhr.responseText);
            message = body.detail ?? body.message ?? message;
          } catch {
            // ignore
          }
          reject(new Error(message));
        }
      };

      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(formData);
    });
  },
};

// ─── Code Import ─────────────────────────────────────────────────────────────

export const imports = {
  fromCode: (data: {
    suite_id: string;
    test_name: string;
    source_code: string;
    source_language?: string;
  }) =>
    request<{
      test_id: string;
      suite_id: string;
      test_name: string;
      source_language: string;
      steps: unknown[];
      code: string;
      version: number;
      message: string;
    }>('/imports/code', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ─── Runs ────────────────────────────────────────────────────────────────────

export const runs = {
  create: (data: { suite_id: string; browser: string; test_ids?: string[]; use_playwright_code?: boolean }) =>
    request<TestRun>('/runs', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) => request<TestRun>(`/runs/${id}`),
};
