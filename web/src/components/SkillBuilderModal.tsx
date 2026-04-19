import { useCallback, useEffect, useState } from 'react';
import { X, Loader2, Sparkles, Check, ArrowLeft } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, type SkillDraft } from '../api/client';
import { useI18n } from '../i18n';
import styles from './SkillBuilderModal.module.css';

export interface SkillBuilderModalProps {
  open: boolean;
  onClose: () => void;
  departmentName: string;
  departmentLabel: string;
  onSuccess: () => void;
}

export function SkillBuilderModal({
  open,
  onClose,
  departmentName,
  departmentLabel,
  onSuccess,
}: SkillBuilderModalProps) {
  const { t } = useI18n();
  const [step, setStep] = useState<1 | 2>(1);
  const [loadingSuggest, setLoadingSuggest] = useState(false);
  const [suggestions, setSuggestions] = useState<{ title: string; description: string }[]>([]);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [customTitle, setCustomTitle] = useState('');
  const [customDesc, setCustomDesc] = useState('');
  const [generating, setGenerating] = useState(false);
  const [draft, setDraft] = useState<SkillDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setStep(1);
    setSuggestions([]);
    setSelectedIdx(null);
    setCustomTitle('');
    setCustomDesc('');
    setDraft(null);
    setError(null);
    setLoadingSuggest(false);
    setGenerating(false);
    setSaving(false);
  }, []);

  useEffect(() => {
    if (!open) {
      reset();
      return;
    }
    reset();
    let cancelled = false;
    setLoadingSuggest(true);
    setError(null);
    api
      .suggestSkills(departmentName)
      .then((res) => {
        if (cancelled) return;
        setSuggestions(Array.isArray(res.suggested_skills) ? res.suggested_skills : []);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : t('skill.builder.suggestError'));
          setSuggestions([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingSuggest(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, departmentName, reset, t]);

  const pickCard = (idx: number) => {
    setSelectedIdx(idx);
    setCustomTitle('');
    setCustomDesc('');
  };

  const onCustomChange = () => {
    setSelectedIdx(null);
  };

  const canProceedStep1 =
    (selectedIdx !== null && suggestions[selectedIdx]) ||
    (customTitle.trim().length >= 2);

  const handleGenerate = async () => {
    let title: string;
    let description: string;
    if (selectedIdx !== null && suggestions[selectedIdx]) {
      title = suggestions[selectedIdx].title;
      description = suggestions[selectedIdx].description ?? '';
    } else {
      title = customTitle.trim();
      description = customDesc.trim();
    }
    setGenerating(true);
    setError(null);
    try {
      const res = await api.generateSkill(departmentName, title, description);
      setDraft({
        title: res.title || title,
        description: res.description ?? description,
        content: res.content ?? '',
      });
      setStep(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('skill.builder.generateError'));
    } finally {
      setGenerating(false);
    }
  };

  const updateDraft = (patch: Partial<SkillDraft>) => {
    setDraft((d) => (d ? { ...d, ...patch } : d));
  };

  const handleSave = async () => {
    if (!draft?.title.trim() || !draft.content?.trim()) {
      setError(t('skill.builder.titleRequired'));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.saveSkill(departmentName, draft);
      onSuccess();
      onClose();
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('skill.builder.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    onClose();
    reset();
  };

  if (!open) return null;

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="skill-builder-title">
      <div className={styles.dialog}>
        <div className={styles.header}>
          <div>
            <h2 id="skill-builder-title">{t('skill.builder.dialogTitle')}</h2>
            <p className={styles.headerMeta}>{departmentLabel}</p>
          </div>
          <button type="button" className={styles.closeBtn} onClick={handleClose} aria-label={t('common.close')}>
            <X size={18} />
          </button>
        </div>

        <div className={styles.body}>
          {error && <p className={styles.error}>{error}</p>}

          {step === 1 && (
            <>
              <p className={styles.stepHint}>{t('skill.builder.step1Hint')}</p>

              {loadingSuggest ? (
                <div className={styles.loadingBox}>
                  <Loader2 size={18} className={styles.spin} />
                  <span>{t('skill.builder.loadingSuggestLine')}</span>
                </div>
              ) : (
                <div className={styles.suggestGrid}>
                  {suggestions.map((s, idx) => (
                    <button
                      key={`${idx}-${s.title}`}
                      type="button"
                      className={`${styles.suggestCard} ${selectedIdx === idx ? styles.suggestCardActive : ''}`}
                      onClick={() => pickCard(idx)}
                    >
                      <div className={styles.suggestTitle}>{s.title}</div>
                      {s.description && <p className={styles.suggestDesc}>{s.description}</p>}
                    </button>
                  ))}
                </div>
              )}

              <div className={styles.divider}>{t('skill.builder.orCustom')}</div>
              <label className={styles.label} htmlFor="skill-custom-title">
                {t('skill.builder.fieldTitle')}
              </label>
              <input
                id="skill-custom-title"
                className={styles.input}
                value={customTitle}
                onChange={(e) => {
                  setCustomTitle(e.target.value);
                  onCustomChange();
                }}
                placeholder={t('skill.builder.fieldTitlePh')}
                autoComplete="off"
              />
              <label className={styles.label} htmlFor="skill-custom-desc" style={{ marginTop: 12 }}>
                {t('skill.builder.fieldDescOpt')}
              </label>
              <textarea
                id="skill-custom-desc"
                className={styles.textarea}
                value={customDesc}
                onChange={(e) => {
                  setCustomDesc(e.target.value);
                  onCustomChange();
                }}
                placeholder={t('skill.builder.fieldDescPh')}
              />
            </>
          )}

          {step === 2 && draft && (
            <>
              <p className={styles.stepHint}>{t('skill.builder.step2Hint')}</p>
              <label className={styles.label} htmlFor="skill-draft-title">
                {t('skill.builder.fieldTitle')}
              </label>
              <input
                id="skill-draft-title"
                className={styles.input}
                value={draft.title}
                onChange={(e) => updateDraft({ title: e.target.value })}
              />
              <label className={styles.label} htmlFor="skill-draft-desc" style={{ marginTop: 12 }}>
                {t('skill.builder.fieldDesc')}
              </label>
              <input
                id="skill-draft-desc"
                className={styles.input}
                value={draft.description ?? ''}
                onChange={(e) => updateDraft({ description: e.target.value })}
              />
              <label className={styles.label} htmlFor="skill-draft-content" style={{ marginTop: 12 }}>
                {t('skill.builder.contentMd')}
              </label>
              <div className={styles.split}>
                <textarea
                  id="skill-draft-content"
                  className={styles.textarea}
                  style={{ minHeight: 260 }}
                  value={draft.content ?? ''}
                  onChange={(e) => updateDraft({ content: e.target.value })}
                />
                <div>
                  <span className={styles.label}>{t('skill.builder.preview')}</span>
                  <div className={styles.preview}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {draft.content || t('skill.builder.previewEmpty')}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        <div className={styles.footer}>
          {step === 2 ? (
            <>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnGhost}`}
                disabled={generating || saving}
                onClick={() => {
                  setStep(1);
                  setDraft(null);
                  setError(null);
                }}
              >
                <ArrowLeft size={15} /> {t('skill.builder.back')}
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnPrimary}`}
                disabled={saving || !draft?.content?.trim()}
                onClick={() => void handleSave()}
              >
                {saving ? <Loader2 size={15} className={styles.spin} /> : <Check size={15} />}
                {t('skill.builder.save')}
              </button>
            </>
          ) : (
            <>
              <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={handleClose}>
                {t('skill.builder.cancel')}
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnPrimary}`}
                disabled={!canProceedStep1 || generating || loadingSuggest}
                onClick={() => void handleGenerate()}
              >
                {generating ? (
                  <Loader2 size={15} className={styles.spin} />
                ) : (
                  <Sparkles size={15} />
                )}
                {t('skill.builder.generate')}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
