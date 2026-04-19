import { useEffect, useRef, useState } from 'react';
import { Loader2, Play, Repeat, Zap } from 'lucide-react';
import { useI18n } from '../i18n';
import popoverStyles from './JobModePopover.module.css';

export interface JobModePopoverProps {
  /** Class for the Play trigger button (e.g. CSS module). */
  triggerClassName: string;
  title?: string;
  disabled?: boolean;
  submitting?: boolean;
  'aria-label'?: string;
  onSelect: (mode: 'single' | 'deep') => void;
}

export function JobModePopover({
  triggerClassName,
  title: titleProp,
  disabled = false,
  submitting = false,
  'aria-label': ariaLabelProp,
  onSelect,
}: JobModePopoverProps) {
  const { t } = useI18n();
  const title = titleProp ?? t('jobs.mode.title');
  const ariaLabel = ariaLabelProp ?? t('jobs.mode.aria');
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as Node;
      if (wrapRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div className={popoverStyles.wrap} ref={wrapRef}>
      <button
        type="button"
        className={triggerClassName}
        title={title}
        disabled={disabled || submitting}
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => {
          if (disabled || submitting) return;
          setOpen((o) => !o);
        }}
      >
        {submitting ? <Loader2 size={14} className={popoverStyles.spin} /> : <Play size={14} />}
      </button>
      {open && (
        <div className={popoverStyles.menu} role="menu" aria-label={t('jobs.mode.menuAria')}>
          <button
            type="button"
            role="menuitem"
            className={popoverStyles.option}
            onClick={() => {
              onSelect('single');
              setOpen(false);
            }}
          >
            <Zap size={16} className={popoverStyles.optionIcon} />
            <span className={popoverStyles.optionBody}>
              <span className={popoverStyles.optionTitle}>{t('jobs.mode.simpleTitle')}</span>
              <span className={popoverStyles.optionDesc}>{t('jobs.mode.simpleDesc')}</span>
            </span>
          </button>
          <div className={popoverStyles.divider} />
          <button
            type="button"
            role="menuitem"
            className={popoverStyles.option}
            onClick={() => {
              onSelect('deep');
              setOpen(false);
            }}
          >
            <Repeat size={16} className={popoverStyles.optionIcon} />
            <span className={popoverStyles.optionBody}>
              <span className={popoverStyles.optionTitle}>{t('jobs.mode.deepTitle')}</span>
              <span className={popoverStyles.optionDesc}>{t('jobs.mode.deepDesc')}</span>
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
