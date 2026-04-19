import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Plus, Trash2, Play, Save } from 'lucide-react';
import {
  api,
  type DepartmentProactive,
  type ProactiveMission,
} from '../api/client';
import { useI18n } from '../i18n';
import styles from './ProactiveTab.module.css';

const SCHEDULE_PRESETS: { id: string; cron: string | null }[] = [
  { id: 'inherit', cron: null },
  { id: 'hourly', cron: '0 * * * *' },
  { id: 'daily', cron: '0 6 * * *' },
  { id: 'weeklyMon', cron: '0 6 * * 1' },
  { id: 'monthly', cron: '0 6 1 * *' },
];

function matchPreset(cron: string | null): string {
  if (cron == null || cron === '') return 'inherit';
  const hit = SCHEDULE_PRESETS.find((p) => p.cron === cron);
  return hit?.id ?? 'custom';
}

function emptyMission(): ProactiveMission {
  return { id: '', label: '', prompt: '' };
}

export interface ProactiveTabProps {
  departmentName: string;
  onSaved: () => Promise<void>;
}

export function ProactiveTab({ departmentName, onSaved }: ProactiveTabProps) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [strategy, setStrategy] = useState<string>('rotate');
  const [schedulePreset, setSchedulePreset] = useState<string>('inherit');
  const [customCron, setCustomCron] = useState('');
  const [missions, setMissions] = useState<ProactiveMission[]>([]);
  const [testingId, setTestingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.getDepartmentProactive(departmentName);
      setEnabled(d.enabled);
      setStrategy(d.strategy || 'rotate');
      const cron = d.schedule ?? null;
      const preset = matchPreset(cron);
      setSchedulePreset(preset);
      if (preset === 'custom' && cron) setCustomCron(cron);
      else setCustomCron('');
      setMissions(d.missions?.length ? d.missions : [emptyMission()]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [departmentName]);

  useEffect(() => {
    void load();
  }, [load]);

  const resolvedSchedule = useMemo(() => {
    if (schedulePreset === 'inherit') return null;
    if (schedulePreset === 'custom') return customCron.trim() || null;
    const p = SCHEDULE_PRESETS.find((x) => x.id === schedulePreset);
    return p?.cron ?? null;
  }, [schedulePreset, customCron]);

  const payload = useMemo(
    (): DepartmentProactive => ({
      enabled,
      schedule: resolvedSchedule,
      strategy,
      missions: missions.filter((m) => m.id.trim()),
    }),
    [enabled, resolvedSchedule, strategy, missions],
  );

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.putDepartmentProactive(departmentName, payload);
      await onSaved();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const handleTestMission = async (missionId: string | undefined) => {
    setTestingId(missionId ?? '__generic__');
    setError(null);
    try {
      await api.triggerDeptProactive(departmentName, missionId);
      await onSaved();
    } catch (e) {
      setError(String(e));
    } finally {
      setTestingId(null);
    }
  };

  const updateMission = (idx: number, patch: Partial<ProactiveMission>) => {
    setMissions((prev) => prev.map((m, i) => (i === idx ? { ...m, ...patch } : m)));
  };

  if (loading) {
    return (
      <div className={styles.loadWrap}>
        <Loader2 size={18} className={styles.spin} aria-hidden />
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      {error && <p className={styles.err}>{error}</p>}

      {/* ── Enable / disable ── */}
      <div className={styles.section}>
        <p className={styles.sectionTitle}>{t('dept.proactive.status')}</p>
        <div className={styles.toggleRow}>
          <button
            type="button"
            role="switch"
            aria-checked={enabled}
            className={`${styles.toggleSwitch} ${enabled ? styles.toggleSwitchOn : ''}`}
            onClick={() => setEnabled((v) => !v)}
          >
            <span className={styles.toggleThumb} />
          </button>
          <span className={styles.toggleLabel} onClick={() => setEnabled((v) => !v)}>
            {enabled ? t('dept.proactive.enabled') : t('dept.proactive.disabled')}
          </span>
        </div>
        <p className={styles.hint} style={{ marginTop: 8 }}>
          {t('dept.proactive.statusHint')}
        </p>
      </div>

      {/* ── Schedule ── */}
      <div className={styles.section}>
        <p className={styles.sectionTitle}>{t('dept.proactive.schedule')}</p>
        <div className={styles.fieldRow}>
          <label className={styles.label}>{t('dept.proactive.schedulePreset')}</label>
          <select
            className={styles.select}
            value={schedulePreset}
            onChange={(e) => {
              const v = e.target.value;
              setSchedulePreset(v);
              if (v !== 'custom') setCustomCron('');
            }}
          >
            <option value="inherit">{t('dept.proactive.preset.inherit')}</option>
            <option value="hourly">{t('dept.proactive.preset.hourly')}</option>
            <option value="daily">{t('dept.proactive.preset.daily')}</option>
            <option value="weeklyMon">{t('dept.proactive.preset.weeklyMon')}</option>
            <option value="monthly">{t('dept.proactive.preset.monthly')}</option>
            <option value="custom">{t('dept.proactive.preset.custom')}</option>
          </select>
          {schedulePreset === 'custom' && (
            <input
              className={styles.input}
              placeholder="0 6 * * *"
              value={customCron}
              onChange={(e) => setCustomCron(e.target.value)}
            />
          )}
          <p className={styles.hint}>{t('dept.proactive.scheduleHint')}</p>
        </div>
      </div>

      {/* ── Strategy ── */}
      <div className={styles.section}>
        <p className={styles.sectionTitle}>{t('dept.proactive.strategy')}</p>
        <div className={styles.radioGroup}>
          {(['rotate', 'random', 'all'] as const).map((s) => (
            <label
              key={s}
              className={`${styles.radioChip} ${strategy === s ? styles.radioChipActive : ''}`}
            >
              <input
                type="radio"
                name="proactive-strat"
                checked={strategy === s}
                onChange={() => setStrategy(s)}
              />
              {s === 'rotate' && t('dept.proactive.strategyRotate')}
              {s === 'random' && t('dept.proactive.strategyRandom')}
              {s === 'all' && t('dept.proactive.strategyAll')}
            </label>
          ))}
        </div>
        <p className={styles.hint} style={{ marginTop: 8 }}>
          {strategy === 'rotate' && t('dept.proactive.strategyHint.rotate')}
          {strategy === 'random' && t('dept.proactive.strategyHint.random')}
          {strategy === 'all'    && t('dept.proactive.strategyHint.all')}
        </p>
      </div>

      {/* ── Missions ── */}
      <div className={styles.section}>
        <p className={styles.sectionTitle}>{t('dept.proactive.missions')}</p>
        <div className={styles.missionList}>
          {missions.map((m, idx) => (
            <div key={idx} className={styles.missionCard}>
              <div className={styles.missionCardHead}>
                <span className={styles.missionIndex}>{idx + 1}</span>
                <input
                  className={styles.missionIdInput}
                  placeholder="mission-id"
                  value={m.id}
                  onChange={(e) => updateMission(idx, { id: e.target.value })}
                />
                <input
                  className={styles.missionLabelInput}
                  placeholder={t('dept.proactive.missionLabel')}
                  value={m.label}
                  onChange={(e) => updateMission(idx, { label: e.target.value })}
                />
                <div className={styles.missionCardActions}>
                  <button
                    type="button"
                    className={`${styles.btnIcon} ${styles.btnPlayMission}`}
                    disabled={!m.id.trim() || testingId !== null}
                    title={t('dept.proactive.testMission')}
                    onClick={() => void handleTestMission(m.id.trim())}
                  >
                    {testingId === m.id ? (
                      <Loader2 size={13} className={styles.spin} />
                    ) : (
                      <Play size={13} />
                    )}
                  </button>
                  <button
                    type="button"
                    className={`${styles.btnIcon} ${styles.btnDelete}`}
                    onClick={() => setMissions((prev) => prev.filter((_, i) => i !== idx))}
                    title={t('dept.proactive.removeMission')}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
              <div className={styles.missionCardBody}>
                <textarea
                  className={styles.textarea}
                  placeholder={t('dept.proactive.missionPrompt')}
                  value={m.prompt}
                  onChange={(e) => updateMission(idx, { prompt: e.target.value })}
                />
              </div>
            </div>
          ))}
        </div>
        <button
          type="button"
          className={styles.btnAdd}
          onClick={() => setMissions((prev) => [...prev, emptyMission()])}
        >
          <Plus size={13} />
          {t('dept.proactive.addMission')}
        </button>
      </div>

      {/* ── Toolbar ── */}
      <div className={styles.toolbar}>
        <button
          type="button"
          className={styles.btnSecondary}
          disabled={testingId !== null}
          onClick={() => void handleTestMission(undefined)}
        >
          {testingId === '__generic__' ? (
            <Loader2 size={13} className={styles.spin} />
          ) : (
            <Play size={13} />
          )}
          {t('dept.proactive.testGeneric')}
        </button>
        <button
          type="button"
          className={styles.btnPrimary}
          disabled={saving}
          onClick={() => void handleSave()}
        >
          {saving ? <Loader2 size={13} className={styles.spin} /> : <Save size={13} />}
          {t('dept.proactive.save')}
        </button>
      </div>
    </div>
  );
}
