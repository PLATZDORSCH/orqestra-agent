import { useMemo, useState } from 'react';
import { api, type ProjectData } from '../api/client';
import { useI18n } from '../i18n';
import styles from './SetupWizard.module.css';

interface Props {
  onComplete: () => void;
}

export function SetupWizard({ onComplete }: Props) {
  const { t } = useI18n();

  const [form, setForm] = useState({
    name: '',
    type: '',
    location: '',
    focus: '',
    target_market: '',
    notes: '',
  });
  const [saving, setSaving] = useState(false);

  type FieldRow = {
    key: keyof Omit<ProjectData, 'configured'>;
    label: string;
    placeholder: string;
    textarea?: boolean;
  };

  const FIELDS: FieldRow[] = useMemo(
    () => [
      { key: 'name', label: t('setup.field.name'), placeholder: t('setup.field.namePh') },
      { key: 'type', label: t('setup.field.type'), placeholder: t('setup.field.typePh') },
      { key: 'location', label: t('setup.field.location'), placeholder: t('setup.field.locationPh') },
      { key: 'focus', label: t('setup.field.focus'), placeholder: t('setup.field.focusPh') },
      {
        key: 'target_market',
        label: t('setup.field.targetMarket'),
        placeholder: t('setup.field.targetMarketPh'),
      },
      {
        key: 'notes',
        label: t('setup.field.notes'),
        placeholder: t('setup.field.notesPh'),
        textarea: true,
      },
    ],
    [t],
  );

  const hasContent = Object.values(form).some((v) => v.trim());

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.saveProject(form);
    } catch {
      /* best effort */
    }
    onComplete();
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.logo}>
            <div className={styles.logoDot} />
          </div>
          <h2 className={styles.title}>{t('setup.welcomeTitle')}</h2>
          <p className={styles.subtitle}>{t('setup.welcomeSubtitle')}</p>
        </div>

        <div className={styles.fields}>
          {FIELDS.map(({ key, label, placeholder, textarea }) => (
            <div key={key} className={styles.field}>
              <label>{label}</label>
              {textarea ? (
                <textarea
                  placeholder={placeholder}
                  value={form[key]}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  rows={2}
                />
              ) : (
                <input
                  type="text"
                  placeholder={placeholder}
                  value={form[key]}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                />
              )}
            </div>
          ))}
        </div>

        <div className={styles.actions}>
          <button className={styles.btnSkip} onClick={onComplete}>
            {t('setup.skip')}
          </button>
          <button className={styles.btnSave} disabled={!hasContent || saving} onClick={handleSave}>
            {saving ? t('setup.saving') : t('setup.save')}
          </button>
        </div>
      </div>
    </div>
  );
}
