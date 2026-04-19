import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Plus, Trash2, ChevronRight, Sparkles, Check, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, type SkillDraft, type DepartmentTemplate, type BuilderQaStepId } from '../api/client';
import { useI18n } from '../i18n';
import type { TranslationKey } from '../i18n/types';
import styles from './DepartmentBuilder.module.css';

export interface DepartmentBuilderProps {
  onSuccess?: (departmentName: string) => void;
}

// ── Step definitions ──────────────────────────────────────────────────

interface Step {
  id: BuilderQaStepId;
  question: string;
  context: string;
  placeholder: string;
}

const STEP_IDS: BuilderQaStepId[] = ['domain', 'tasks', 'style', 'knowledge'];

const CAP_ICONS: Record<string, string> = {
  web_search: '🔍',
  fetch_url: '🌐',
  run_script: '⚙️',
  read_data: '📊',
  generate_chart: '📈',
  analyze_page_seo: '🔎',
  axe_wcag_scan: '♿',
};

// ── Helpers ───────────────────────────────────────────────────────────

function defaultPersona(l: string, lang: 'en' | 'de'): string {
  if (lang === 'de') {
    return (
      `# ${l}\n\n` +
      `Du bist der **${l}**-Spezialist. Liefere präzise, nachvollziehbare Ergebnisse und dokumentiere sie im Department-Wiki.\n\n` +
      `## Kernaufgaben\n\n` +
      `- Aufgaben aus dem Gespräch mit dem Nutzer umsetzen\n` +
      `- Relevante Informationen im Wiki strukturieren und pflegen\n` +
      `- Wenn der Auftrag eine URL nennt: zuerst fetch_url, nicht web_search\n` +
      `- web_search nur für neue Quellen nutzen, die nicht bereits verlinkt sind\n` +
      `- Bestehende Wiki-Inhalte vor Duplikaten prüfen (kb_search, kb_list)\n` +
      `- Klare Deliverables für Hintergrundjobs markieren (job_role)\n\n` +
      `## Arbeitsstil\n\n` +
      `- Zuerst Wiki prüfen, dann externe Quellen\n` +
      `- Sachlich und auf den Projektkontext bezogen\n` +
      `- Quellen und Annahmen transparent machen\n` +
      `- Prägnant, aber mit genug Kontext für spätere Nutzung\n\n` +
      `## Wiki-Struktur\n\n` +
      `Speichere Ergebnisse in passenden Ordnern: wiki/akteure/ (Firmen/Personen), ` +
      `wiki/recherche/ (Quellen), wiki/wissen/ (Fachwissen), wiki/ergebnisse/ (Analysen). ` +
      `Bei Ingest den Skill wiki-ingest befolgen.\n`
    );
  }
  return (
    `# ${l}\n\n` +
    `You are the **${l}** specialist. Deliver precise, well-sourced results and document them in the department wiki.\n\n` +
    `## Core tasks\n\n` +
    `- Execute tasks from the user conversation\n` +
    `- Structure and maintain relevant information in the wiki\n` +
    `- If the assignment names a URL, use fetch_url first — not web_search\n` +
    `- Use web_search only for new sources that are not already linked\n` +
    `- Check existing wiki content for duplicates (kb_search, kb_list)\n` +
    `- Mark clear deliverables for background jobs (job_role)\n\n` +
    `## Working style\n\n` +
    `- Check the wiki first, then external sources\n` +
    `- Factual and anchored to the project context\n` +
    `- Make sources and assumptions transparent\n` +
    `- Concise but with enough context for later reuse\n\n` +
    `## Wiki structure\n\n` +
    `Save results in matching folders: wiki/akteure/ (companies/people), ` +
    `wiki/recherche/ (sources), wiki/wissen/ (expertise), wiki/ergebnisse/ (analyses). ` +
    `Follow the wiki-ingest skill on ingest.\n`
  );
}

function slugifyLabel(label: string): string {
  const s = label
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
  if (!s) return '';
  const withLetter = /^[a-z]/.test(s) ? s : `d-${s}`;
  return withLetter.replace(/[^a-z0-9_-]/g, '-').slice(0, 64);
}

// ── Component ─────────────────────────────────────────────────────────

