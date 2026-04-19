import { getApiLanguage } from '../i18n/apiLang';

const BASE = '/api';

function apiHeaders(extra?: HeadersInit): HeadersInit {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = import.meta.env.VITE_ORQESTRA_API_TOKEN;
  if (token) {
    h.Authorization = `Bearer ${token}`;
  }
  h['X-Orqestra-Lang'] = getApiLanguage();
  if (extra) {
    const e = new Headers(extra);
    e.forEach((v, k) => {
      h[k] = v;
    });
  }
  return h;
}

function uploadHeaders(): HeadersInit {
  const h: Record<string, string> = {};
  const token = import.meta.env.VITE_ORQESTRA_API_TOKEN;
  if (token) {
    h.Authorization = `Bearer ${token}`;
  }
  h['X-Orqestra-Lang'] = getApiLanguage();
  return h;
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: apiHeaders(opts?.headers as HeadersInit),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { detail?: string | { msg?: string }[] };
    const detail = body.detail;
    const msg =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => (typeof d === 'object' && d && 'msg' in d ? String(d.msg) : '')).join(', ')
          : undefined;
    throw new Error(msg ?? `HTTP ${res.status}`);
  }
  return res.json();
}

/** Labels for upload message (match server `format_upload_user_message` structure). */
export interface UploadMessageLabels {
  kindImage: string;
  kindFile: string;
  wikiHint: string;
  userTaskLabel: string;
}

const DEFAULT_UPLOAD_LABELS_EN: UploadMessageLabels = {
  kindImage: 'Image analysis',
  kindFile: 'File',
  wikiHint:
    'Note: If the user explicitly wants this content saved to the wiki, use kb_write with an appropriate path under wiki/ (e.g. wiki/wissen/…).',
  userTaskLabel: 'User message / task:',
};

/** Build orchestrator user message from an uploaded file (must match server `format_upload_user_message`). */
export function formatUploadUserMessage(
  filename: string,
  contextText: string,
  isImage: boolean,
  userMessage = '',
  labels: UploadMessageLabels = DEFAULT_UPLOAD_LABELS_EN,
): string {
  const kind = isImage ? labels.kindImage : labels.kindFile;
  const lines = [
    `[${kind}: ${filename}]`,
    '',
    contextText.trim(),
    '',
    '---',
    labels.wikiHint,
  ];
  const um = userMessage.trim();
  if (um) {
    lines.push('', labels.userTaskLabel, um);
  }
  return lines.join('\n');
}

export interface ProjectData {
  name: string;
  type: string;
  location: string;
  focus: string;
  target_market: string;
  notes: string;
  configured: boolean;
}

export interface UploadResult {
  filename: string;
  mime: string;
  is_image: boolean;
  context_text: string;
}

export interface ProactiveMission {
  id: string;
  label: string;
  prompt: string;
}

export interface DepartmentProactive {
  enabled: boolean;
  schedule: string | null;
  strategy: string;
  missions: ProactiveMission[];
}

export interface Department {
  name: string;
  label: string;
  color?: string | null;
  icon?: string | null;
  capabilities: string[];
  skills: {
    name: string;
    title?: string;
    description?: string;
    tags?: string[];
  }[];
  proactive?: DepartmentProactive;
}

export interface JobHistoryEntry {
  role: 'user' | 'assistant';
  content: string;
}

export interface JobEvent {
  type: 'tool_call' | 'thinking';
  name: string;
  preview: string;
  ts: number;
  iteration?: number;
  role?: string;
  detail?: { path?: string; job_role?: string };
}

export interface Job {
  job_id: string;
  department: string;
  status: string;
  elapsed_seconds: number;
  task_preview?: string;
  task?: string;
  result?: string | null;
  error?: string | null;
  history?: JobHistoryEntry[];
  events?: JobEvent[];
  mode?: string;
  max_iterations?: number;
  current_iteration?: number;
  eval_status?: string;
  progress_pct?: number;
  written_files?: { path: string; title: string; job_role?: string }[];
  pipeline_run_id?: string | null;
  proactive_mission_id?: string | null;
  proactive_mission_label?: string | null;
}

