import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Send,
  Loader2,
  X,
  Clock,
  CheckCircle,
  AlertCircle,
  ArrowLeft,
  BookOpen,
  Zap,
  ChevronRight,
  Paperclip,
  Repeat,
  Trash2,
  FileText,
  Plus,
  Brain,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  api,
  type Department,
  type Job,
  type JobEvent,
  type WikiPage as WikiPageData,
  type ProgressEvent,
  formatUploadUserMessage,
  type UploadResult,
} from '../api/client';
import type { DeptChatTurn, DeptUserTurn, DeptStreamState } from '../types/deptChat';
import { isUserDeptTurn, isChatUserTurn, isAssistantTurn, defaultDeptStreamState } from '../types/deptChat';
import styles from './DepartmentPage.module.css';
import { SkillBuilderModal } from '../components/SkillBuilderModal';
import { JobModePopover } from '../components/JobModePopover';
import { ProactiveTab } from './ProactiveTab';
import { useI18n } from '../i18n';

const STATUS_ICON: Record<string, React.ReactNode> = {
  running: <Loader2 size={13} className={styles.spin} />,
  pending: <Clock size={13} />,
  done: <CheckCircle size={13} />,
  error: <AlertCircle size={13} />,
  cancelled: <X size={13} />,
};

const JOB_ROLE_BADGE: Record<string, string> = {
  RESEARCHER: styles.jobEventRole_RESEARCHER,
  CRITIC: styles.jobEventRole_CRITIC,
  VALIDATOR: styles.jobEventRole_VALIDATOR,
  WRITER: styles.jobEventRole_WRITER,
  ANALYST: styles.jobEventRole_ANALYST,
};

type StreamPatch = Partial<DeptStreamState> | ((s: DeptStreamState) => Partial<DeptStreamState>);

export interface DepartmentPageProps {
  /** Department slug (slug from departments.yaml). */
  departmentName: string;
  departments: Department[];
  jobs: Job[];
  deptMessages: Record<string, DeptChatTurn[]>;
  addDeptTurn: (deptName: string, turn: DeptChatTurn) => void;
  deptStreamStates: Record<string, DeptStreamState>;
  updateDeptStream: (deptName: string, patch: StreamPatch) => void;
  reloadJobs: () => Promise<void>;
  onJobDone: (job: Job) => void;
  reloadDepartments: () => Promise<void>;
}

type SkillItem = Department['skills'][number];

/** User input bundle for streaming chat. */
interface ChatInputPayload {
  text: string;
  skill: SkillItem | null;
  attachment: UploadResult | null;
}

