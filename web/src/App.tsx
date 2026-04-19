import { useEffect, useState, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { type Message, type ChatStreamState, defaultChatStreamState } from './components/ChatWindow';
import { JobToast } from './components/JobToast';
import { SetupWizard } from './components/SetupWizard';
import { Overview } from './pages/Overview';
import { ChatHub } from './pages/ChatHub';
import { JobsPage } from './pages/JobsPage';
import { PipelinesPage } from './pages/PipelinesPage';
import { WikiPage } from './pages/WikiPage';
import { SettingsPage } from './pages/SettingsPage';
import { DepartmentBuilder } from './pages/DepartmentBuilder';
import { api, type Department, type Job } from './api/client';
import type { DeptChatTurn, DeptStreamState } from './types/deptChat';
import { defaultDeptStreamState } from './types/deptChat';
import { useI18n } from './i18n';

const POLL_MS = 5000;

function RedirectDeptToChat() {
  const { name } = useParams<{ name: string }>();
  const target = name ? `/chat?dept=${encodeURIComponent(name)}` : '/chat';
  return <Navigate to={target} replace />;
}

export default function App() {
  const { t } = useI18n();
  const [showWizard, setShowWizard] = useState(false);
  const [wizardChecked, setWizardChecked] = useState(false);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentsError, setDepartmentsError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [chatStreamState, setChatStreamState] = useState<ChatStreamState>(defaultChatStreamState());
  const [deptMessages, setDeptMessages] = useState<Record<string, DeptChatTurn[]>>({});
  const [deptStreamStates, setDeptStreamStates] = useState<Record<string, DeptStreamState>>({});
  const dismissedJobIdsRef = useRef<Set<string>>(new Set());
  const [dismissedJobIds, setDismissedJobIds] = useState<Set<string>>(new Set());

  const reloadJobs = useCallback(async () => {
    try {
      const res = await api.jobs(0, 20);
      setJobs(res.jobs);
    } catch {
      /* ignore */
    }
  }, []);

  const reloadDepartments = useCallback(async () => {
    try {
      const d = await api.departments();
      setDepartments(d);
      setDepartmentsError(null);
    } catch (e) {
      setDepartments([]);
      setDepartmentsError(e instanceof Error ? e.message : t('app.departmentsLoadError'));
    }
  }, [t]);

  useEffect(() => {
    api.getProject()
      .then((p) => {
        if (!p.configured && !localStorage.getItem('orqestra-wizard-dismissed')) {
          setShowWizard(true);
        }
        setWizardChecked(true);
      })
      .catch(() => setWizardChecked(true));
  }, []);

  const handleWizardComplete = useCallback(() => {
    localStorage.setItem('orqestra-wizard-dismissed', '1');
    setShowWizard(false);
  }, []);

  useEffect(() => {
    void reloadDepartments();
    api.createSession()
      .then((s) => setSessionId(s.session_id))
      .catch(() => {
        setTimeout(() => {
          api.createSession()
            .then((s) => setSessionId(s.session_id))
            .catch(() => { /* server not reachable */ });
        }, 2000);
      });
  }, [reloadDepartments]);

  useEffect(() => {
    reloadJobs();
    const iv = setInterval(reloadJobs, POLL_MS);
    return () => clearInterval(iv);
  }, [reloadJobs]);

  const handleNewChat = useCallback(async () => {
    setMessages([]);
    const s = await api.createSession();
    setSessionId(s.session_id);
  }, []);

  const addDeptTurn = useCallback((deptName: string, turn: DeptChatTurn) => {
    setDeptMessages((prev) => ({
      ...prev,
      [deptName]: [...(prev[deptName] ?? []), turn],
    }));
  }, []);

  const updateChatStreamState = useCallback(
    (patch: Partial<ChatStreamState> | ((s: ChatStreamState) => Partial<ChatStreamState>)) => {
      setChatStreamState((prev) => {
        const changes = typeof patch === 'function' ? patch(prev) : patch;
        return { ...prev, ...changes };
      });
    },
    [],
  );

  const updateDeptStream = useCallback(
    (deptName: string, patch: Partial<DeptStreamState> | ((s: DeptStreamState) => Partial<DeptStreamState>)) => {
      setDeptStreamStates((prev) => {
        const cur = prev[deptName] ?? defaultDeptStreamState();
        const changes = typeof patch === 'function' ? patch(cur) : patch;
        return { ...prev, [deptName]: { ...cur, ...changes } };
      });
    },
    [],
  );

  const handleJobDone = useCallback(
    (job: Job) => {
      addDeptTurn(job.department, {
        id: crypto.randomUUID(),
        kind: 'system',
        text: t('app.jobDoneSystem', {
          jobId: job.job_id,
          err: job.status === 'error' ? t('app.jobDoneError') : '',
        }),
      });
    },
    [addDeptTurn, t],
  );

  const handleDismissToast = useCallback((jobId: string) => {
    dismissedJobIdsRef.current.add(jobId);
    setDismissedJobIds(new Set(dismissedJobIdsRef.current));
  }, []);

  const chatHubProps = {
    departments,
    sessionId,
    messages,
    setMessages,
    onNewChat: handleNewChat,
    chatStreamState,
    updateChatStreamState,
    jobs,
    deptMessages,
    addDeptTurn,
    deptStreamStates,
    updateDeptStream,
    reloadJobs,
    onJobDone: handleJobDone,
    reloadDepartments,
  };

  return (
    <BrowserRouter>
      {showWizard && wizardChecked && <SetupWizard onComplete={handleWizardComplete} />}
      <Sidebar departments={departments} departmentsError={departmentsError} jobs={jobs} />
      <JobToast
        jobs={jobs}
        dismissedIds={dismissedJobIds}
        onDismiss={handleDismissToast}
      />
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/chat" element={<ChatHub {...chatHubProps} />} />
        <Route
          path="/jobs"
          element={
            <JobsPage
              jobs={jobs}
              reloadJobs={reloadJobs}
              departments={departments}
              departmentsError={departmentsError}
            />
          }
        />
        <Route
          path="/pipelines"
          element={
            <PipelinesPage departments={departments} departmentsError={departmentsError} />
          }
        />
        <Route path="/wiki" element={<WikiPage />} />
        <Route
          path="/departments/new"
          element={
            <DepartmentBuilder
              onSuccess={() => {
                void reloadDepartments();
              }}
            />
          }
        />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/departments/:name" element={<RedirectDeptToChat />} />
      </Routes>
    </BrowserRouter>
  );
}
