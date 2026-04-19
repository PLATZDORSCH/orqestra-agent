import { useMemo } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  MessageSquare,
  Briefcase,
  BookOpen,
  Plus,
  LayoutDashboard,
  PenTool,
  Search,
  Settings,
  Building2,
  GitMerge,
} from 'lucide-react';
import type { Department, Job } from '../api/client';
import { useI18n } from '../i18n';
import styles from './Sidebar.module.css';

const DEPT_ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'pen-tool': PenTool,
  search: Search,
  settings: Settings,
  building2: Building2,
};

function DeptIcon({ icon, size = 15 }: { icon?: string | null; size?: number }) {
  const Cmp = (icon && DEPT_ICONS[icon]) || Building2;
  return <Cmp size={size} />;
}

interface Props {
  departments: Department[];
  departmentsError?: string | null;
  jobs?: Job[];
}

export function Sidebar({ departments, departmentsError, jobs = [] }: Props) {
  const { t } = useI18n();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const chatDept = searchParams.get('dept');

  const activeJobsByDept = useMemo(() => {
    const m: Record<string, number> = {};
    for (const j of jobs) {
      if (j.status === 'running' || j.status === 'pending') {
        m[j.department] = (m[j.department] ?? 0) + 1;
      }
    }
    return m;
  }, [jobs]);

  return (
    <nav className={styles.sidebar}>
      <div className={styles.logo}>
        <img src="/orqestra-icon.svg" alt="Orqestra" className={styles.logoMark} />
        <span className={styles.logoText}>Orqestra</span>
      </div>

      <div className={styles.nav}>
        <NavLink
          to="/"
          end
          className={({ isActive }) => (isActive ? styles.active : styles.link)}
        >
          <LayoutDashboard size={15} className={styles.linkIcon} />
          <span>{t('nav.overview')}</span>
        </NavLink>
        <NavLink
          to="/chat"
          className={() => {
            const orqestraOnly = location.pathname === '/chat' && !chatDept;
            return orqestraOnly ? styles.active : styles.link;
          }}
        >
          <MessageSquare size={15} className={styles.linkIcon} />
          <span>{t('nav.chat')}</span>
        </NavLink>
        <NavLink to="/jobs" className={({ isActive }) => (isActive ? styles.active : styles.link)}>
          <Briefcase size={15} className={styles.linkIcon} />
          <span>{t('nav.jobs')}</span>
        </NavLink>
        <NavLink to="/pipelines" className={({ isActive }) => (isActive ? styles.active : styles.link)}>
          <GitMerge size={15} className={styles.linkIcon} />
          <span>{t('nav.pipelines')}</span>
        </NavLink>
        <NavLink to="/wiki" className={({ isActive }) => (isActive ? styles.active : styles.link)}>
          <BookOpen size={15} className={styles.linkIcon} />
          <span>{t('nav.wiki')}</span>
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => (isActive ? styles.active : styles.link)}>
          <Settings size={15} className={styles.linkIcon} />
          <span>{t('nav.settings')}</span>
        </NavLink>

        <div className={styles.divider} />

        <div className={styles.sectionTitle}>{t('nav.departments')}</div>
        <NavLink
          to="/departments/new"
          className={({ isActive }) => (isActive ? styles.active : styles.link)}
        >
          <Plus size={15} className={styles.linkIcon} />
          <span>{t('nav.createDepartment')}</span>
        </NavLink>
        {departments.map((d) => {
          const color = d.color ?? '#16a34a';
          const n = activeJobsByDept[d.name] ?? 0;
          const isDeptActive = chatDept === d.name;
          return (
            <NavLink
              key={d.name}
              to={`/chat?dept=${encodeURIComponent(d.name)}`}
              className={() => (isDeptActive ? styles.active : styles.link)}
            >
              <span
                className={styles.deptIconWrap}
                style={{ borderColor: `${color}55`, color }}
              >
                <DeptIcon icon={d.icon} size={13} />
              </span>
              <span className={styles.deptLabel}>{d.label}</span>
              {n > 0 && <span className={styles.deptBadge}>{n}</span>}
            </NavLink>
          );
        })}
        {departments.length === 0 && !departmentsError && (
          <p className={styles.apiHint}>{t('nav.noDepartments')}</p>
        )}
        {departmentsError && (
          <p className={styles.apiHint}>{t('nav.apiUnreachable')}</p>
        )}
      </div>
    </nav>
  );
}