export interface PipelineStepDef {
  department: string;
  task_template: string;
  result_key?: string | null;
  mode?: string;
}

export interface PipelineDefinition {
  name: string;
  label: string;
  description: string;
  steps: PipelineStepDef[];
  variable_descriptions?: Record<string, string>;
}

export interface PipelineRunSummary {
  run_id: string;
  pipeline: string;
  status: string;
  current_step: number;
  total_steps: number;
  started_at: number;
  finished_at?: number | null;
  error?: string | null;
}

export interface PipelineRunDetail extends PipelineRunSummary {
  variables: Record<string, string>;
  steps: {
    department: string;
    job_id?: string | null;
    status: string;
    result_key?: string | null;
    error?: string | null;
  }[];
}

// ── Wiki types ───────────────────────────────────────────────────────

export interface WikiTreeEntry {
  path: string;
  title: string;
  category: string;
}

export interface WikiTreeSection {
  label: string;
  folders: Record<string, WikiTreeEntry[]>;
  index_path: string | null;
}

export interface WikiTree {
  main: WikiTreeSection;
  /** Persönliches Wiki „Mein Wissen“ (optional, wenn Backend aktiviert). */
  personal?: WikiTreeSection;
  departments: Record<string, WikiTreeSection>;
}

export interface WikiPage {
  path: string;
  title: string;
  category: string;
  tags: string[];
  created: string;
  updated: string;
  content: string;
  job_id?: string;
  job_role?: string;
}

export interface WikiSearchHit {
  path: string;
  title: string;
  category: string;
  snippet: string;
  department: string | null;
  department_label: string;
}

export interface WikiGraphNode {
  id: string;
  title: string;
  department: string | null;
  department_label: string;
  category: string;
  tags: string[];
  job_id?: string;
  job_role?: string;
}

export interface WikiGraphEdge {
  source: string;
  target: string;
  type: 'link' | 'tag' | 'job';
}

export interface WikiGraph {
  nodes: WikiGraphNode[];
  edges: WikiGraphEdge[];
}

export interface WikiClusterPage {
  path: string;
  title: string;
  category: string;
  tags: string[];
  folder: string;
  folder_label: string;
  job_id: string;
  job_role: string;
  updated: string;
}

export interface WikiCluster {
  label: string;
  tag: string;
  page_count: number;
  folders: string[];
  has_deliverable: boolean;
  pages: WikiClusterPage[];
}

export interface WikiClusters {
  clusters: WikiCluster[];
  unclustered: WikiClusterPage[];
}

export interface DepartmentTemplate {
  name: string;
  label: string;
  label_de: string;
  description: string;
  description_de: string;
  capabilities: string[];
}

export interface PipelineTemplate {
  name: string;
  label: string;
  label_de: string;
  description: string;
  description_de: string;
  required_departments: string[];
  steps_count: number;
  installed: boolean;
}

export interface WikiHomeDeptSection {
  name: string;
  label: string;
  page_count: number;
  categories: Record<string, number>;
}

export interface WikiHomeRecent {
  path: string;
  title: string;
  category: string;
  updated: string;
  department: string | null;
  department_label: string;
}

export interface WikiHome {
  main: { label: string; page_count: number; categories: Record<string, number> };
  /** Statistik für „Mein Wissen“, wenn aktiviert. */
  personal?: { label: string; page_count: number; categories: Record<string, number> };
  departments: WikiHomeDeptSection[];
  recent: WikiHomeRecent[];
}

export interface TopologyDepartment {
  id: string;
  label: string;
  color: string | null;
  icon: string | null;
  skills_count: number;
  active_jobs: number;
  proactive?: {
    enabled: boolean;
    schedule: string | null;
    mission_count: number;
  };
}

export interface TopologyResponse {
  orchestrator: { id: string; label: string };
  departments: TopologyDepartment[];
}

// ── Chat types ───────────────────────────────────────────────────────

export interface ProgressEvent {
  type: 'tool_call' | 'thinking' | 'answer' | 'error';
  name?: string;
  preview?: string;
  content?: string;
  error?: string;
}