export function DepartmentPage({
  departmentName,
  departments,
  jobs,
  deptMessages,
  addDeptTurn,
  deptStreamStates,
  updateDeptStream,
  reloadJobs,
  reloadDepartments,
  onJobDone,
}: DepartmentPageProps) {
  const { t } = useI18n();
  const statusLabel = useMemo(
    () => ({
      running: t('dept.status.running'),
      pending: t('dept.status.pending'),
      done: t('dept.status.done'),
      error: t('dept.status.error'),
      cancelled: t('dept.status.cancelled'),
    }),
    [t],
  );
  const name = departmentName;
  const [searchParams, setSearchParams] = useSearchParams();
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState<SkillItem | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<Job | null>(null);
  const [jobDetailLoading, setJobDetailLoading] = useState(false);
  const [replyInput, setReplyInput] = useState('');
  const [replying, setReplying] = useState(false);
  const [previewFile, setPreviewFile] = useState<WikiPageData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [skillBuilderOpen, setSkillBuilderOpen] = useState(false);
  const [tab, setTab] = useState<'chat' | 'jobs' | 'proactive'>('chat');
  const [skillDeleteConfirm, setSkillDeleteConfirm] = useState<string | null>(null);

  interface JobDeleteState {
    jobId: string;
    wikiFiles: { path: string; title: string; job_role?: string }[];
    deleteWiki: Record<string, boolean>;
  }
  const [jobDeleteConfirm, setJobDeleteConfirm] = useState<JobDeleteState | null>(null);

  // Per-department stream state lives in App.tsx so it survives route changes
  const streamState = name ? (deptStreamStates[name] ?? defaultDeptStreamState()) : defaultDeptStreamState();
  const chatLoading = streamState.loading;
  const chatSteps = streamState.steps;
  const chatThinking = streamState.thinking;

  // One AbortController ref per component mount (doesn't need to survive route changes —
  // we just need the stream callbacks to write into the correct dept via updateDeptStream)
  const chatStreamRef = useRef<AbortController | null>(null);

  // Prefill chat input from ?chat=… (deep links with pre-filled message)
  useEffect(() => {
    if (!name) return;
    const chat = searchParams.get('chat');
    if (!chat) return;
    setInput((prev) => (prev.trim() ? prev : decodeURIComponent(chat)));
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev);
        n.delete('chat');
        return n;
      },
      { replace: true },
    );
  }, [name, searchParams, setSearchParams]);

  // File upload
  const [uploading, setUploading] = useState(false);
  const [attachment, setAttachment] = useState<UploadResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const chatBottomRef = useRef<HTMLDivElement>(null);
  const jobChatBottomRef = useRef<HTMLDivElement>(null);
  const prevJobStatusesRef = useRef<Record<string, string>>({});

  const dept = useMemo(
    () => (name ? departments.find((d) => d.name === name) ?? null : null),
    [departments, name],
  );

  const turns = useMemo(() => {
    const raw = name ? deptMessages[name] ?? [] : [];
    return raw.map((t): DeptChatTurn => {
      if ('kind' in t && (t.kind === 'system' || t.kind === 'chat-user' || t.kind === 'assistant')) return t;
      if ('kind' in t && t.kind === 'user') return t;
      const x = t as unknown as { id: string; task: string; jobId: string };
      return { id: x.id, kind: 'user', task: x.task, jobId: x.jobId } satisfies DeptUserTurn;
    });
  }, [name, deptMessages]);

  const deptJobs = useMemo(() => {
    if (!name) return [];
    return [...jobs.filter((j) => j.department === name)].sort(
      (a, b) => b.job_id.localeCompare(a.job_id, undefined, { numeric: true }),
    );
  }, [jobs, name]);

  const runningJobCount = useMemo(
    () => deptJobs.filter((j) => j.status === 'running' || j.status === 'pending').length,
    [deptJobs],
  );

  const selectedJob = useMemo(
    () => (selectedJobId ? deptJobs.find((j) => j.job_id === selectedJobId) ?? null : null),
    [deptJobs, selectedJobId],
  );

  // Detect job completions
  useEffect(() => {
    for (const job of deptJobs) {
      const prev = prevJobStatusesRef.current[job.job_id];
      const curr = job.status;
      if (prev && prev !== curr && (curr === 'done' || curr === 'error' || curr === 'cancelled')) {
        onJobDone(job);
      }
      prevJobStatusesRef.current[job.job_id] = curr;
    }
  }, [deptJobs, onJobDone]);

  // Reset local UI state on department switch (stream state in App.tsx survives)
  useEffect(() => {
    setSelectedJobId(null);
    setJobDetail(null);
    setSelectedSkill(null);
    setInput('');
    setReplyInput('');
    setAttachment(null);
    setTab('chat');
  }, [name]);

  // Load detail when job selected
  useEffect(() => {
    if (!selectedJobId) { setJobDetail(null); return; }
    setPreviewFile(null);
    setJobDetailLoading(true);
    api.job(selectedJobId)
      .then(setJobDetail)
      .catch(() => setJobDetail(null))
      .finally(() => setJobDetailLoading(false));
  }, [selectedJobId]);

  // Poll job detail while running (for live events)
  useEffect(() => {
    if (!selectedJobId) return;
    const isRunning = selectedJob?.status === 'running' || selectedJob?.status === 'pending';
    if (!isRunning && jobDetail && selectedJob?.status === jobDetail.status) return;

    const poll = () => {
      api.job(selectedJobId).then(setJobDetail).catch(() => {});
    };

    if (isRunning) {
      poll();
      const iv = setInterval(poll, 2000);
      return () => clearInterval(iv);
    }

    poll();
  }, [selectedJobId, selectedJob?.status]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns.length, chatSteps.length, chatLoading]);

  useEffect(() => {
    jobChatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [jobDetail?.status, jobDetail?.events?.length, jobDetail?.current_iteration]);

  // ── File upload ──────────────────────────────────────────────────────────
  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !name) return;
    e.target.value = '';
    setUploading(true);
    try {
      const result = await api.upload(file);
      setAttachment(result);
    } catch (err) {
      console.error('Upload failed', err);
    } finally {
      setUploading(false);
    }
  }, [name]);

  // ── Build the full message for chat stream ──────────────────────────────
  const buildMessage = useCallback(
    (p: ChatInputPayload): { display: string; full: string } => {
      const title = p.skill?.title ?? p.skill?.name ?? '';
      let full = p.skill
        ? t('dept.skillMessageWithSkill')
            .replace('{text}', p.text)
            .replace('{title}', title)
        : p.text;
      if (p.attachment) {
        full = formatUploadUserMessage(
          p.attachment.filename,
          p.attachment.context_text,
          p.attachment.is_image,
          full,
          {
            kindImage: t('upload.kindImage'),
            kindFile: t('upload.kindFile'),
            wikiHint: t('upload.wikiHint'),
            userTaskLabel: t('upload.userTaskLabel'),
          },
        );
      }
      const display = p.attachment
        ? `${p.attachment.filename}${p.text ? ` — ${p.text}` : ''}`
        : p.text;
      return { display, full: full || p.text };
    },
    [t],
  );

  // ── Direct chat stream ──────────────────────────────────────────────────
  const runChatStream = useCallback((p: ChatInputPayload, deptName: string) => {
    const { display, full } = buildMessage(p);
    addDeptTurn(deptName, { id: crypto.randomUUID(), kind: 'chat-user', text: display });
    updateDeptStream(deptName, { loading: true, steps: [], thinking: t('dept.thinking') });

    chatStreamRef.current?.abort();
    const ctrl = api.deptChatStream(deptName, full, (ev: ProgressEvent) => {
      if (ev.type === 'tool_call') {
        updateDeptStream(deptName, (s) => ({
          steps: [...s.steps, { name: ev.name ?? '', preview: ev.preview ?? '' }],
        }));
      } else if (ev.type === 'thinking') {
        updateDeptStream(deptName, { thinking: ev.name ?? '' });
      } else if (ev.type === 'answer') {
        addDeptTurn(deptName, { id: crypto.randomUUID(), kind: 'assistant', text: ev.content ?? '' });
        updateDeptStream(deptName, { loading: false, steps: [], thinking: '' });
      } else if (ev.type === 'error') {
        addDeptTurn(deptName, {
          id: crypto.randomUUID(),
          kind: 'system',
          text: `${t('chat.errorPrefix')} ${ev.error}`,
        });
        updateDeptStream(deptName, { loading: false, steps: [], thinking: '' });
      }
    });
    chatStreamRef.current = ctrl;
  }, [addDeptTurn, buildMessage, updateDeptStream, t]);

  // ── Send: always stream chat ─────────────────────────────────────────────
  const handleSend = useCallback(() => {
    if (!name || (!input.trim() && !attachment) || submitting || chatLoading) return;
    const text = input.trim();
    const p: ChatInputPayload = { text, skill: selectedSkill, attachment };
    setInput('');
    setSelectedSkill(null);
    setAttachment(null);
    runChatStream(p, name);
  }, [name, input, attachment, submitting, chatLoading, selectedSkill, runChatStream]);

  // ── Background job: from chat context OR directly from input text ───────
  const handleStartJobFromChat = useCallback(
    async (mode: 'single' | 'deep') => {
      const hasDraft = !!(input.trim() || attachment);
      if (!name || submitting || chatLoading) return;
      if (turns.length === 0 && !hasDraft) return;
      setSubmitting(true);
      try {
        let job_id: string;
        let label: string;

        const draftPayload: ChatInputPayload = {
          text: input.trim(),
          skill: selectedSkill,
          attachment,
        };
        const { full: draftFull, display: draftDisplay } = hasDraft
          ? buildMessage(draftPayload)
          : { full: '', display: '' };

        if (turns.length === 0) {
          // Path A: no conversation yet — send input text directly as job task
          const res = await api.createJob(name, draftFull || draftDisplay, mode);
          job_id = res.job_id;
          label = draftDisplay || draftFull;
        } else {
          // Path B: conversation exists — LLM formulates task from turns.
          // The freshly typed input is the user's CURRENT intent and must be
          // forwarded as draft_message; otherwise the LLM would re-derive the
          // previous task from the existing turns.
          const serializable = turns.map((t) => ({ ...t }));
          const res = await api.createJobFromChat(
            name,
            serializable,
            mode,
            draftFull || undefined,
          );
          job_id = res.job_id;
          label =
            res.task_summary?.trim() ||
            draftDisplay ||
            t('dept.jobFromChatDefault');
        }

        setInput('');
        setSelectedSkill(null);
        setAttachment(null);
        addDeptTurn(name, { id: crypto.randomUUID(), kind: 'user', task: label, jobId: job_id });
        const modeLine =
          mode === 'deep'
            ? t('dept.jobStartedDeep', { jobId: job_id })
            : t('dept.jobStartedSimple', { jobId: job_id });
        addDeptTurn(name, { id: crypto.randomUUID(), kind: 'system', text: modeLine });
        setSelectedJobId(job_id);
        await reloadJobs();
      } catch (e) {
        console.error('createJobFromChat failed', e);
        addDeptTurn(name, {
          id: crypto.randomUUID(),
          kind: 'system',
          text: t('dept.jobStartFailedErr', { err: e instanceof Error ? e.message : String(e) }),
        });
      } finally {
        setSubmitting(false);
      }
    },
    [name, submitting, chatLoading, turns, input, attachment, selectedSkill, buildMessage, addDeptTurn, reloadJobs],
  );

  // ── Reply to finished job (stays in same job) ───────────────────────────
  const handleReply = useCallback(async () => {
    if (!selectedJobId || !replyInput.trim() || replying) return;
    setReplying(true);
    const msg = replyInput.trim();
    try {
      await api.replyToJob(selectedJobId, msg);
      setReplyInput('');
      setJobDetail(null);
      await reloadJobs();
      // Reload detail to show updated history + running state
      api.job(selectedJobId).then(setJobDetail).catch(() => {});
    } catch (e) {
      console.error('Reply failed', e);
    } finally {
      setReplying(false);
    }
  }, [selectedJobId, replyInput, replying, reloadJobs]);

  const handleCancelJob = async (jobId: string) => {
    await api.cancelJob(jobId);
    await reloadJobs();
    if (selectedJobId === jobId) {
      api.job(jobId).then(setJobDetail).catch(() => {});
    }
  };

  const requestDeleteJob = useCallback((jobId: string) => {
    // Gather wiki files from the currently loaded jobDetail (if it matches),
    // or from the job list entry (which has no written_files). We prefer
    // jobDetail since it has the full file list.
    const files =
      (jobDetail?.job_id === jobId ? jobDetail?.written_files : undefined) ?? [];
    const initialChecks: Record<string, boolean> = {};
    for (const f of files) initialChecks[f.path] = true;
    setJobDeleteConfirm({ jobId, wikiFiles: files, deleteWiki: initialChecks });
  }, [jobDetail]);

  const confirmDeleteJob = useCallback(async (state: { jobId: string; wikiFiles: { path: string; title: string; job_role?: string }[]; deleteWiki: Record<string, boolean> }) => {
    setJobDeleteConfirm(null);
    // Delete selected wiki files first
    const toDelete = state.wikiFiles.filter((f) => state.deleteWiki[f.path]);
    const job = jobs.find((j) => j.job_id === state.jobId);
    const dept = job?.department;
    await Promise.allSettled(
      toDelete.map((f) => api.wikiDelete(f.path, dept)),
    );
    // Delete / cancel the job itself
    await api.cancelJob(state.jobId);
    if (selectedJobId === state.jobId) {
      setSelectedJobId(null);
      setJobDetail(null);
    }
    await reloadJobs();
  }, [jobs, selectedJobId, reloadJobs]);

  const handleDeleteSkill = async (skillName: string) => {
    if (!name) return;
    try {
      await api.deleteSkill(name, skillName + '.md');
      if (selectedSkill?.name === skillName) setSelectedSkill(null);
      await reloadDepartments();
    } catch (e) {
      console.error('Delete skill failed', e);
    }
  };

  const jobEventGroups = useMemo(() => {
    const evs = jobDetail?.events;
    if (!evs?.length) return [];
    const m = new Map<number, JobEvent[]>();
    for (const ev of evs) {
      const it = ev.iteration ?? 0;
      if (!m.has(it)) m.set(it, []);
      m.get(it)!.push(ev);
    }
    return [...m.entries()].sort((a, b) => a[0] - b[0]);
  }, [jobDetail?.events]);

  if (!name || !dept) {
    return (
      <div className={styles.shell}>
        <div className={styles.loadingState}>
          <Loader2 size={20} className={styles.spin} />
          <span>{!name ? t('dept.noneSelected') : t('dept.loading')}</span>
        </div>
      </div>
    );
  }

  const jobRunning = selectedJob?.status === 'running' || selectedJob?.status === 'pending';
  const jobDone = selectedJob?.status === 'done' || selectedJob?.status === 'error' || selectedJob?.status === 'cancelled';
  const hasWrittenFiles = !!(jobDetail?.written_files && jobDetail.written_files.length > 0);
  const writtenFilesList = jobDetail?.written_files ?? [];
  const deliverableFiles = writtenFilesList.filter((f) => f.job_role === 'deliverable');
  const materialFiles = writtenFilesList.filter((f) => f.job_role !== 'deliverable');
  const showFileGroups = deliverableFiles.length > 0 && materialFiles.length > 0;
  const inputDisabled = submitting || chatLoading;
  const canStartJobFromChat = !chatLoading && !submitting && (turns.length > 0 || !!(input.trim() || attachment));

  return (
    <div className={styles.shell}>
      {/* Tab bar: Chat / Jobs (hidden while viewing a job) */}
      {!selectedJobId && (
        <header className={styles.tabBar}>
          <div className={styles.tabBarLeft}>
            <span className={styles.topBarDept}>{dept.label}</span>
            <span className={styles.topBarMeta}>
              {dept.skills.length} {dept.skills.length === 1 ? 'Skill' : 'Skills'}
            </span>
          </div>
          <div className={styles.tabBarTabs}>
            <button
              type="button"
              className={`${styles.tabBtn} ${tab === 'chat' ? styles.tabBtnActive : ''}`}
              onClick={() => setTab('chat')}
            >
              {t('dept.tab.chat')}
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${tab === 'jobs' ? styles.tabBtnActive : ''}`}
              onClick={() => setTab('jobs')}
            >
              {t('dept.tab.jobs')}
              {deptJobs.length > 0 && (
                <span className={styles.tabBadge}>{deptJobs.length}</span>
              )}
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${tab === 'proactive' ? styles.tabBtnActive : ''}`}
              onClick={() => setTab('proactive')}
              title={t('dept.tab.proactiveTitle')}
            >
              <Clock size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              {t('dept.tab.proactive')}
            </button>
          </div>
          {runningJobCount > 0 && (
            <button
              type="button"
              className={styles.runningIndicator}
              onClick={() => setTab('jobs')}
              title={t('dept.toJobsTitle')}
            >
              <span className={styles.runningDot} />
              {runningJobCount} {runningJobCount === 1 ? t('dept.running') : t('dept.runningMany')}
            </button>
          )}
        </header>
      )}

      {/* Job detail header (replaces tab bar) */}
      {selectedJobId && (
        <header className={styles.jobDetailHeader}>
          <button
            type="button"
            className={styles.jobDetailHeaderBack}
            onClick={() => { setSelectedJobId(null); setJobDetail(null); }}
          >
            <ArrowLeft size={16} />
            {t('dept.back')}
          </button>
          <div className={styles.jobDetailHeaderRight}>
            {selectedJob ? (
              <>
                <span className={`${styles.topBarJobStatus} ${styles[`status_${selectedJob.status}`]}`}>
                  {STATUS_ICON[selectedJob.status]}
                  {statusLabel[selectedJob.status as keyof typeof statusLabel] ?? selectedJob.status}
                </span>
                <code className={styles.topBarJobId}>{selectedJob.job_id}</code>
                {jobRunning && (
                  <button
                    type="button"
                    className={styles.topBarCancel}
                    onClick={() => handleCancelJob(selectedJob.job_id)}
                  >
                    {t('dept.cancelJob')}
                  </button>
                )}
                {!jobRunning && (
                  <button
                    type="button"
                    className={styles.topBarCancel}
                    style={{ color: 'var(--text-dim)' }}
                    onClick={() => requestDeleteJob(selectedJob.job_id)}
                    title={t('dept.deleteJobTitle')}
                  >
                    <Trash2 size={13} />
                    {t('dept.deleteJob')}
                  </button>
                )}
              </>
            ) : (
              <code className={styles.topBarJobId}>{selectedJobId}</code>
            )}
          </div>
        </header>
      )}

      {/* Chat tab */}
      {tab === 'chat' && !selectedJobId && (
        <main className={styles.chatView}>
          <div className={styles.chatMessages}>
            {turns.length === 0 && !chatLoading && (
              <div className={styles.chatEmpty}>
                <BookOpen size={32} strokeWidth={1.2} />
                <p>{t('dept.emptyChat')}</p>
                <p className={styles.dimText}>
                  {t('dept.chatHint')}
                </p>
              </div>
            )}

            {turns.map((turn) => {
              if (isUserDeptTurn(turn)) {
                return (
                  <div key={turn.id} className={styles.msgRow}>
                    <div className={styles.msgUser}>
                      <div className={styles.msgBubble}>{turn.task}</div>
                      <button
                        type="button"
                        className={styles.msgJobLink}
                        onClick={() => setSelectedJobId(turn.jobId)}
                      >
                        {turn.jobId} →
                      </button>
                    </div>
                  </div>
                );
              }
              if (isChatUserTurn(turn)) {
                return (
                  <div key={turn.id} className={styles.msgRow}>
                    <div className={styles.msgUser}>
                      <div className={styles.msgBubble}>{turn.text}</div>
                    </div>
                  </div>
                );
              }
              if (isAssistantTurn(turn)) {
                return (
                  <div key={turn.id} className={styles.msgAssistant}>
                    <div className={styles.msgAssistantLabel}>
                    <span style={{ display:'inline-flex', alignItems:'center', justifyContent:'center', width:20, height:20, borderRadius:4, background:'var(--bg-elevated)', fontSize:10, fontWeight:700, flexShrink:0, color:'var(--text-dim)' }}>D</span>
                    {dept.label}
                  </div>
                    <div className={styles.msgAssistantBody}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.text}</ReactMarkdown>
                    </div>
                  </div>
                );
              }
              return (
                <div key={turn.id} className={styles.msgSystem}>
                  {turn.text}
                </div>
              );
            })}

            {/* Chat streaming progress */}
            {chatLoading && (
              <div className={styles.chatProgress}>
                <div className={styles.chatProgressTitle}>
                  <Loader2 size={14} className={styles.spin} />
                  {t('dept.chatProcessing')}
                </div>
                {chatSteps.map((s, i) => (
                  <div key={i} className={styles.chatProgressStep}>
                    <span>•</span>
                    <code>{s.name}</code>
                    {s.preview && <span className={styles.chatProgressPreview}>{s.preview.slice(0, 60)}</span>}
                  </div>
                ))}
                {chatThinking && (
                  <div className={styles.chatProgressThinking}>{chatThinking}…</div>
                )}
              </div>
            )}

            <div ref={chatBottomRef} />
          </div>

          {/* Fixed bottom: skills + chips + input */}
          <div className={styles.chatFooter}>
          {/* Skill tags above input */}
          <div className={styles.skillTags}>
            {dept.skills.map((s) => {
              const active = selectedSkill?.name === s.name;
              const title = s.title ?? s.name;
              return (
                <div key={s.name} className={`${styles.skillTag} ${active ? styles.skillTagActive : ''}`}>
                  <button
                    type="button"
                    className={styles.skillTagBody}
                    onClick={() => setSelectedSkill(active ? null : s)}
                  >
                    <span className={styles.skillTagIcon}>
                      <Zap size={11} />
                    </span>
                    <span className={styles.skillTagLabel}>{title}</span>
                  </button>
                  <button
                    type="button"
                    className={styles.skillTagDeleteBtn}
                    onClick={(e) => { e.stopPropagation(); setSkillDeleteConfirm(s.name); }}
                    title={t('dept.skillDeleteTitle')}
                    aria-label={t('dept.skillDeleteAria', { title })}
                  >
                    <X size={11} />
                  </button>
                </div>
              );
            })}
            <button
              type="button"
              className={styles.skillTagAddBtn}
              onClick={() => setSkillBuilderOpen(true)}
              title={t('dept.skillNew')}
              aria-label={t('dept.skillNew')}
            >
              <Plus size={14} />
            </button>
          </div>

          {/* Skill chip */}
          {selectedSkill && (
            <div className={styles.skillChip}>
              <Zap size={13} className={styles.skillChipIcon} />
              <span>{selectedSkill.title ?? selectedSkill.name}</span>
              {selectedSkill.description && (
                <span className={styles.skillChipDesc}> — {selectedSkill.description}</span>
              )}
              <button
                type="button"
                className={styles.skillChipClose}
                onClick={() => setSelectedSkill(null)}
                aria-label={t('dept.skillRemove')}
              >
                <X size={13} />
              </button>
            </div>
          )}

          {/* Attachment chip */}
          {attachment && (
            <div className={styles.attachChip}>
              <Paperclip size={13} className={styles.attachChipIcon} />
              <span className={styles.attachChipName}>{attachment.filename}</span>
              <button
                type="button"
                className={styles.skillChipClose}
                onClick={() => setAttachment(null)}
                aria-label={t('dept.fileRemove')}
              >
                <X size={13} />
              </button>
            </div>
          )}

          {/* Input row */}
          <div className={styles.inputRow}>
            <input
              type="file"
              ref={fileInputRef}
              className={styles.hiddenFile}
              onChange={handleFileChange}
              accept=".pdf,.docx,.txt,.md,.csv,.json,.yaml,.yml,.html,.xml,image/*"
            />
            <button
              type="button"
              className={styles.attachBtn}
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || inputDisabled}
              aria-label={t('dept.fileAttach')}
            >
              {uploading ? <Loader2 size={15} className={styles.spin} /> : <Paperclip size={15} />}
            </button>
            <input
              className={styles.inputField}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder={
                selectedSkill
                  ? t('dept.chatPlaceholderSkill', { title: selectedSkill.title ?? selectedSkill.name })
                  : attachment
                    ? t('dept.chatPlaceholderAttach')
                    : t('dept.chatPlaceholderMsg', { label: dept.label })
              }
              disabled={inputDisabled}
            />
            <JobModePopover
              triggerClassName={styles.jobFromChatBtn}
              title={t('dept.jobFromChatTitle')}
              disabled={!canStartJobFromChat}
              submitting={submitting}
              aria-label={t('dept.jobFromChatAria')}
              onSelect={(mode) => void handleStartJobFromChat(mode)}
            />
            <button
              className={styles.sendBtn}
              type="button"
              onClick={handleSend}
              disabled={inputDisabled || (!input.trim() && !attachment)}
              aria-label={t('dept.sendAria')}
            >
              {submitting ? <Loader2 size={16} className={styles.spin} /> : <Send size={16} />}
            </button>
          </div>
          </div>{/* /chatFooter */}
        </main>
      )}

      {/* Jobs tab: list only */}
      {tab === 'jobs' && !selectedJobId && (
        <div className={styles.jobsView}>
          <div className={styles.sectionLabel}>
            <BookOpen size={13} />
            {t('dept.jobsHeading')}
            {runningJobCount > 0 && (
              <span className={styles.queueBadge}>{runningJobCount}</span>
            )}
          </div>
          <div className={styles.jobsViewInner}>
            <div className={styles.jobList}>
              {deptJobs.length === 0 && (
                <p className={styles.dimText}>{t('dept.noJobsYet')}</p>
              )}
              {deptJobs.map((j) => (
                <div key={j.job_id} className={styles.jobCardWrap}>
                  <button
                    type="button"
                    className={styles.jobCard}
                    onClick={() => setSelectedJobId(j.job_id)}
                  >
                    <span className={`${styles.jobCardStatus} ${styles[`status_${j.status}`]}`}>
                      {STATUS_ICON[j.status]}
                      {(j.mode === 'deep' || j.mode === 'proactive') && (
                        <Repeat size={11} className={styles.deepIcon} aria-label="Deep Work" />
                      )}
                    </span>
                    <div className={styles.jobCardBody}>
                      <div className={styles.jobCardTop}>
                        <code className={styles.jobCardId}>{j.job_id}</code>
                        <span className={styles.jobCardTime}>{j.elapsed_seconds.toFixed(0)}s</span>
                      </div>
                      <span className={styles.jobCardPreview}>
                        {j.task_preview ?? j.task ?? '—'}
                      </span>
                    </div>
                    <ChevronRight size={14} className={styles.jobCardArrow} />
                  </button>
                  {j.status !== 'running' && j.status !== 'pending' && (
                    <button
                      type="button"
                      className={styles.jobCardDeleteBtn}
                      onClick={(e) => { e.stopPropagation(); requestDeleteJob(j.job_id); }}
                      title={t('dept.deleteJobTitle')}
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'proactive' && !selectedJobId && name && (
        <main className={styles.jobsView}>
          <div className={styles.sectionLabel}>
            <Clock size={13} />
            {t('dept.proactive.heading')}
          </div>
          <ProactiveTab departmentName={name} onSaved={reloadDepartments} />
        </main>
      )}

      {/* Job detail (fullscreen under header) */}
      {selectedJobId && (
        <div className={styles.jobDetailView}>
          <div className={styles.jobDetailPane}>
              {jobDetailLoading && (
                <div className={styles.detailLoading}>
                  <Loader2 size={18} className={styles.spin} />
                </div>
              )}

              {!jobDetailLoading && jobDetail && (
                <div
                  className={hasWrittenFiles ? styles.jobDetailWithFiles : undefined}
                  style={
                    hasWrittenFiles
                      ? undefined
                      : { display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }
                  }
                >
                  {hasWrittenFiles && (
                    <div className={styles.jobFilesCol}>
                      <div className={styles.jobFilesHeading}>{t('dept.filesHeading')}</div>
                      {previewFile && (
                        <button
                          type="button"
                          className={`${styles.jobFileLink} ${styles.jobFileLinkBack}`}
                          onClick={() => setPreviewFile(null)}
                        >
                          <ArrowLeft size={11} />
                          {t('dept.backToJob')}
                        </button>
                      )}
                      {showFileGroups ? (
                        <>
                          <div className={styles.jobFilesSubheading}>{t('dept.resultsHeading')}</div>
                          {deliverableFiles.map((f) => (
                            <button
                              key={f.path}
                              type="button"
                              className={`${styles.jobFileLink} ${styles.jobFileLinkDeliverable} ${previewFile?.path === f.path ? styles.jobFileLinkActive : ''}`}
                              title={f.path}
                              onClick={async () => {
                                setPreviewLoading(true);
                                setPreviewFile(null);
                                try {
                                  const page = await api.wikiRead(f.path, jobDetail.department);
                                  setPreviewFile(page);
                                } finally {
                                  setPreviewLoading(false);
                                }
                              }}
                            >
                              <FileText size={11} style={{ flexShrink: 0 }} />
                              {f.title}
                            </button>
                          ))}
                          <div className={styles.jobFilesSubheading}>{t('dept.materialHeading')}</div>
                          {materialFiles.map((f) => (
                            <button
                              key={f.path}
                              type="button"
                              className={`${styles.jobFileLink} ${previewFile?.path === f.path ? styles.jobFileLinkActive : ''}`}
                              title={f.path}
                              onClick={async () => {
                                setPreviewLoading(true);
                                setPreviewFile(null);
                                try {
                                  const page = await api.wikiRead(f.path, jobDetail.department);
                                  setPreviewFile(page);
                                } finally {
                                  setPreviewLoading(false);
                                }
                              }}
                            >
                              <FileText size={11} style={{ flexShrink: 0 }} />
                              {f.title}
                            </button>
                          ))}
                        </>
                      ) : (
                        writtenFilesList.map((f) => (
                          <button
                            key={f.path}
                            type="button"
                            className={`${styles.jobFileLink} ${f.job_role === 'deliverable' ? styles.jobFileLinkDeliverable : ''} ${previewFile?.path === f.path ? styles.jobFileLinkActive : ''}`}
                            title={f.path}
                            onClick={async () => {
                              setPreviewLoading(true);
                              setPreviewFile(null);
                              try {
                                const page = await api.wikiRead(f.path, jobDetail.department);
                                setPreviewFile(page);
                              } finally {
                                setPreviewLoading(false);
                              }
                            }}
                          >
                            <FileText size={11} style={{ flexShrink: 0 }} />
                            {f.title}
                          </button>
                        ))
                      )}
                    </div>
                  )}
                  <div className={styles.jobDetailScroll}>
                    {previewLoading && (
                      <div className={styles.detailLoading}>
                        <Loader2 size={18} className={styles.spin} />
                      </div>
                    )}
                    {previewFile && !previewLoading && (
                      <div className={styles.filePreview}>
                        <div className={styles.filePreviewTitle}>{previewFile.title}</div>
                        <div className={styles.detailResultBody}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{previewFile.content}</ReactMarkdown>
                        </div>
                      </div>
                    )}
                    {!previewFile && !previewLoading && (
                    <>
                    <div className={styles.detailStatusRow}>
                      <span className={`${styles.statusBadge} ${styles[`status_${jobDetail.status}`]}`}>
                        {STATUS_ICON[jobDetail.status]}
                        {statusLabel[jobDetail.status as keyof typeof statusLabel] ?? jobDetail.status}
                      </span>
                      {jobDetail.mode === 'proactive' && jobDetail.proactive_mission_label && (
                        <span className={styles.iterBadge} title={t('dept.proactiveMissionBadge')}>
                          {jobDetail.proactive_mission_label}
                        </span>
                      )}
                      {(jobDetail.mode === 'deep' || jobDetail.mode === 'proactive') &&
                        jobDetail.max_iterations != null &&
                        jobDetail.max_iterations > 0 && (<>
                        <span className={styles.iterBadge} title={t('dept.phaseProgressTitle')}>
                          {t('dept.phaseProgress', { cur: jobDetail.current_iteration ?? 0, total: jobDetail.max_iterations })}
                        </span>
                        {(jobDetail.progress_pct ?? 0) > 0 && (
                          <span className={styles.iterBadge} title={t('dept.progressEstimate')}>
                            {jobDetail.progress_pct}%
                          </span>
                        )}
                        {jobDetail.eval_status && (
                          <span className={styles.iterBadge} title={t('dept.evalStatusTitle')} style={{
                            borderColor: jobDetail.eval_status === 'GOAL_REACHED' ? 'var(--green, #22c55e)' :
                                         jobDetail.eval_status === 'BUDGET_EXHAUSTED' ? 'var(--yellow, #eab308)' :
                                         'var(--border)',
                          }}>
                            {jobDetail.eval_status === 'GOAL_REACHED' ? t('dept.eval.goal') :
                             jobDetail.eval_status === 'BUDGET_EXHAUSTED' ? t('dept.eval.budget') :
                             jobDetail.eval_status === 'CONTINUE' ? t('dept.eval.continue') :
                             t('dept.eval.working')}
                          </span>
                        )}
                      </>)}
                      <span className={styles.detailTime}>{jobDetail.elapsed_seconds.toFixed(0)}s</span>
                    </div>

                    {/* Conversation history */}
                    {jobDetail.history && jobDetail.history.length > 0 && (
                      <div className={styles.jobConversation}>
                        {jobDetail.history.map((entry, i) => (
                          <div
                            key={i}
                            className={
                              entry.role === 'user'
                                ? styles.jobConvUser
                                : styles.jobConvAssistant
                            }
                          >
                            <div className={styles.jobConvLabel}>
                              {entry.role === 'user' ? t('dept.role.you') : dept?.label ?? t('dept.fallbackLabel')}
                            </div>
                            <div className={styles.jobConvBody}>
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.content}</ReactMarkdown>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Current turn */}
                    <div className={styles.detailSection}>
                      <div className={styles.jobConvUser}>
                        <div className={styles.jobConvLabel}>{t('dept.you')}</div>
                        <div className={styles.jobConvBody}>
                          {jobDetail.task ?? jobDetail.task_preview ?? '—'}
                        </div>
                      </div>
                    </div>

                    {(jobDetail.status === 'running' || jobDetail.status === 'pending') && (
                      <div className={styles.detailRunning}>
                        <div className={styles.detailRunningDot} />
                        <span>{t('dept.working')}</span>
                      </div>
                    )}

                    {jobDetail.events && jobDetail.events.length > 0 && (
                      <div className={styles.jobEvents}>
                        {jobEventGroups.map(([iter, evs]) => {
                          const phaseRole = evs.find((e) => e.role)?.role;
                          return (
                            <div key={iter} className={styles.jobEventPhaseBlock}>
                              <div className={styles.jobEventPhaseHeader}>
                                {t('dept.phase', { n: iter })}
                                {phaseRole && (
                                  <span
                                    className={`${styles.jobEventRoleBadge} ${JOB_ROLE_BADGE[phaseRole] ?? ''}`}
                                  >
                                    {phaseRole}
                                  </span>
                                )}
                              </div>
                              {evs.map((ev, i) =>
                                ev.type === 'thinking' ? (
                                  <div key={`${iter}-${i}-${ev.ts}`} className={styles.jobEventThinkingRow}>
                                    <Brain size={12} className={styles.jobEventThinkingIcon} aria-hidden />
                                    <div className={styles.jobEventThinkingBody}>
                                      <span className={styles.jobEventThinkingLabel}>{ev.name}</span>
                                      {ev.preview ? (
                                        <span className={styles.jobEventThinkingPreview}>{ev.preview}</span>
                                      ) : null}
                                    </div>
                                  </div>
                                ) : (
                                  <div key={`${iter}-${i}-${ev.ts}`} className={styles.jobEventRow}>
                                    <span className={styles.jobEventDot}>•</span>
                                    <code className={styles.jobEventName}>{ev.name}</code>
                                    {ev.preview ? (
                                      <span className={styles.jobEventPreview}>{ev.preview.slice(0, 120)}</span>
                                    ) : null}
                                    {ev.detail?.path && (
                                      <span className={styles.jobEventPath} title={ev.detail.path}>
                                        {ev.detail.job_role === 'deliverable' ? t('dept.role.deliverablePrefix') : ''}
                                        {ev.detail.path}
                                      </span>
                                    )}
                                  </div>
                                ),
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {jobDetail.error && (
                      <div className={styles.detailError}>
                        <AlertCircle size={14} />
                        {jobDetail.error}
                      </div>
                    )}

                    {jobDetail.result && (
                      <div className={styles.jobConvAssistant}>
                        <div className={styles.jobConvLabel}>{dept?.label ?? t('dept.fallbackLabel')}</div>
                        <div className={styles.detailResultBody}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{jobDetail.result}</ReactMarkdown>
                        </div>
                      </div>
                    )}

                    {!jobDetail.result && !jobDetail.error && jobDetail.status === 'done' && (
                      <p className={styles.dimText}>{t('dept.noJobOutput')}</p>
                    )}

                    <div ref={jobChatBottomRef} />
                    </>
                    )}
                  </div>
                </div>
              )}

              {jobDone && (
                <div className={styles.replySection}>
                  <div className={styles.replyInputRow}>
                    <input
                      className={styles.replyInput}
                      value={replyInput}
                      onChange={(e) => setReplyInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleReply()}
                      placeholder={t('dept.replyPlaceholder')}
                      disabled={replying}
                    />
                    <button
                      type="button"
                      className={styles.sendBtn}
                      onClick={handleReply}
                      disabled={replying || !replyInput.trim()}
                      aria-label={t('dept.replyAria')}
                    >
                      {replying
                        ? <Loader2 size={15} className={styles.spin} />
                        : <Send size={15} />
                      }
                    </button>
                  </div>
                </div>
              )}
            </div>
        </div>
      )}

      {/* Skill delete confirm modal */}
      {skillDeleteConfirm && (() => {
        const skill = dept.skills.find((s) => s.name === skillDeleteConfirm);
        const title = skill?.title ?? skillDeleteConfirm;
        return (
          <div className={styles.confirmOverlay} role="dialog" aria-modal="true" aria-label={t('dept.skillDeleteConfirmAria')}>
            <div className={styles.confirmBox}>
              <div className={styles.confirmTitle}>{t('dept.skillDeleteConfirmTitle')}</div>
              <p className={styles.confirmBody}>
                {t('dept.skillDeleteConfirmBodyPre')} <strong>„{title}“</strong>{t('dept.skillDeleteConfirmBodyPost')}
              </p>
              <div className={styles.confirmActions}>
                <button
                  type="button"
                  className={styles.confirmBtnCancel}
                  onClick={() => setSkillDeleteConfirm(null)}
                >
                  {t('dept.confirmCancel')}
                </button>
                <button
                  type="button"
                  className={styles.confirmBtnDelete}
                  onClick={async () => {
                    setSkillDeleteConfirm(null);
                    await handleDeleteSkill(skillDeleteConfirm);
                  }}
                >
                  <Trash2 size={13} />
                  {t('dept.confirmDelete')}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Job delete confirm modal */}
      {jobDeleteConfirm && (
        <div className={styles.confirmOverlay} role="dialog" aria-modal="true" aria-label={t('dept.jobDeleteConfirmAria')}>
          <div className={styles.confirmBox}>
            <div className={styles.confirmTitle}>{t('dept.jobDeleteConfirmTitle')}</div>
            <p className={styles.confirmBody}>
              {t('dept.jobDeleteConfirmBodyPre')} <code style={{ color: 'var(--accent)', fontSize: 12 }}>{jobDeleteConfirm.jobId}</code> {t('dept.jobDeleteConfirmBodyPost')}
            </p>

            {jobDeleteConfirm.wikiFiles.length > 0 && (
              <div className={styles.jobDeleteWikiSection}>
                <div className={styles.jobDeleteWikiTitle}>
                  {t('dept.alsoDeleteWiki')}
                </div>
                <div className={styles.jobDeleteWikiList}>
                  {jobDeleteConfirm.wikiFiles.map((f) => (
                    <label key={f.path} className={styles.jobDeleteWikiItem}>
                      <input
                        type="checkbox"
                        checked={jobDeleteConfirm.deleteWiki[f.path] ?? true}
                        onChange={(e) =>
                          setJobDeleteConfirm((prev) =>
                            prev
                              ? { ...prev, deleteWiki: { ...prev.deleteWiki, [f.path]: e.target.checked } }
                              : null,
                          )
                        }
                      />
                      <span className={styles.jobDeleteWikiLabel}>
                        <span className={`${styles.jobDeleteWikiRole} ${f.job_role === 'deliverable' ? styles.jobDeleteWikiRoleDeliverable : ''}`}>
                          {f.job_role === 'deliverable' ? t('dept.wiki.deliverable') : t('dept.wiki.material')}
                        </span>
                        {f.title}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div className={styles.confirmActions}>
              <button
                type="button"
                className={styles.confirmBtnCancel}
                onClick={() => setJobDeleteConfirm(null)}
              >
                {t('dept.confirmCancel')}
              </button>
              <button
                type="button"
                className={styles.confirmBtnDelete}
                onClick={() => void confirmDeleteJob(jobDeleteConfirm)}
              >
                <Trash2 size={13} />
                {jobDeleteConfirm.wikiFiles.some((f) => jobDeleteConfirm.deleteWiki[f.path])
                  ? t('dept.jobPlusPages')
                  : t('dept.deleteJobTitle')}
              </button>
            </div>
          </div>
        </div>
      )}

      <SkillBuilderModal
        open={skillBuilderOpen}
        onClose={() => setSkillBuilderOpen(false)}
        departmentName={dept.name}
        departmentLabel={dept.label}
        onSuccess={() => void reloadDepartments()}
      />
    </div>
  );
}