export function DepartmentBuilder({ onSuccess }: DepartmentBuilderProps) {
  const navigate = useNavigate();
  const chatLogRef = useRef<HTMLDivElement>(null);
  const { t, lang } = useI18n();

  const STEPS: Step[] = useMemo(
    () =>
      STEP_IDS.map((id) => ({
        id,
        question: t(`builder.q.${id}.q` as TranslationKey),
        context: t(`builder.q.${id}.ctx` as TranslationKey),
        placeholder: t(`builder.q.${id}.ph` as TranslationKey),
      })),
    [t],
  );
  const WIZARD_STEPS = useMemo(
    () => [
      t('builder.wizardName'),
      t('builder.wizardDescription'),
      t('builder.wizardTools'),
      t('builder.wizardPersona'),
      t('builder.wizardSkills'),
      t('builder.wizardDone'),
    ],
    [t],
  );
  const capLabel = useCallback(
    (c: string) => t(`builder.cap.${c}.label` as TranslationKey, {}),
    [t],
  );
  const capDesc = useCallback(
    (c: string) => t(`builder.cap.${c}.desc` as TranslationKey, {}),
    [t],
  );

  // ─ Wizard state
  const [wizardStep, setWizardStep] = useState(0);

  // ─ Step 0: Name
  const [label, setLabel] = useState('');
  const [name, setName] = useState('');
  const [nameTouched, setNameTouched] = useState(false);

  // ─ Step 1: Guided Q&A (one question at a time)
  const [qaStep, setQaStep] = useState(0);
  const [answers, setAnswers] = useState<string[]>(['', '', '', '']);
  const [currentInput, setCurrentInput] = useState('');
  const [qaLoading] = useState(false);
  const [qaFollowup, setQaFollowup] = useState<string | null>(null);
  const [followupInput, setFollowupInput] = useState('');

  // LLM-generated example chips (per Q&A step; falls back to STEPS[].examples)
  const [dynamicExamples, setDynamicExamples] = useState<string[] | null>(null);
  const [loadingExamples, setLoadingExamples] = useState(false);

  // ─ Step 2: Capabilities
  const [capOptions, setCapOptions] = useState<string[]>([]);
  const [selectedCaps, setSelectedCaps] = useState<Set<string>>(new Set<string>());

  // ─ Step 3: Persona
  const [personaDraft, setPersonaDraft] = useState('');
  const [generatingPersona, setGeneratingPersona] = useState(false);

  // ─ Step 4: Skills
  const [skills, setSkills] = useState<SkillDraft[]>([]);

  // ─ General
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // ─ Templates
  const [templates, setTemplates] = useState<DepartmentTemplate[]>([]);
  const [installingTpl, setInstallingTpl] = useState<string | null>(null);

  // ─ Load templates on mount
  useEffect(() => {
    api.templates().then(setTemplates).catch(() => setTemplates([]));
  }, []);

  // ─ Load capabilities when reaching step 2
  useEffect(() => {
    if (wizardStep === 2 && capOptions.length === 0) {
      api.availableCapabilities().then(setCapOptions).catch(() => setCapOptions([]));
    }
  }, [wizardStep, capOptions.length]);

  // ─ Auto-generate persona when reaching step 3 for the first time
  useEffect(() => {
    if (wizardStep === 3 && !personaDraft && !generatingPersona) {
      void generatePersona();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wizardStep]);

  // ─ Scroll chat log to bottom
  useEffect(() => {
    if (chatLogRef.current) {
      chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight;
    }
  }, [qaStep, qaFollowup]);

  // ─ LLM suggestions for example chips (department-specific)
  useEffect(() => {
    if (wizardStep !== 1 || !label.trim()) return;
    let cancelled = false;
    setLoadingExamples(true);
    setDynamicExamples(null);
    const prevMessages: { role: 'user'; content: string }[] = [];
    for (let i = 0; i < qaStep; i++) {
      const a = answers[i];
      if (!a.trim()) continue;
      prevMessages.push({ role: 'user', content: `${STEPS[i].question}\n\n${a}` });
    }
    const qaStepId = STEPS[qaStep].id as BuilderQaStepId;
    api
      .builderChat({
        messages: prevMessages,
        step: 'suggestions',
        department_name: name.trim() || undefined,
        department_label: label.trim(),
        qa_step: qaStepId,
      })
      .then((res) => {
        if (cancelled) return;
        const s = res.suggestions;
        setDynamicExamples(Array.isArray(s) && s.length > 0 ? s : null);
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn('Department Builder: Vorschlags-LLM fehlgeschlagen', err);
          setDynamicExamples(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingExamples(false);
      });
    return () => {
      cancelled = true;
    };
  }, [wizardStep, qaStep, label, name, answers]);

  const onLabelChange = (v: string) => {
    setLabel(v);
    if (!nameTouched) setName(slugifyLabel(v));
  };

  const onNameChange = (v: string) => {
    setNameTouched(true);
    setName(v.toLowerCase().replace(/[^a-z0-9_-]/g, ''));
  };

  // ── Q&A: confirm an answer and (optionally) get a follow-up ──────────

  const confirmAnswer = useCallback(
    async (value: string) => {
      if (!value.trim() || qaLoading) return;
      const updated = [...answers];
      updated[qaStep] = value.trim();
      setAnswers(updated);
      setCurrentInput('');
      setQaFollowup(null);
      setFollowupInput('');

      const isLast = qaStep === STEPS.length - 1;
      if (!isLast) {
        setQaStep((s) => s + 1);
        return;
      }

      // Last step: all answers collected → move to capabilities
      setWizardStep(2);
    },
    [answers, qaStep, qaLoading],
  );

  const submitFollowup = useCallback(async () => {
    if (!followupInput.trim() || qaLoading) return;
    const updated = [...answers];
    updated[qaStep] = `${updated[qaStep]}\n${followupInput.trim()}`.trim();
    setAnswers(updated);
    setFollowupInput('');
    setQaFollowup(null);
    if (qaStep < STEPS.length - 1) {
      setQaStep((s) => s + 1);
    } else {
      setWizardStep(2);
    }
  }, [answers, followupInput, qaLoading, qaStep]);

  // ── Auto-generate persona from collected answers ─────────────────────

  const generatePersona = useCallback(async () => {
    setGeneratingPersona(true);
    setSubmitError(null);
    const conversationMessages = answers
      .map((a, i) => [
        { role: 'user' as const, content: STEPS[i].question + '\n\n' + a },
      ])
      .flat()
      .filter((m) => m.content.trim() && !m.content.endsWith('\n\n'));

    try {
      const res = await api.builderChat({
        messages: conversationMessages,
        step: 'review',
        department_name: name.trim() || undefined,
        department_label: label.trim() || undefined,
      });

      if (typeof res.persona_draft === 'string' && res.persona_draft.trim()) {
        setPersonaDraft(res.persona_draft.trim());
      } else {
        const l = label.trim() || name.trim() || 'Department';
        setPersonaDraft(defaultPersona(l, lang));
      }

      if (Array.isArray(res.suggested_capabilities) && res.suggested_capabilities.length > 0) {
        setSelectedCaps(new Set(res.suggested_capabilities.filter((c) => typeof c === 'string')));
      }

      if (Array.isArray(res.suggested_skills) && res.suggested_skills.length > 0) {
        setSkills(
          res.suggested_skills.map((s) => ({
            title: String(s.title ?? 'Skill'),
            description: typeof s.description === 'string' ? s.description : '',
            content: typeof s.content === 'string' ? s.content : '',
          })),
        );
      } else {
        setSkills([]);
      }
    } catch {
      const l = label.trim() || name.trim() || 'Department';
      setPersonaDraft(defaultPersona(l, lang));
      setSkills([]);
    } finally {
      setGeneratingPersona(false);
    }
  }, [answers, name, label, lang, STEPS]);

  // ── Capabilities ──────────────────────────────────────────────────────

  const toggleCap = (c: string) => {
    setSelectedCaps((prev) => {
      const n = new Set(prev);
      if (n.has(c)) n.delete(c);
      else n.add(c);
      return n;
    });
  };

  // ── Skills ────────────────────────────────────────────────────────────

  const updateSkill = (idx: number, patch: Partial<SkillDraft>) => {
    setSkills((prev) => prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)));
  };

  const addSkill = () => {
    setSkills((prev) => [
      ...prev,
      {
        title: t('builder.newSkillTitle'),
        description: '',
        content:
          lang === 'de'
            ? '## Wann nutzen\n\n\n\n## Schritte\n\n1. \n'
            : '## When to use\n\n\n\n## Steps\n\n1. \n',
      },
    ]);
  };

  const removeSkill = (idx: number) => {
    setSkills((prev) => prev.filter((_, i) => i !== idx));
  };

  // ── Create ────────────────────────────────────────────────────────────

  const canProceedBasics = useMemo(
    () => /^[a-z][a-z0-9_-]{0,63}$/.test(name.trim()) && label.trim().length >= 2,
    [name, label],
  );

  const handleCreate = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const dept = await api.createDepartment({
        name: name.trim(),
        label: label.trim(),
        persona_content: personaDraft,
        capabilities: Array.from(selectedCaps),
        skills: skills.filter((s) => s.title.trim()),
      });
      onSuccess?.(dept.name);
      navigate(`/chat?dept=${encodeURIComponent(dept.name)}`);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : t('builder.createFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  // ── Render helpers ────────────────────────────────────────────────────

  const currentStep = STEPS[qaStep];
  const exampleChips = dynamicExamples ?? [];

  // ── JSX ───────────────────────────────────────────────────────────────

  return (
    <div className={styles.wrap}>

      {/* Header */}
      <div className={styles.header}>
        <button
          type="button"
          className={`${styles.btn} ${styles.btnGhost}`}
          onClick={() => navigate(-1)}
          style={{ marginBottom: 12 }}
        >
          <ArrowLeft size={16} /> {t('builder.back')}
        </button>
        <h1>{t('builder.headerTitle')}</h1>
        <p>{t('builder.headerSubtitle')}</p>
      </div>

      {/* Templates section */}
      {templates.length > 0 && (
        <div style={{ marginBottom: 24, padding: '16px 20px', border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg-surface, var(--bg))' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 10, color: 'var(--text)' }}>
            <Download size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
            {t('builder.installTemplate')}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
            {templates.map((tpl) => (
              <button
                key={tpl.name}
                disabled={installingTpl !== null}
                style={{
                  textAlign: 'left',
                  padding: '10px 14px',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  background: 'transparent',
                  cursor: installingTpl ? 'not-allowed' : 'pointer',
                  opacity: installingTpl && installingTpl !== tpl.name ? 0.5 : 1,
                  transition: 'border-color 0.15s',
                  color: 'var(--text)',
                }}
                onClick={async () => {
                  setInstallingTpl(tpl.name);
                  try {
                    const result = await api.installTemplate(tpl.name);
                    onSuccess?.(result.name);
                    navigate(`/chat?dept=${encodeURIComponent(result.name)}`);
                  } catch (e) {
                    setSubmitError(e instanceof Error ? e.message : t('builder.installFailed'));
                  } finally {
                    setInstallingTpl(null);
                  }
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.82rem' }}>
                  {lang === 'de' ? tpl.label_de || tpl.label : tpl.label || tpl.label_de}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4, lineHeight: 1.4 }}>
                  {((lang === 'de'
                    ? tpl.description_de || tpl.description
                    : tpl.description || tpl.description_de) || '').slice(0, 120)}
                </div>
                {installingTpl === tpl.name && (
                  <Loader2 size={14} style={{ marginTop: 6, animation: 'spin 1s linear infinite' }} />
                )}
              </button>
            ))}
          </div>
          {submitError && installingTpl === null && (
            <div style={{ color: '#ef4444', fontSize: '0.78rem', marginTop: 8 }}>{submitError}</div>
          )}
        </div>
      )}

      {/* Step progress bar */}
      <div className={styles.progressBar}>
        {WIZARD_STEPS.map((s, i) => (
          <div key={s} className={styles.progressItem}>
            <div className={`${styles.progressDot} ${i < wizardStep ? styles.dotDone : i === wizardStep ? styles.dotActive : ''}`}>
              {i < wizardStep ? <Check size={10} /> : i + 1}
            </div>
            <span className={`${styles.progressLabel} ${i === wizardStep ? styles.progressLabelActive : ''}`}>{s}</span>
          </div>
        ))}
      </div>

      {submitError && <p className={styles.error}>{submitError}</p>}

      {/* ── STEP 0: Name & Label ── */}
      {wizardStep === 0 && (
        <div className={styles.panel}>
          <p className={styles.stepQuestion}>{t('builder.step0Q')}</p>
          <p className={styles.stepContext}>{t('builder.step0Ctx')}</p>

          <div style={{ marginTop: 20 }}>
            <label className={styles.label} htmlFor="dept-label">{t('builder.displayName')}</label>
            <input
              id="dept-label"
              className={styles.input}
              value={label}
              onChange={(e) => onLabelChange(e.target.value)}
              placeholder={t('builder.displayNamePh')}
              autoComplete="off"
              autoFocus
            />
          </div>


          {label && (
            <div style={{ marginTop: 16 }}>
              <label className={styles.label} htmlFor="dept-name">
                {t('builder.technicalName')}{' '}
                <span className={styles.labelNote}>{t('builder.autoGen')}</span>
              </label>
              <input
                id="dept-name"
                className={styles.input}
                value={name}
                onChange={(e) => onNameChange(e.target.value)}
                placeholder={t('builder.technicalNamePh')}
                autoComplete="off"
              />
              {name && !/^[a-z][a-z0-9_-]{0,63}$/.test(name) && (
                <p className={styles.fieldError}>{t('builder.technicalNameInvalid')}</p>
              )}
            </div>
          )}

          <div className={styles.actions}>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnPrimary}`}
              disabled={!canProceedBasics}
              onClick={() => setWizardStep(1)}
            >
              {t('builder.next')} <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 1: Guided Q&A ── */}
      {wizardStep === 1 && (
        <div className={styles.panel}>

          {/* Answered questions summary */}
          {qaStep > 0 && (
            <div className={styles.answeredList} ref={chatLogRef}>
              {answers.slice(0, qaStep).map((ans, i) => (
                <div key={i} className={styles.answeredItem}>
                  <div className={styles.answeredQ}>{STEPS[i].question}</div>
                  <div className={styles.answeredA}>{ans}</div>
                  <button
                    type="button"
                    className={styles.editLink}
                    onClick={() => {
                      setQaStep(i);
                      setCurrentInput(answers[i]);
                      setQaFollowup(null);
                    }}
                  >
                    {t('builder.edit')}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Current question */}
          <div className={styles.questionCard}>
            <div className={styles.questionNum}>
              {t('builder.questionN', { cur: qaStep + 1, total: STEPS.length })}
            </div>
            <p className={styles.stepQuestion}>{currentStep.question}</p>
            <p className={styles.stepContext}>{currentStep.context}</p>

            <textarea
              className={styles.textarea}
              style={{ minHeight: 90, marginTop: 12 }}
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              placeholder={currentStep.placeholder}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && currentInput.trim()) {
                  e.preventDefault();
                  void confirmAnswer(currentInput);
                }
              }}
            />

            {(loadingExamples || exampleChips.length > 0) && (
              <div className={styles.exampleChips} style={{ marginTop: 10, alignItems: 'center' }}>
                {loadingExamples && (
                  <span style={{ display: 'inline-flex', alignItems: 'center', marginRight: 8 }} title={t('builder.suggestionsLoading')}>
                    <Loader2 size={14} className={styles.spin} />
                  </span>
                )}
                {exampleChips.map((ex, chipIdx) => (
                  <button
                    key={`${chipIdx}-${ex.slice(0, 48)}`}
                    type="button"
                    className={styles.chip}
                    onClick={() => setCurrentInput(ex)}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Follow-up answer if present */}
          {qaFollowup && (
            <div className={styles.followupCard}>
              <p className={styles.followupText}>{qaFollowup}</p>
              <textarea
                className={styles.textarea}
                style={{ minHeight: 70 }}
                value={followupInput}
                onChange={(e) => setFollowupInput(e.target.value)}
                placeholder={t('builder.followupPh')}
              />
              <div className={styles.actions}>
                <button
                  type="button"
                  className={`${styles.btn} ${styles.btnPrimary}`}
                  disabled={!followupInput.trim() || qaLoading}
                  onClick={() => void submitFollowup()}
                >
                  {t('builder.next')}
                </button>
                <button
                  type="button"
                  className={`${styles.btn} ${styles.btnGhost}`}
                  onClick={() => {
                    setQaFollowup(null);
                    if (qaStep < STEPS.length - 1) setQaStep((s) => s + 1);
                    else setWizardStep(2);
                  }}
                >
                  {t('builder.skip')}
                </button>
              </div>
            </div>
          )}

          {!qaFollowup && (
            <div className={styles.actions}>
              {qaStep > 0 && (
                <button
                  type="button"
                  className={`${styles.btn} ${styles.btnGhost}`}
                  onClick={() => {
                    setQaStep((s) => s - 1);
                    setCurrentInput(answers[qaStep - 1]);
                    setQaFollowup(null);
                  }}
                >
                  <ArrowLeft size={15} /> {t('builder.back')}
                </button>
              )}
              <button
                type="button"
                className={`${styles.btn} ${styles.btnGhost}`}
                onClick={() => {
                  if (qaStep < STEPS.length - 1) {
                    const updated = [...answers];
                    updated[qaStep] = currentInput.trim() || t('builder.noAnswer');
                    setAnswers(updated);
                    setQaStep((s) => s + 1);
                    setCurrentInput('');
                  } else {
                    setWizardStep(2);
                  }
                }}
              >
                {qaStep < STEPS.length - 1 ? t('builder.skip') : t('builder.doneNext')}
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnPrimary}`}
                disabled={!currentInput.trim() || qaLoading}
                onClick={() => void confirmAnswer(currentInput)}
              >
                {qaLoading ? (
                  <Loader2 size={14} className={styles.spin} />
                ) : qaStep < STEPS.length - 1 ? (
                  <>{t('builder.confirm')} <ChevronRight size={15} /></>
                ) : (
                  <><Sparkles size={14} /> {t('builder.genPersona')}</>
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── STEP 2: Capabilities ── */}
      {wizardStep === 2 && (
        <div className={styles.panel}>
          <p className={styles.stepQuestion}>{t('builder.step2Q')}</p>
          <p className={styles.stepContext}>{t('builder.step2Ctx')}</p>

          <div className={styles.capGrid}>
            {capOptions.map((c) => {
              const icon = CAP_ICONS[c] ?? '🔧';
              const label = capLabel(c) || c;
              const desc = capDesc(c) || c;
              const checked = selectedCaps.has(c);
              return (
                <button
                  key={c}
                  type="button"
                  className={`${styles.capCard} ${checked ? styles.capCardOn : ''}`}
                  onClick={() => toggleCap(c)}
                >
                  <span className={styles.capIcon}>{icon}</span>
                  <span className={styles.capCardText}>
                    <span className={styles.capLabel}>{label}</span>
                    <span className={styles.capDesc}>{desc}</span>
                  </span>
                  <span className={`${styles.capCheck} ${checked ? styles.capCheckOn : ''}`}>
                    {checked && <Check size={12} />}
                  </span>
                </button>
              );
            })}
          </div>

          <div className={styles.actions}>
            <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={() => setWizardStep(1)}>
              <ArrowLeft size={15} /> {t('builder.back')}
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnPrimary}`}
              disabled={selectedCaps.size === 0}
              onClick={() => setWizardStep(3)}
            >
              {t('builder.next')} <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 3: Persona ── */}
      {wizardStep === 3 && (
        <div className={styles.panel}>
          <p className={styles.stepQuestion}>{t('builder.step3Q')}</p>
          <p className={styles.stepContext}>{t('builder.step3Ctx')}</p>

          {generatingPersona ? (
            <div className={styles.generatingBox}>
              <Loader2 size={20} className={styles.spin} />
              <span>{t('builder.generatingPersona')}</span>
            </div>
          ) : (
            <>
              <div className={styles.personaActions}>
                <button
                  type="button"
                  className={`${styles.btn} ${styles.btnGhost}`}
                  onClick={() => void generatePersona()}
                >
                  <Sparkles size={14} /> {t('builder.regenerate')}
                </button>
              </div>
              <div className={styles.split}>
                <div>
                  <label className={styles.label}>{t('builder.editPersona')}</label>
                  <textarea
                    className={styles.textarea}
                    style={{ minHeight: 280 }}
                    value={personaDraft}
                    onChange={(e) => setPersonaDraft(e.target.value)}
                  />
                </div>
                <div>
                  <label className={styles.label}>{t('builder.previewPersona')}</label>
                  <div className={styles.personaPreview}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{personaDraft || t('builder.empty')}</ReactMarkdown>
                  </div>
                </div>
              </div>
            </>
          )}

          <div className={styles.actions}>
            <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={() => setWizardStep(2)}>
              <ArrowLeft size={15} /> {t('builder.back')}
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnPrimary}`}
              disabled={!personaDraft.trim() || generatingPersona}
              onClick={() => setWizardStep(4)}
            >
              {t('builder.next')} <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 4: Skills ── */}
      {wizardStep === 4 && (
        <div className={styles.panel}>
          <p className={styles.stepQuestion}>{t('builder.step4Q')}</p>
          <p className={styles.stepContext}>{t('builder.step4Ctx')}</p>

          {skills.map((s, idx) => (
            <div key={idx} className={styles.skillCard}>
              <div className={styles.skillCardHeader}>
                <span className={styles.skillNum}>{t('builder.skillN', { n: idx + 1 })}</span>
                <button
                  type="button"
                  className={styles.skillRemove}
                  onClick={() => removeSkill(idx)}
                  title={t('builder.skillRemove')}
                >
                  <Trash2 size={13} />
                </button>
              </div>
              <label className={styles.label}>{t('builder.skillTitle')}</label>
              <input
                className={styles.input}
                value={s.title}
                onChange={(e) => updateSkill(idx, { title: e.target.value })}
              />
              <label className={styles.label} style={{ marginTop: 12 }}>{t('builder.skillShortDesc')}</label>
              <input
                className={styles.input}
                value={s.description ?? ''}
                onChange={(e) => updateSkill(idx, { description: e.target.value })}
              />
              <label className={styles.label} style={{ marginTop: 12 }}>
                {t('builder.skillContent')}{' '}
                <span className={styles.labelNote}>{t('builder.skillContentNote')}</span>
              </label>
              <textarea
                className={styles.textarea}
                style={{ minHeight: 120 }}
                value={s.content ?? ''}
                onChange={(e) => updateSkill(idx, { content: e.target.value })}
              />
            </div>
          ))}

          <button type="button" className={`${styles.btn} ${styles.btnGhost}`} style={{ marginTop: 4 }} onClick={addSkill}>
            <Plus size={14} /> {t('builder.addSkill')}
          </button>

          <div className={styles.actions}>
            <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={() => setWizardStep(3)}>
              <ArrowLeft size={15} /> {t('builder.back')}
            </button>
            <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={() => setWizardStep(5)}>
              {t('builder.next')} <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 5: Confirmation ── */}
      {wizardStep === 5 && (
        <div className={styles.panel}>
          <p className={styles.stepQuestion}>{t('builder.step5Q')}</p>
          <p className={styles.stepContext}>{t('builder.step5Ctx')}</p>

          <div className={styles.summaryGrid}>
            <div className={styles.summaryRow}>
              <span className={styles.summaryKey}>{t('builder.summaryName')}</span>
              <span className={styles.summaryVal}>{label} <code className={styles.codeInline}>{name}</code></span>
            </div>
            <div className={styles.summaryRow}>
              <span className={styles.summaryKey}>{t('builder.summaryTools')}</span>
              <span className={styles.summaryVal}>
                {selectedCaps.size > 0
                  ? Array.from(selectedCaps).map((c) => (
                      <span key={c} className={styles.capBadge}>
                        {CAP_ICONS[c] ?? '🔧'} {capLabel(c) || c}
                      </span>
                    ))
                  : <span style={{ color: 'var(--text-dim)' }}>{t('builder.noneVal')}</span>}
              </span>
            </div>
            <div className={styles.summaryRow}>
              <span className={styles.summaryKey}>{t('builder.summarySkills')}</span>
              <span className={styles.summaryVal}>
                {skills.filter((s) => s.title.trim()).length === 0
                  ? <span style={{ color: 'var(--text-dim)' }}>{t('builder.noneVal')}</span>
                  : skills.filter((s) => s.title.trim()).map((s, i) => (
                      <span key={i} className={styles.capBadge}>{s.title}</span>
                    ))}
              </span>
            </div>
            <div className={styles.summaryRow}>
              <span className={styles.summaryKey}>{t('builder.summaryPersona')}</span>
              <span className={styles.summaryVal} style={{ color: 'var(--text-dim)', fontSize: 12 }}>
                {personaDraft.slice(0, 100).replace(/\n/g, ' ')}…
              </span>
            </div>
          </div>

          <div className={styles.actions}>
            <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={() => setWizardStep(4)}>
              <ArrowLeft size={15} /> {t('builder.back')}
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnPrimary}`}
              disabled={submitting || !canProceedBasics || !personaDraft.trim()}
              onClick={() => void handleCreate()}
            >
              {submitting ? <Loader2 size={14} className={styles.spin} /> : <Check size={14} />}
              {t('builder.create')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
