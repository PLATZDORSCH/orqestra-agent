import { useEffect, useRef, useState } from 'react';
import { CheckCircle, XCircle, X } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import type { Job } from '../api/client';
import { useI18n } from '../i18n';
import styles from './JobToast.module.css';

interface Props {
  jobs: Job[];
  dismissedIds: Set<string>;
  onDismiss: (jobId: string) => void;
}

const TERMINAL = new Set(['done', 'error', 'cancelled']);
const ACTIVE = new Set(['running', 'pending']);

export function JobToast({ jobs, dismissedIds, onDismiss }: Props) {
  const { t } = useI18n();
  const prevStatusRef = useRef<Record<string, string>>({});
  const [toastIds, setToastIds] = useState<string[]>([]);

  useEffect(() => {
    const newlyDone: string[] = [];
    const next = { ...prevStatusRef.current };
    for (const j of jobs) {
      const prev = prevStatusRef.current[j.job_id];
      if (prev !== undefined && ACTIVE.has(prev) && TERMINAL.has(j.status)) {
        if (!dismissedIds.has(j.job_id)) {
          newlyDone.push(j.job_id);
        }
      }
      next[j.job_id] = j.status;
    }
    prevStatusRef.current = next;
    if (newlyDone.length) {
      setToastIds((prev) => [...new Set([...prev, ...newlyDone])]);
    }
  }, [jobs, dismissedIds]);

  const visible = toastIds
    .filter((id) => !dismissedIds.has(id))
    .map((id) => jobs.find((j) => j.job_id === id))
    .filter(Boolean) as Job[];

  if (visible.length === 0) return null;

  return (
    <div className={styles.stack}>
      {visible.map((j) => (
        <div
          key={j.job_id}
          className={`${styles.toast} ${j.status === 'error' ? styles.error : styles.done}`}
        >
          <div className={styles.icon}>
            {j.status === 'error' ? <XCircle size={18} /> : <CheckCircle size={18} />}
          </div>
          <div className={styles.body}>
            <div className={styles.title}>
              {j.status === 'error' ? t('jobs.toast.failed') : t('jobs.toast.done')}
            </div>
            <div className={styles.meta}>
              <span className={styles.dept}>{j.department}</span>
              <span className={styles.preview}>{j.task_preview ?? j.task ?? '—'}</span>
            </div>
            <NavLink
              to={`/chat?dept=${encodeURIComponent(j.department)}`}
              className={styles.link}
              onClick={() => onDismiss(j.job_id)}
            >
              {t('jobs.toast.toDept')}
            </NavLink>
          </div>
          <button
            type="button"
            className={styles.close}
            onClick={() => onDismiss(j.job_id)}
            aria-label={t('jobs.toast.close')}
          >
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
