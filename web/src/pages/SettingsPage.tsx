import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { useI18n } from '../i18n';
import styles from './SettingsPage.module.css';

export function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const [form, setForm] = useState({
    name: '',
    type: '',
    location: '',
    focus: '',
    target_market: '',
    notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  type FieldRow = {
    key: keyof typeof form;
    label: string;
    placeholder: string;
    textarea?: boolean;
  };

  const FIELDS: FieldRow[] = useMemo(
    () => [
      { key: 'name', label: t('settings.field.name'), placeholder: t('settings.field.namePh') },
      { key: 'type', label: t('settings.field.type'), placeholder: t('settings.field.typePh') },
      { key: 'location', label: t('settings.field.location'), placeholder: t('settings.field.locationPh') },
      { key: 'focus', label: t('settings.field.focus'), placeholder: t('settings.field.focusPh') },
      {
        key: 'target_market',
        label: t('settings.field.targetMarket'),
        placeholder: t('settings.field.targetMarketPh'),
      },
      {
        key: 'notes',
        label: t('settings.field.notes'),
        placeholder: t('settings.field.notesPh'),
        textarea: true,
      },
    ],
    [t],
  );

  useEffect(() => {
    api
      .getProject()
      .then((p) => {
        setForm({
          name: p.name,
          type: p.type,
          location: p.location,
          focus: p.focus,
          target_market: p.target_market,
          notes: p.notes,
        });
      })
      .catch(() => {});
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.saveProject(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      /* ignore */
    }
    setSaving(false);
  }, [form]);

  return (
    <div className={styles.page}>
      <h1 className={styles.heading}>{t('settings.title')}</h1>
      <p className={styles.sub}>{t('settings.subtitle')}</p>

      <div className={styles.field} style={{ marginBottom: 20 }}>
        <label>{t('settings.uiLanguage')}</label>
        <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
          <button
            type="button"
            className={styles.btnSave}
            style={
              lang === 'de'
                ? undefined
                : { opacity: 0.65, background: 'var(--bg-elevated)', color: 'var(--text)' }
            }
            onClick={() => setLang('de')}
          >
            {t('settings.lang.de')}
          </button>
          <button
            type="button"
            className={styles.btnSave}
            style={
              lang === 'en'
                ? undefined
                : { opacity: 0.65, background: 'var(--bg-elevated)', color: 'var(--text)' }
            }
            onClick={() => setLang('en')}
          >
            {t('settings.lang.en')}
          </button>
        </div>
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
        <button className={styles.btnSave} disabled={saving} onClick={handleSave}>
          {saving ? t('settings.saving') : t('settings.save')}
        </button>
        {saved && <span className={styles.saved}>{t('settings.saved')}</span>}
      </div>
    </div>
  );
}
