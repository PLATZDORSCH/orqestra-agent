import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  RefreshCw,
  X,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Send,
  Trash2,
  Repeat,
  RotateCcw,
  ArrowLeft,
  FileText,
  Zap,
  ChevronDown,
  Brain,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, type Department, type Job, type JobEvent, type WikiPage as WikiPageData } from '../api/client';
import { useI18n } from '../i18n';
import styles from './JobsPage.module.css';

/** Orchestrator wiki-ingest jobs — no per-job file list in UI. */
const MAIN_WIKI_DEPARTMENT = 'main_wiki';

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

function deptLabel(departments: Department[], department: string): string {
  return departments.find((d) => d.name === department)?.label ?? department;
}

function deptAccent(departments: Department[], department: string): string {
  const c = departments.find((d) => d.name === department)?.color;
  return (c && c.trim()) || 'var(--border)';
}

interface Props {
  jobs: Job[];
  reloadJobs: () => Promise<void>;
  departments: Department[];
  departmentsError?: string | null;
}

interface JobDeleteState {
  jobId: string;
  wikiFiles: { path: string; title: string; job_role?: string }[];
  deleteWiki: Record<string, boolean>;
}

const PAGE_SIZE = 20;

export function JobsPage({ reloadJobs, departments, departmentsError }: Props) {
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [expandedResult, setExpandedResult] = useState<Job | null>(null);
  const [replyInput, setReplyInput] = useState('');
  const [replying, setReplying] = useState(false);
  const [previewFile, setPreviewFile] = useState<WikiPageData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [proactiveOpen, setProactiveOpen] = useState(false);
  const [proactiveBusy, setProactiveBusy] = useState(false);
  const [jobDeleteConfirm, setJobDeleteConfirm] = useState<JobDeleteState | null>(null);
  const proactiveWrapRef = useRef<HTMLDivElement>(null);
  const jobChatBottomRef = useRef<HTMLDivElement>(null);

  const [items, setItems] = useState<Job[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const itemsCountRef = useRef(0);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    itemsCountRef.current = items.length;
  }, [items.length]);

  const refreshItems = useCallback(async () => {
    try {
      const cnt = Math.max(PAGE_SIZE, itemsCountRef.current);
      const res = await api.jobs(0, cnt);
      setItems(res.jobs);
      setHasMore(res.has_more);
    } catch {
      /* ignore */
    } finally {
      setInitialLoaded(true);
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const res = await api.jobs(itemsCountRef.current, PAGE_SIZE);
      setItems((prev) => {
        const seen = new Set(prev.map((j) => j.job_id));
        const add = res.jobs.filter((j) => !seen.has(j.job_id));
        return [...prev, ...add];
      });
      setHasMore(res.has_more);
    } catch {
      /* ignore */
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, loadingMore]);

  useEffect(() => {
    void refreshItems();
    const iv = setInterval(() => void refreshItems(), 5000);
    return () => clearInterval(iv);
  }, [refreshItems]);

  useEffect(() => {
    const el = loadMoreRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) void loadMore();
      },
      { rootMargin: '200px' },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [loadMore, hasMore, expandedJob]);

  const reloadAll = useCallback(async () => {
    await Promise.all([refreshItems(), reloadJobs()]);
  }, [refreshItems, reloadJobs]);

  const handleCancel = async (jobId: string) => {
    await api.cancelJob(jobId);
    await reloadAll();
    if (expandedJob === jobId) {
      api.job(jobId).then(setExpandedResult).catch(() => {});
    }
  };

  const handleDelete = async (jobId: string) => {
    await api.cancelJob(jobId);
    if (expandedJob === jobId) {
      setExpandedJob(null);
      setExpandedResult(null);
      setPreviewFile(null);
    }
    await reloadAll();
  };

  const handleRetry = async (jobId: string) => {
    await api.retryJob(jobId);
    await reloadAll();
    void openJob(jobId);
  };

  const handleBack = () => {
    setExpandedJob(null);
    setExpandedResult(null);
    setPreviewFile(null);
    setReplyInput('');
    setJobDeleteConfirm(null);
  };

  const expandParam = searchParams.get('expand');
  useEffect(() => {
    if (!expandParam) return;
    void (async () => {
      setExpandedJob(expandParam);
      setPreviewFile(null);
      setReplyInput('');
      try {
        setExpandedResult(await api.job(expandParam));
      } catch {
        /* ignore */
      }
    })();
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev);
        n.delete('expand');
        return n;
      },
      { replace: true },
    );
  }, [expandParam, setSearchParams]);

  const openJob = async (jobId: string) => {
    setExpandedJob(jobId);
    setPreviewFile(null);
    setReplyInput('');
    setExpandedResult(await api.job(jobId));
  };

  useEffect(() => {
    if (!expandedJob) return;
    const summary = items.find((j) => j.job_id === expandedJob);
    const isRunning = summary?.status === 'running' || summary?.status === 'pending';
    if (!isRunning) return;
    const iv = setInterval(async () => {
      try {
        setExpandedResult(await api.job(expandedJob));
      } catch {
        /* ignore */
      }
    }, 2000);
    return () => clearInterval(iv);
  }, [expandedJob, items]);

  const handleReply = useCallback(async () => {
    if (!expandedJob || !replyInput.trim() || replying) return;
    setReplying(true);
    try {
      await api.replyToJob(expandedJob, replyInput.trim());
      setReplyInput('');
      await reloadAll();
      setExpandedResult(await api.job(expandedJob));
    } catch (e) {
      console.error('Reply failed', e);
    } finally {
      setReplying(false);
    }
  }, [expandedJob, replyInput, replying, reloadAll]);

  const jobEventGroups = useMemo(() => {
    const evs = expandedResult?.events;
    if (!evs?.length) return [];
    const m = new Map<number, JobEvent[]>();
    for (const ev of evs) {
      const it = ev.iteration ?? 0;
      if (!m.has(it)) m.set(it, []);
      m.get(it)!.push(ev);
    }
    return [...m.entries()].sort((a, b) => a[0] - b[0]);
  }, [expandedResult?.events]);

  const requestDeleteJob = useCallback(
    (jobId: string) => {
      const files =
        (expandedResult?.job_id === jobId ? expandedResult?.written_files : undefined) ?? [];
      const initialChecks: Record<string, boolean> = {};
      for (const f of files) initialChecks[f.path] = true;
      setJobDeleteConfirm({ jobId, wikiFiles: files, deleteWiki: initialChecks });
    },
    [expandedResult],
  );

  const confirmDeleteJob = useCallback(
    async (state: JobDeleteState) => {
      setJobDeleteConfirm(null);
      const toDelete = state.wikiFiles.filter((f) => state.deleteWiki[f.path]);
      const job = items.find((j) => j.job_id === state.jobId);
      const deptName = job?.department;
      await Promise.allSettled(toDelete.map((f) => api.wikiDelete(f.path, deptName)));
      await api.cancelJob(state.jobId);
      if (expandedJob === state.jobId) {
        setExpandedJob(null);
        setExpandedResult(null);
        setPreviewFile(null);
      }
      await reloadAll();
    },
    [items, expandedJob, reloadAll],
  );

  useEffect(() => {
    if (!proactiveOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (proactiveWrapRef.current && !proactiveWrapRef.current.contains(e.target as Node)) {
        setProactiveOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [proactiveOpen]);

  useEffect(() => {
    jobChatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [expandedResult?.status, expandedResult?.events?.length, expandedResult?.current_iteration]);

  const handleProactiveDept = async (name: string, missionId?: string) => {
    setProactiveBusy(true);
    try {
      const res = await api.triggerDeptProactive(name, missionId);
      setProactiveOpen(false);
      await reloadAll();
      const first = res.job_ids[0];
      if (first) {
        setSearchParams((prev) => {
          const n = new URLSearchParams(prev);
          n.set('expand', first);
          return n;
        });
      }
    } catch (e) {
      console.error('Proactive job failed', e);
    } finally {
      setProactiveBusy(false);
    }
  };

  const renderJobDetail = (jobId: string, er: Job) => {
    const deptNameLabel = deptLabel(departments, er.department);
    const wf = er.written_files ?? [];
    const hasWrittenFiles = wf.length > 0;
    const deliverableFiles = wf.filter((f) => f.job_role === 'deliverable');
    const materialFiles = wf.filter((f) => f.job_role !== 'deliverable');
    const showFileGroups = deliverableFiles.length > 0 && materialFiles.length > 0;
    const jobRunning = er.status === 'running' || er.status === 'pending';
    const jobDone =
      er.status === 'done' || er.status === 'error' || er.status === 'cancelled';

    return (
      <div className={styles.jobDetailPage}>
        <header className={styles.jobDetailHeader}>
          <button type="button" className={styles.jobDetailHeaderBack} onClick={handleBack}>
            <ArrowLeft size={16} />
            {t('jobs.backToOverview')}
          </button>
          <div className={styles.jobDetailHeaderRight}>
            <span className={`${styles.topBarJobStatus} ${styles[`status_${er.status}`]}`}>
              {STATUS_ICON[er.status]}
              {statusLabel[er.status as keyof typeof statusLabel] ?? er.status}
            </span>
            <code className={styles.topBarJobId}>{jobId}</code>
            {jobRunning && (
              <button
                type="button"
                className={styles.topBarCancel}
                onClick={() => void handleCancel(jobId)}
              >
                {t('pipelines.cancelRun')}
              </button>
            )}
            {!jobRunning && (
              <button
                type="button"
                className={styles.topBarCancel}
                style={{ color: 'var(--text-dim)' }}
                onClick={() => requestDeleteJob(jobId)}
                title={t('jobs.deleteJobAria')}
              >
                <Trash2 size={13} />
                {t('jobs.delete')}
              </button>
            )}
          </div>
        </header>

        <div className={styles.jobDetailView}>
          <div className={styles.jobDetailPane}>
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
                      {t('jobs.backToJob')}
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
                              const page = await api.wikiRead(f.path, er.department);
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
                              const page = await api.wikiRead(f.path, er.department);
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
                    wf.map((f) => (
                      <button
                        key={f.path}
                        type="button"
                        className={`${styles.jobFileLink} ${f.job_role === 'deliverable' ? styles.jobFileLinkDeliverable : ''} ${previewFile?.path === f.path ? styles.jobFileLinkActive : ''}`}
                        title={f.path}
                        onClick={async () => {
                          setPreviewLoading(true);
                          setPreviewFile(null);
                          try {
                            const page = await api.wikiRead(f.path, er.department);
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
                      <span className={`${styles.statusBadge} ${styles[`status_${er.status}`]}`}>
                        {STATUS_ICON[er.status]}
                        {statusLabel[er.status as keyof typeof statusLabel] ?? er.status}
                      </span>
                      {er.mode === 'proactive' && er.proactive_mission_label && (
                        <span className={styles.iterBadge} title={t('dept.proactiveMissionBadge')}>
                          {er.proactive_mission_label}
                        </span>
                      )}
                      {(er.mode === 'deep' || er.mode === 'proactive') &&
                        er.max_iterations != null &&
                        er.max_iterations > 0 && (
                          <>
                            <span className={styles.iterBadge} title={t('dept.phaseProgressTitle')}>
                              {t('dept.phaseProgress', { cur: er.current_iteration ?? 0, total: er.max_iterations })}
                            </span>
                            {(er.progress_pct ?? 0) > 0 && (
                              <span className={styles.iterBadge} title={t('jobs.progressEstimateTitle')}>
                                {er.progress_pct}%
                              </span>
                            )}
                            {er.eval_status && (
                              <span
                                className={styles.iterBadge}
                                title={t('dept.evalStatusTitle')}
                                style={{
                                  borderColor:
                                    er.eval_status === 'GOAL_REACHED'
                                      ? 'var(--green, #22c55e)'
                                      : er.eval_status === 'BUDGET_EXHAUSTED'
                                        ? 'var(--yellow, #eab308)'
                                        : 'var(--border)',
                                }}
                              >
                                {er.eval_status === 'GOAL_REACHED'
                                  ? t('dept.eval.goal')
                                  : er.eval_status === 'BUDGET_EXHAUSTED'
                                    ? t('dept.eval.budget')
                                    : er.eval_status === 'CONTINUE'
                                      ? t('dept.eval.continue')
                                      : t('dept.eval.working')}
                              </span>
                            )}
                          </>
                        )}
                      <span className={styles.detailTime}>{er.elapsed_seconds.toFixed(0)}s</span>
                    </div>

                    {er.history && er.history.length > 0 && (
                      <div className={styles.jobConversation}>
                        {er.history.map((entry, i) => (
                          <div
                            key={i}
                            className={
                              entry.role === 'user' ? styles.jobConvUser : styles.jobConvAssistant
                            }
                          >
                            <div className={styles.jobConvLabel}>
                              {entry.role === 'user' ? t('dept.you') : deptNameLabel}
                            </div>
                            <div className={styles.jobConvBody}>
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.content}</ReactMarkdown>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className={styles.detailSection}>
                      <div className={styles.jobConvUser}>
                        <div className={styles.jobConvLabel}>{t('dept.you')}</div>
                        <div className={styles.jobConvBody}>{er.task ?? er.task_preview ?? '—'}</div>
                      </div>
                    </div>

                    {(er.status === 'running' || er.status === 'pending') && (
                      <div className={styles.detailRunning}>
                        <div className={styles.detailRunningDot} />
                        <span>{t('dept.working')}</span>
                      </div>
                    )}

                    {er.events && er.events.length > 0 && (
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
                                  <div
                                    key={`${iter}-${i}-${ev.ts}`}
                                    className={styles.jobEventThinkingRow}
                                  >
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
                                      <span className={styles.jobEventPreview}>
                                        {ev.preview.slice(0, 120)}
                                      </span>
                                    ) : null}
                                    {ev.detail?.path && (
                                      <span className={styles.jobEventPath} title={ev.detail.path}>
                                        {ev.detail.job_role === 'deliverable' ? t('jobs.deliverablePrefix') : ''}
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

                    {er.error && (
                      <div className={styles.detailError}>
                        <AlertCircle size={14} />
                        {er.error}
                      </div>
                    )}

                    {er.result && (
                      <div className={styles.jobConvAssistant}>
                        <div className={styles.jobConvLabel}>{deptNameLabel}</div>
                        <div className={styles.detailResultBody}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{er.result}</ReactMarkdown>
                        </div>
                      </div>
                    )}

                    {!er.result &&
                      !er.error &&
                      er.status === 'done' &&
                      er.department !== MAIN_WIKI_DEPARTMENT &&
                      !(er.written_files && er.written_files.length > 0) && (
                        <p className={styles.dimText}>{t('jobs.noResult')}</p>
                      )}

                    <div ref={jobChatBottomRef} />
                  </>
                )}
              </div>
            </div>

            {jobDone && (
              <div className={styles.replySection}>
                {(er.status === 'error' || er.status === 'cancelled') && (
                  <div className={styles.retryRow}>
                    <button
                      type="button"
                      className={styles.retryDetailBtn}
                      onClick={() => void handleRetry(jobId)}
                    >
                      <RotateCcw size={14} />
                      {t('jobs.retry')}
                    </button>
                  </div>
                )}
                <div className={styles.replyInputRow}>
                  <input
                    className={styles.replyInput}
                    value={replyInput}
                    onChange={(e) => setReplyInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleReply()}
                    placeholder={t('jobs.replyPlaceholder')}
                    disabled={replying}
                  />
                  <button
                    type="button"
                    className={styles.sendBtn}
                    onClick={handleReply}
                    disabled={replying || !replyInput.trim()}
                    aria-label={t('jobs.reply')}
                  >
                    {replying ? <Loader2 size={15} className={styles.spin} /> : <Send size={15} />}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>{t('jobs.allJobsTitle')}</h2>
        <div className={styles.headerActions}>
          <div className={styles.proactiveWrap} ref={proactiveWrapRef}>
            <button
              type="button"
              className={styles.proactiveBtn}
              disabled={proactiveBusy || departments.length === 0}
              title={
                departments.length === 0
                  ? t('jobs.noDepartments')
                  : t('jobs.proactiveTriggerTitle')
              }
              onClick={() => setProactiveOpen((v) => !v)}
            >
              <Zap size={14} />
              {t('jobs.proactiveRun')}
              <ChevronDown size={14} className={proactiveOpen ? styles.proactiveChevronOpen : undefined} />
            </button>
            {proactiveOpen && (
              <div className={styles.proactiveMenu} role="menu">
                {departmentsError && (
                  <div className={styles.proactiveMenuError}>{departmentsError}</div>
                )}
                {departments.map((d) => (
                  <div key={d.name} className={styles.proactiveDeptBlock}>
                    <div className={styles.proactiveDeptRow}>
                      <span className={styles.proactiveMenuLabel}>{d.label}</span>
                      <span className={styles.proactiveMenuName}>{d.name}</span>
                    </div>
                    <button
                      type="button"
                      role="menuitem"
                      className={styles.proactiveMenuItem}
                      disabled={proactiveBusy}
                      onClick={() => void handleProactiveDept(d.name)}
                    >
                      <span className={styles.proactiveMenuLabel}>{t('jobs.proactiveDefault')}</span>
                    </button>
                    {(d.proactive?.missions ?? []).map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        role="menuitem"
                        className={styles.proactiveMenuItem}
                        disabled={proactiveBusy}
                        onClick={() => void handleProactiveDept(d.name, m.id)}
                      >
                        <span className={styles.proactiveMenuLabel}>{m.label || m.id}</span>
                        <span className={styles.proactiveMenuName}>{m.id}</span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
          <button type="button" className={styles.refreshBtn} onClick={() => void reloadAll()}>
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      <div
        className={
          expandedJob && expandedResult && expandedResult.job_id === expandedJob
            ? `${styles.content} ${styles.contentDetail}`
            : styles.content
        }
      >
        {initialLoaded && items.length === 0 && <p className={styles.empty}>{t('jobs.noJobs')}</p>}

        {expandedJob && expandedResult && expandedResult.job_id === expandedJob
          ? renderJobDetail(expandedJob, expandedResult)
          : items.length > 0 && (
              <div className={styles.tileGrid}>
                {items.map((j) => {
                  const accent = deptAccent(departments, j.department);
                  const label = deptLabel(departments, j.department);
                  return (
                    <div key={j.job_id} className={styles.jobTileWrap}>
                      <button
                        type="button"
                        className={styles.jobTile}
                        style={{ ['--dept-accent' as string]: accent }}
                        onClick={() => void openJob(j.job_id)}
                      >
                        <span className={styles.jobTileAccentBg} aria-hidden />
                        <div className={styles.jobTileInner}>
                          <div className={styles.jobTileTop}>
                            <span className={styles.jobTileStatus} data-status={j.status}>
                              {STATUS_ICON[j.status] ?? null}
                              {j.status}
                            </span>
                            <div className={styles.jobTileActions}>
                              {(j.mode === 'deep' || j.mode === 'proactive') && (
                                <span className={styles.tileModeIcon} title={t('jobs.multiPhase')}>
                                  <Repeat size={12} />
                                </span>
                              )}
                            </div>
                          </div>
                          <div className={styles.jobTileDept}>{label}</div>
                          <div className={styles.jobTileId}>{j.job_id}</div>
                          <div className={styles.jobTileTask}>{j.task_preview ?? '—'}</div>
                          {j.proactive_mission_label && (
                            <div className={styles.jobTileMission}>{j.proactive_mission_label}</div>
                          )}
                          <div className={styles.jobTileMeta}>
                            <span className={styles.jobTileTime}>{j.elapsed_seconds.toFixed(0)}s</span>
                          </div>
                        </div>
                      </button>
                      <div className={styles.jobTileToolbar}>
                        {j.status === 'running' && (
                          <button
                            type="button"
                            className={styles.cancelBtn}
                            onClick={() => void handleCancel(j.job_id)}
                            title={t('pipelines.cancelRun')}
                          >
                            <X size={14} />
                          </button>
                        )}
                        {(j.status === 'error' || j.status === 'cancelled') && (
                          <>
                            <button
                              type="button"
                              className={styles.retryBtn}
                              onClick={() => void handleRetry(j.job_id)}
                              title={t('jobs.retryTitle')}
                            >
                              <RotateCcw size={14} />
                            </button>
                            <button
                              type="button"
                              className={styles.deleteBtn}
                              onClick={() => void handleDelete(j.job_id)}
                              title={t('jobs.deleteJobAria')}
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

        {!expandedJob && items.length > 0 && (
          <div ref={loadMoreRef} className={styles.loadMoreSentinel} aria-hidden>
            {loadingMore && (
              <div className={styles.loadMoreSpinner}>
                <Loader2 size={16} className={styles.spin} />
              </div>
            )}
          </div>
        )}
      </div>

      {jobDeleteConfirm && (
        <div
          className={styles.confirmOverlay}
          role="dialog"
          aria-modal="true"
          aria-label={t('jobs.deleteConfirmTitle')}
        >
          <div className={styles.confirmBox}>
            <div className={styles.confirmTitle}>{t('jobs.deleteConfirmTitle')}</div>
            <p className={styles.confirmBody}>
              {t('jobs.deleteConfirmBodyWithId', { jobId: jobDeleteConfirm.jobId })}
            </p>

            {jobDeleteConfirm.wikiFiles.length > 0 && (
              <div className={styles.jobDeleteWikiSection}>
                <div className={styles.jobDeleteWikiTitle}>{t('jobs.deleteWikiTitle')}</div>
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
                        <span
                          className={`${styles.jobDeleteWikiRole} ${f.job_role === 'deliverable' ? styles.jobDeleteWikiRoleDeliverable : ''}`}
                        >
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
                {t('wiki.cancel')}
              </button>
              <button
                type="button"
                className={styles.confirmBtnDelete}
                onClick={() => void confirmDeleteJob(jobDeleteConfirm)}
              >
                <Trash2 size={13} />
                {jobDeleteConfirm.wikiFiles.some((f) => jobDeleteConfirm.deleteWiki[f.path])
                  ? t('dept.delete.jobAndPages')
                  : t('dept.delete.jobOnly')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