export interface BuilderChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface SkillDraft {
  title: string;
  description?: string;
  content?: string;
}

/** Q&A wizard step ids (Department Builder) — matches backend QA_STEP_TOPICS_DE keys */
export type BuilderQaStepId = 'domain' | 'tasks' | 'style' | 'knowledge';

export interface BuilderChatResponse {
  reply: string;
  persona_draft?: string;
  suggested_capabilities?: string[];
  suggested_skills?: SkillDraft[];
  /** Present when step === "suggestions" */
  suggestions?: string[];
}

export interface CreateDepartmentPayload {
  name: string;
  label: string;
  persona_content: string;
  capabilities: string[];
  skills: SkillDraft[];
}

export const api = {
  createSession: () =>
    request<{ session_id: string }>('/sessions', { method: 'POST' }),

  deleteSession: (id: string) =>
    request<{ ok: boolean }>(`/sessions/${id}`, { method: 'DELETE' }),

  chatStream: (
    sessionId: string,
    message: string,
    onEvent: (ev: ProgressEvent) => void,
  ): AbortController => {
    const controller = new AbortController();

    fetch(`${BASE}/chat`, {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ session_id: sessionId, message }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok || !res.body) {
          onEvent({ type: 'error', error: `HTTP ${res.status}` });
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          let currentEvent = '';
          for (const line of lines) {
            if (line.startsWith('event:')) {
              currentEvent = line.slice(6).trim();
            } else if (line.startsWith('data:') && currentEvent) {
              try {
                const data = JSON.parse(line.slice(5).trim());
                onEvent({ type: currentEvent as ProgressEvent['type'], ...data });
              } catch { /* skip malformed */ }
              currentEvent = '';
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onEvent({ type: 'error', error: String(err) });
        }
      });

    return controller;
  },

  departments: () => request<Department[]>('/departments'),

  topology: () => request<TopologyResponse>('/topology'),

  availableCapabilities: () =>
    request<{ capabilities: string[] }>('/capabilities').then((r) => r.capabilities),

  builderChat: (body: {
    messages: BuilderChatMessage[];
    step: 'expertise' | 'tasks' | 'style' | 'review' | 'suggestions';
    department_name?: string;
    department_label?: string;
    qa_step?: BuilderQaStepId;
  }) =>
    request<BuilderChatResponse>('/departments/builder/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  createDepartment: (payload: CreateDepartmentPayload) =>
    request<Department>('/departments', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  deleteDepartment: (name: string) =>
    request<{ ok: boolean; deleted: string }>(`/departments/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),

  deptChatStream: (
    deptName: string,
    message: string,
    onEvent: (ev: ProgressEvent) => void,
  ): AbortController => {
    const controller = new AbortController();

    fetch(`${BASE}/departments/${deptName}/chat`, {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ message }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok || !res.body) {
          onEvent({ type: 'error', error: `HTTP ${res.status}` });
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          let currentEvent = '';
          for (const line of lines) {
            if (line.startsWith('event:')) {
              currentEvent = line.slice(6).trim();
            } else if (line.startsWith('data:') && currentEvent) {
              try {
                const data = JSON.parse(line.slice(5).trim());
                onEvent({ type: currentEvent as ProgressEvent['type'], ...data });
              } catch { /* skip malformed */ }
              currentEvent = '';
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onEvent({ type: 'error', error: String(err) });
        }
      });

    return controller;
  },

  createJob: (department: string, task: string, mode: 'single' | 'deep' = 'deep') =>
    request<{ job_id: string; department: string; status: string }>(
      `/departments/${department}/jobs`,
      { method: 'POST', body: JSON.stringify({ task, mode }) },
    ),

  createJobFromChat: (
    department: string,
    turns: unknown[],
    mode: 'single' | 'deep' = 'deep',
    draftMessage?: string,
  ) =>
    request<{ job_id: string; department: string; task_summary: string; status: string }>(
      `/departments/${encodeURIComponent(department)}/jobs/from-chat`,
      {
        method: 'POST',
        body: JSON.stringify({
          turns,
          mode,
          draft_message: draftMessage?.trim() || undefined,
        }),
      },
    ),

  createOrchestratorJob: (
    sessionId: string,
    mode: 'single' | 'deep',
    draftMessage?: string,
  ) =>
    request<{ job_id: string; department: string; task_summary: string; status: string }>(
      '/chat/job',
      {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId,
          mode,
          draft_message: draftMessage?.trim() || undefined,
        }),
      },
    ),

  jobs: (offset: number = 0, limit: number = 20) =>
    request<{
      jobs: Job[];
      total: number;
      offset: number;
      limit: number;
      has_more: boolean;
    }>(`/jobs?offset=${offset}&limit=${limit}`),

  job: (id: string) => request<Job>(`/jobs/${id}`),

  pipelines: () =>
    request<{ pipelines: PipelineDefinition[] }>('/pipelines').then((r) => r.pipelines),

  pipeline: (name: string) =>
    request<PipelineDefinition>(`/pipelines/${encodeURIComponent(name)}`),

  createPipeline: (p: PipelineDefinition) =>
    request<PipelineDefinition>('/pipelines', {
      method: 'POST',
      body: JSON.stringify(p),
    }),

  updatePipeline: (name: string, p: PipelineDefinition) =>
    request<PipelineDefinition>(`/pipelines/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(p),
    }),

  deletePipeline: (name: string) =>
    request<{ success: boolean; name: string }>(`/pipelines/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),

  startPipelineRun: (name: string, variables: Record<string, string>) =>
    request<{
      run_id: string;
      pipeline: string;
      status: string;
      current_step: number;
      total_steps: number;
    }>(`/pipelines/${encodeURIComponent(name)}/run`, {
      method: 'POST',
      body: JSON.stringify({ variables }),
    }),

  pipelineRuns: () =>
    request<{ runs: PipelineRunSummary[] }>('/pipeline-runs').then((r) => r.runs),

  pipelineRun: (runId: string) =>
    request<PipelineRunDetail>(`/pipeline-runs/${encodeURIComponent(runId)}`),

  cancelPipelineRun: (runId: string) =>
    request<{ success: boolean; run_id: string }>(
      `/pipeline-runs/${encodeURIComponent(runId)}/cancel`,
      { method: 'POST' },
    ),

  deletePipelineRun: (runId: string) =>
    request<{ success: boolean; run_id: string }>(
      `/pipeline-runs/${encodeURIComponent(runId)}`,
      { method: 'DELETE' },
    ),

  pipelineTemplates: () =>
    request<{ templates: PipelineTemplate[] }>('/pipeline-templates').then((r) => r.templates),

  installPipelineTemplate: (name: string) =>
    request<{
      success: boolean;
      pipeline: PipelineDefinition;
      missing_departments: string[];
    }>(`/pipeline-templates/${encodeURIComponent(name)}/install`, {
      method: 'POST',
    }),

  cancelJob: (id: string) =>
    request<{ success: boolean }>(`/jobs/${id}`, { method: 'DELETE' }),

  retryJob: (id: string) =>
    request<{ job_id: string; department: string; status: string }>(
      `/jobs/${id}/retry`,
      { method: 'POST' },
    ),

  deleteSkill: (department: string, filename: string) =>
    request<{ success: boolean; deleted: string }>(
      `/departments/${department}/skills/${filename}`,
      { method: 'DELETE' },
    ),

  suggestSkills: (department: string) =>
    request<{ suggested_skills: { title: string; description: string }[] }>(
      `/departments/${encodeURIComponent(department)}/skills/suggest`,
      { method: 'POST', body: JSON.stringify({}) },
    ),

  generateSkill: (department: string, title: string, description?: string) =>
    request<{ title: string; description: string; content: string }>(
      `/departments/${encodeURIComponent(department)}/skills/generate`,
      {
        method: 'POST',
        body: JSON.stringify({ title, description: description ?? '' }),
      },
    ),

  saveSkill: (department: string, skill: SkillDraft) =>
    request<{ success: boolean; filename: string }>(
      `/departments/${encodeURIComponent(department)}/skills`,
      {
        method: 'POST',
        body: JSON.stringify({
          title: skill.title,
          description: skill.description ?? '',
          content: skill.content ?? '',
        }),
      },
    ),

  replyToJob: (id: string, message: string) =>
    request<{ job_id: string; department: string; status: string }>(
      `/jobs/${id}/reply`,
      { method: 'POST', body: JSON.stringify({ message }) },
    ),

  wikiHome: () => request<WikiHome>('/wiki/home'),
  wikiTree: () => request<WikiTree>('/wiki/tree'),
  wikiRead: (path: string, department?: string) => {
    const params = new URLSearchParams({ path });
    if (department) params.set('department', department);
    return request<WikiPage>(`/wiki/read?${params}`);
  },
  wikiSearch: (q: string, limit = 20) =>
    request<WikiSearchHit[]>(`/wiki/search?${new URLSearchParams({ q, limit: String(limit) })}`),
  wikiDelete: (path: string, department?: string) => {
    const params = new URLSearchParams({ path });
    if (department) params.set('department', department);
    return request<{ success: boolean; deleted: string; cleaned_references_in: string[] }>(
      `/wiki/delete?${params}`,
      { method: 'DELETE' },
    );
  },
  wikiIngest: async (
    file: File,
    department?: string,
  ): Promise<{ job_id: string; filename: string; department: string | null }> => {
    const fd = new FormData();
    fd.append('file', file);
    if (department) fd.append('department', department);
    const res = await fetch(`${BASE}/wiki/ingest`, { method: 'POST', headers: uploadHeaders(), body: fd });
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string };
      throw new Error(
        typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`,
      );
    }
    return res.json();
  },
  wikiExportPdf: async (path: string, department?: string): Promise<Blob> => {
    const params = new URLSearchParams({ path });
    if (department) params.set('department', department);
    const res = await fetch(`${BASE}/wiki/export/pdf?${params}`, {
      headers: uploadHeaders(),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string };
      throw new Error(
        typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`,
      );
    }
    return res.blob();
  },
  wikiClusters: (department?: string) => {
    const params = new URLSearchParams();
    if (department) params.set('department', department);
    const qs = params.toString();
    return request<WikiClusters>(`/wiki/clusters${qs ? `?${qs}` : ''}`);
  },
  wikiGraph: () => request<WikiGraph>('/wiki/graph'),

  triggerProactive: () =>
    request<{ triggered: number; message: string }>('/proactive/trigger', { method: 'POST' }),

  getDepartmentProactive: (department: string) =>
    request<DepartmentProactive>(`/departments/${encodeURIComponent(department)}/proactive`),

  putDepartmentProactive: (department: string, body: DepartmentProactive) =>
    request<{ ok: boolean; department: string }>(`/departments/${encodeURIComponent(department)}/proactive`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  triggerDeptProactive: (department: string, missionId?: string) => {
    const qs = missionId ? `?mission_id=${encodeURIComponent(missionId)}` : '';
    return request<{ job_ids: string[]; submitted: number; department: string; status: string }>(
      `/departments/${encodeURIComponent(department)}/proactive${qs}`,
      { method: 'POST' },
    );
  },

  templates: () =>
    request<DepartmentTemplate[]>('/templates'),
  installTemplate: (name: string) =>
    request<{ name: string; label: string }>(`/templates/${name}/install`, { method: 'POST' }),

  getProject: () => request<ProjectData>('/project'),

  getUiSettings: () => request<{ language: string }>('/settings/ui'),

  putUiSettings: (body: { language: string }) =>
    request<{ language: string }>('/settings/ui', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  saveProject: (data: Omit<ProjectData, 'configured'>) =>
    request<ProjectData>('/project', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  upload: async (file: File, sessionId?: string): Promise<UploadResult> => {
    const fd = new FormData();
    if (sessionId) fd.append('session_id', sessionId);
    fd.append('file', file);
    const res = await fetch(`${BASE}/upload`, { method: 'POST', headers: uploadHeaders(), body: fd });
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string };
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  },
};
