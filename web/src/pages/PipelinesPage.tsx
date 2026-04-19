import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  GitMerge,
  Plus,
  Trash2,
  Play,
  ChevronDown,
  ChevronRight,
  Loader2,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import {
  api,
  type Department,
  type PipelineDefinition,
  type PipelineRunDetail,
  type PipelineRunSummary,
  type PipelineStepDef,
  type PipelineTemplate,
} from '../api/client';
import { useI18n } from '../i18n';
import styles from './PipelinesPage.module.css';

const PH = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;

function extractPlaceholders(steps: { task_template: string; result_key?: string | null }[]): string[] {
  const resultKeys = new Set(steps.map((s) => s.result_key).filter(Boolean) as string[]);
  const seen = new Set<string>();
  const out: string[] = [];
  for (const s of steps) {
    PH.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = PH.exec(s.task_template)) !== null) {
      const k = m[1];
      if (!seen.has(k) && !resultKeys.has(k)) {
        seen.add(k);
        out.push(k);
      }
    }
  }
  return out;
}

function emptyStep(): PipelineStepDef {
  return { department: '', task_template: '', result_key: '', mode: 'deep' };
}

interface Props {
  departments: Department[];
  departmentsError?: string | null;
}

export function PipelinesPage({ departments, departmentsError }: Props) {
  const { t, lang } = useI18n();
  const [pipelines, setPipelines] = useState<PipelineDefinition[]>([]);
  const [runs, setRuns] = useState<PipelineRunSummary[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editOriginalName, setEditOriginalName] = useState<string | null>(null);
  const [draft, setDraft] = useState<PipelineDefinition>({
    name: '',
    label: '',
    description: '',
    steps: [emptyStep()],
  });

  const [runPipelineName, setRunPipelineName] = useState<string>('');
  const [runVars, setRunVars] = useState<Record<string, string>>({});
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const [expandedRun, setExpandedRun] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<PipelineRunDetail | null>(null);
  const [runDetailLoading, setRunDetailLoading] = useState(false);

  const [templates, setTemplates] = useState<PipelineTemplate[]>([]);
  const [templateMsg, setTemplateMsg] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setLoadError(null);
      const [pl, rs, tpls] = await Promise.all([
        api.pipelines(),
        api.pipelineRuns(),
        api.pipelineTemplates().catch(() => [] as PipelineTemplate[]),
      ]);
      setPipelines(pl);
      setRuns(rs);
      setTemplates(tpls);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const anyRunActive = useMemo(
    () => runs.some((r) => r.status === 'running' || r.status === 'pending'),
    [runs],
  );

  useEffect(() => {
    if (!anyRunActive) return;
    const iv = setInterval(() => {
      void api.pipelineRuns().then(setRuns).catch(() => {});
      if (expandedRun) {
        void api
          .pipelineRun(expandedRun)
          .then(setRunDetail)
          .catch(() => {});
      }
    }, 3000);
    return () => clearInterval(iv);
  }, [anyRunActive, expandedRun]);

  const openCreate = () => {
    setEditOriginalName(null);
    setDraft({
      name: '',
      label: '',
      description: '',
      steps: [emptyStep()],
    });
    setEditorOpen(true);
  };

  const openEdit = (p: PipelineDefinition) => {
    setEditOriginalName(p.name);
    setDraft({
      ...p,
      steps: p.steps.length ? p.steps.map((s) => ({ ...s, result_key: s.result_key || '' })) : [emptyStep()],
    });
    setEditorOpen(true);
  };

  const saveDraft = async () => {
    const name = draft.name.trim().toLowerCase();
    if (!name || !draft.label.trim()) {
      setLoadError(t('jobs.nameLabelRequired'));
      return;
    }
    const steps = draft.steps
      .filter((s) => s.department.trim() && s.task_template.trim())
      .map((s) => ({
        department: s.department.trim(),
        task_template: s.task_template,
        result_key: (s.result_key || '').trim() || undefined,
        mode: (s.mode === 'single' || s.mode === 'proactive' ? s.mode : 'deep') as string,
      }));
    if (steps.length === 0) {
      setLoadError(t('pipelines.stepError'));
      return;
    }
    const payload: PipelineDefinition = {
      name,
      label: draft.label.trim(),
      description: draft.description.trim(),
      steps,
    };
    setBusy(true);
    setLoadError(null);
    try {
      if (editOriginalName === null) {
        await api.createPipeline(payload);
      } else {
        await api.updatePipeline(editOriginalName, payload);
      }
      setEditorOpen(false);
      await reload();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const deletePl = async (name: string) => {
    if (!window.confirm(t('pipelines.deleteConfirm', { name }))) return;
    setBusy(true);
    try {
      await api.deletePipeline(name);
      await reload();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const selectedPipeline = pipelines.find((p) => p.name === runPipelineName);
  const runPlaceholders = useMemo(() => {
    if (!selectedPipeline) return [];
    return extractPlaceholders(selectedPipeline.steps);
  }, [selectedPipeline]);

  const startRun = async () => {
    if (!runPipelineName) return;
    setBusy(true);
    setRunMessage(null);
    try {
      await api.startPipelineRun(runPipelineName, runVars);
      setRunMessage(t('jobs.pipelineStarted'));
      await reload();
    } catch (e) {
      setRunMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleExpand = async (runId: string) => {
    if (expandedRun === runId) {
      setExpandedRun(null);
      setRunDetail(null);
      return;
    }
    setExpandedRun(runId);
    setRunDetailLoading(true);
    try {
      const d = await api.pipelineRun(runId);
      setRunDetail(d);
    } catch {
      setRunDetail(null);
    } finally {
      setRunDetailLoading(false);
    }
  };

  const cancelRun = async (runId: string) => {
    setBusy(true);
    try {
      await api.cancelPipelineRun(runId);
      await reload();
      if (expandedRun === runId) {
        const d = await api.pipelineRun(runId).catch(() => null);
        setRunDetail(d);
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteRun = async (runId: string) => {
    if (!window.confirm(t('jobs.removeRunConfirm'))) return;
    setBusy(true);
    try {
      await api.deletePipelineRun(runId);
      if (expandedRun === runId) {
        setExpandedRun(null);
        setRunDetail(null);
      }
      await reload();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const installTemplate = async (name: string) => {
    setBusy(true);
    setTemplateMsg(null);
    try {
      const res = await api.installPipelineTemplate(name);
      if (res.missing_departments.length > 0) {
        setTemplateMsg(
          t('jobs.pipelineMissingDepts', { list: res.missing_departments.join(', ') }),
        );
      } else {
        setTemplateMsg(t('jobs.pipelineInstalled'));
      }
      await reload();
    } catch (e) {
      setTemplateMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const deptNames = departments.map((d) => d.name);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h2>
          <GitMerge size={16} style={{ verticalAlign: 'middle', marginRight: 8 }} />
          {t('pipelines.title')}
        </h2>
        <div className={styles.row}>
          <button type="button" className={styles.btn} onClick={() => void reload()} disabled={busy}>
            <RefreshCw size={14} /> {t('pipelines.refresh')}
          </button>
          <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={openCreate} disabled={busy}>
            <Plus size={14} /> {t('pipelines.newPipeline')}
          </button>
        </div>
      </header>

      <div className={styles.scroll}>
        {departmentsError && <p className={styles.error}>{departmentsError}</p>}
        {loadError && <p className={styles.error}>{loadError}</p>}

        {templates.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionTitle}>{t('pipelines.templatesSection')}</div>
            {templateMsg && (
              <p
                className={
                  templateMsg.includes('Fehlende') || templateMsg.includes('Missing')
                    ? styles.error
                    : styles.success
                }
              >
                {templateMsg}
              </p>
            )}
            <div className={styles.templateGrid}>
              {templates.map((tpl) => (
                <div key={tpl.name} className={`${styles.card} ${tpl.installed ? styles.cardInstalled : ''}`}>
                  <div className={styles.cardTitle}>
                    {lang === 'de' ? tpl.label_de || tpl.label : tpl.label || tpl.label_de}
                  </div>
                  <div className={styles.cardDesc}>
                    {lang === 'de'
                      ? tpl.description_de || tpl.description
                      : tpl.description || tpl.description_de}
                  </div>
                  <div className={styles.templateMeta}>
                    {t('jobs.stepsRequires', {
                      n: tpl.steps_count,
                      depts: tpl.required_departments.join(', '),
                    })}
                  </div>
                  <button
                    type="button"
                    className={`${styles.btn} ${tpl.installed ? '' : styles.btnPrimary}`}
                    disabled={busy || tpl.installed}
                    onClick={() => void installTemplate(tpl.name)}
                    style={{ marginTop: 8 }}
                  >
                    {tpl.installed ? t('jobs.installed') : t('jobs.install')}
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className={styles.section}>
          <div className={styles.sectionTitle}>{t('pipelines.defsSection')}</div>
          {pipelines.length === 0 && (
            <p className={styles.cardDesc}>{t('pipelines.noPipelines')}</p>
          )}
          {pipelines.map((p) => (
            <div key={p.name} className={styles.card}>
              <div className={styles.cardHead}>
                <div>
                  <div className={styles.cardTitle}>{p.label}</div>
                  <div className={styles.mono} style={{ marginTop: 4 }}>
                    {p.name}
                  </div>
                  {p.description && <div className={styles.cardDesc}>{p.description}</div>}
                  <div className={styles.chain}>
                    {p.steps.map((s, i) => (
                      <span key={`${p.name}-${i}`}>
                        {i > 0 && <span className={styles.arrow}> → </span>}
                        <span className={styles.badge}>{s.department}</span>
                      </span>
                    ))}
                  </div>
                </div>
                <div className={styles.row}>
                  <button type="button" className={styles.btn} onClick={() => openEdit(p)} disabled={busy}>
                    {t('pipelines.edit')}
                  </button>
                  <button
                    type="button"
                    className={`${styles.btn} ${styles.btnDanger}`}
                    onClick={() => void deletePl(p.name)}
                    disabled={busy}
                  >
                    <Trash2 size={14} /> {t('pipelines.deletePipelineBtn')}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </section>

        <section className={styles.section}>
          <div className={styles.sectionTitle}>{t('pipelines.startSection')}</div>
          <div className={styles.card}>
            <div className={styles.label}>{t('pipelines.pipelineField')}</div>
            <select
              className={styles.select}
              value={runPipelineName}
              onChange={(e) => {
                setRunPipelineName(e.target.value);
                setRunVars({});
                setRunMessage(null);
              }}
            >
              <option value="">{t('jobs.selectPlaceholder')}</option>
              {pipelines.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.label} ({p.name})
                </option>
              ))}
            </select>
            {selectedPipeline && runPlaceholders.length > 0 && (
              <div className={styles.formGrid} style={{ marginTop: 12 }}>
                {runPlaceholders.map((key) => {
                  const desc = selectedPipeline.variable_descriptions?.[key];
                  return (
                    <div key={key}>
                      <div className={styles.label}>
                        {desc ? desc : `{${key}}`}
                      </div>
                      <input
                        className={styles.input}
                        value={runVars[key] ?? ''}
                        onChange={(e) => setRunVars((v) => ({ ...v, [key]: e.target.value }))}
                        placeholder={desc ?? key}
                      />
                    </div>
                  );
                })}
              </div>
            )}
            <div style={{ marginTop: 12 }}>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnPrimary}`}
                onClick={() => void startRun()}
                disabled={busy || !runPipelineName}
              >
                <Play size={14} /> {t('pipelines.start')}
              </button>
            </div>
            {runMessage && (
              <p className={runMessage.startsWith('HTTP') || runMessage.includes('Missing') ? styles.error : styles.success}>
                {runMessage}
              </p>
            )}
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionTitle}>{t('pipelines.runsSection')}</div>
          {runs.length === 0 && <p className={styles.cardDesc}>{t('pipelines.noRuns')}</p>}
          {runs.map((r) => (
            <div key={r.run_id} className={styles.card}>
              <div
                className={styles.cardHead}
                style={{ cursor: 'pointer', marginBottom: 0 }}
                onClick={() => void toggleExpand(r.run_id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') void toggleExpand(r.run_id);
                }}
                role="button"
                tabIndex={0}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {expandedRun === r.run_id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  <div>
                    <span className={styles.cardTitle}>{r.pipeline}</span>
                    <span className={styles.mono} style={{ marginLeft: 8 }}>
                      {r.run_id}
                    </span>
                    <div className={styles.runMeta}>
                      {t('pipelines.runStep', {
                        cur: Math.min(r.current_step + 1, Math.max(r.total_steps, 1)),
                        total: Math.max(r.total_steps, 1),
                        status: r.status,
                      })}
                      {r.error && ` · ${r.error}`}
                    </div>
                  </div>
                </div>
                <div className={styles.row} onClick={(e) => e.stopPropagation()}>
                  {(r.status === 'running' || r.status === 'pending') && (
                    <button type="button" className={styles.btn} onClick={() => void cancelRun(r.run_id)} disabled={busy}>
                      <XCircle size={14} /> {t('pipelines.cancelRun')}
                    </button>
                  )}
                  <button
                    type="button"
                    className={`${styles.btn} ${styles.btnDanger}`}
                    onClick={() => void deleteRun(r.run_id)}
                    disabled={busy}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {expandedRun === r.run_id && (
                <div className={styles.stepsDetail}>
                  {runDetailLoading && (
                    <span className={styles.row}>
                      <Loader2 size={14} className={styles.spin} /> {t('pipelines.loading')}
                    </span>
                  )}
                  {runDetail && !runDetailLoading && (
                    <>
                      <div className={styles.label}>{t('pipelines.variables')}</div>
                      <pre className={styles.mono} style={{ whiteSpace: 'pre-wrap', marginBottom: 8 }}>
                        {JSON.stringify(runDetail.variables, null, 2)}
                      </pre>
                      {runDetail.steps.map((s, i) => (
                        <div key={i} className={styles.stepLine}>
                          <strong>{s.department}</strong>
                          <span>{s.status}</span>
                          {s.job_id && <span className={styles.mono}>{s.job_id}</span>}
                          {s.error && <span className={styles.error}>{s.error}</span>}
                        </div>
                      ))}
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </section>
      </div>

      {editorOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.45)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
          }}
        >
          <div
            className={styles.card}
            style={{ maxWidth: 640, width: '100%', maxHeight: '90vh', overflowY: 'auto' }}
          >
            <div className={styles.cardTitle} style={{ marginBottom: 12 }}>
              {editOriginalName ? t('pipelines.editTitle') : t('pipelines.newTitle')}
            </div>
            <div className={styles.formGrid}>
              <div>
                <div className={styles.label}>{t('pipelines.nameId')}</div>
                <input
                  className={styles.input}
                  value={draft.name}
                  onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                  disabled={editOriginalName !== null}
                />
              </div>
              <div>
                <div className={styles.label}>{t('pipelines.label')}</div>
                <input
                  className={styles.input}
                  value={draft.label}
                  onChange={(e) => setDraft((d) => ({ ...d, label: e.target.value }))}
                />
              </div>
              <div>
                <div className={styles.label}>{t('pipelines.description')}</div>
                <input
                  className={styles.input}
                  value={draft.description}
                  onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
                />
              </div>
            </div>
            <div className={styles.sectionTitle} style={{ marginTop: 16 }}>
              {t('pipelines.stepsSection')}
            </div>
            {draft.steps.map((s, idx) => (
              <div key={idx} className={styles.stepEditor}>
                <div className={styles.stepEditorHead}>
                  {t('pipelines.stepHead', { n: idx + 1 })}
                  <button
                    type="button"
                    className={styles.btn}
                    onClick={() =>
                      setDraft((d) => ({
                        ...d,
                        steps: d.steps.filter((_, j) => j !== idx),
                      }))
                    }
                  >
                    {t('pipelines.removeStep')}
                  </button>
                </div>
                <div className={styles.label}>{t('pipelines.department')}</div>
                <select
                  className={styles.select}
                  value={s.department}
                  onChange={(e) => {
                    const v = e.target.value;
                    setDraft((d) => {
                      const steps = [...d.steps];
                      steps[idx] = { ...steps[idx], department: v };
                      return { ...d, steps };
                    });
                  }}
                >
                  <option value="">{t('jobs.selectPlaceholder')}</option>
                  {deptNames.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                <div className={styles.label} style={{ marginTop: 8 }}>
                  {t('pipelines.taskTemplate')}
                </div>
                <textarea
                  className={styles.textarea}
                  value={s.task_template}
                  onChange={(e) => {
                    const v = e.target.value;
                    setDraft((d) => {
                      const steps = [...d.steps];
                      steps[idx] = { ...steps[idx], task_template: v };
                      return { ...d, steps };
                    });
                  }}
                />
                <div className={styles.label} style={{ marginTop: 8 }}>
                  result_key (optional)
                </div>
                <input
                  className={styles.input}
                  value={s.result_key ?? ''}
                  onChange={(e) => {
                    const v = e.target.value;
                    setDraft((d) => {
                      const steps = [...d.steps];
                      steps[idx] = { ...steps[idx], result_key: v };
                      return { ...d, steps };
                    });
                  }}
                />
                <div className={styles.label} style={{ marginTop: 8 }}>
                  {t('pipelines.mode')}
                </div>
                <select
                  className={styles.select}
                  value={s.mode || 'deep'}
                  onChange={(e) => {
                    const v = e.target.value;
                    setDraft((d) => {
                      const steps = [...d.steps];
                      steps[idx] = { ...steps[idx], mode: v };
                      return { ...d, steps };
                    });
                  }}
                >
                  <option value="deep">deep</option>
                  <option value="single">single</option>
                  <option value="proactive">proactive</option>
                </select>
              </div>
            ))}
            <button
              type="button"
              className={styles.btn}
              style={{ marginTop: 8 }}
              onClick={() => setDraft((d) => ({ ...d, steps: [...d.steps, emptyStep()] }))}
            >
              <Plus size={14} /> {t('pipelines.addStep')}
            </button>
            <div className={styles.row} style={{ marginTop: 16, justifyContent: 'flex-end' }}>
              <button type="button" className={styles.btn} onClick={() => setEditorOpen(false)} disabled={busy}>
                {t('pipelines.cancel')}
              </button>
              <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={() => void saveDraft()} disabled={busy}>
                {t('pipelines.save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
