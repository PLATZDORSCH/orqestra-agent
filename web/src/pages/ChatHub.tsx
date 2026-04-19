import { useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChatWindow, type Message, type ChatStreamState } from '../components/ChatWindow';
import { DepartmentPage } from './DepartmentPage';
import type { Department, Job } from '../api/client';
import type { DeptChatTurn, DeptStreamState } from '../types/deptChat';
import { useI18n } from '../i18n';
import styles from './ChatHub.module.css';

type StreamPatch = Partial<ChatStreamState> | ((s: ChatStreamState) => Partial<ChatStreamState>);
type DeptStreamPatch = Partial<DeptStreamState> | ((s: DeptStreamState) => Partial<DeptStreamState>);

interface Props {
  departments: Department[];
  sessionId: string | null;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  onNewChat: () => Promise<void>;
  chatStreamState: ChatStreamState;
  updateChatStreamState: (patch: StreamPatch) => void;
  jobs: Job[];
  deptMessages: Record<string, DeptChatTurn[]>;
  addDeptTurn: (deptName: string, turn: DeptChatTurn) => void;
  deptStreamStates: Record<string, DeptStreamState>;
  updateDeptStream: (deptName: string, patch: DeptStreamPatch) => void;
  reloadJobs: () => Promise<void>;
  onJobDone: (job: Job) => void;
  reloadDepartments: () => Promise<void>;
}

export function ChatHub({
  departments,
  sessionId,
  messages,
  setMessages,
  onNewChat,
  chatStreamState,
  updateChatStreamState,
  jobs,
  deptMessages,
  addDeptTurn,
  deptStreamStates,
  updateDeptStream,
  reloadJobs,
  onJobDone,
  reloadDepartments,
}: Props) {
  const { t } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const deptParam = searchParams.get('dept');

  const activeDept = useMemo(() => {
    if (!deptParam) return null;
    return departments.some((d) => d.name === deptParam) ? deptParam : null;
  }, [deptParam, departments]);

  useEffect(() => {
    if (!deptParam || departments.length === 0) return;
    if (!departments.some((d) => d.name === deptParam)) {
      setSearchParams({}, { replace: true });
    }
  }, [deptParam, departments, setSearchParams]);

  const selectOrchestrator = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  const selectDepartment = useCallback(
    (name: string) => {
      setSearchParams({ dept: name }, { replace: true });
    },
    [setSearchParams],
  );

  return (
    <div className={styles.shell}>
      <div className={styles.tabBar} role="tablist" aria-label={t('chathub.tablistAria')}>
        <button
          type="button"
          role="tab"
          aria-selected={!activeDept}
          className={`${styles.tab} ${!activeDept ? styles.tabActive : ''}`}
          onClick={selectOrchestrator}
        >
          <span className={styles.tabOrqestraAvatar}>O</span>
          {t('chathub.orchestrator')}
        </button>
        {departments.map((d) => {
          const color = d.color ?? '#16a34a';
          const isActive = activeDept === d.name;
          return (
            <button
              key={d.name}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`${styles.tab} ${isActive ? styles.tabActive : ''}`}
              style={
                isActive
                  ? { borderBottomColor: color, color: 'var(--text)' }
                  : undefined
              }
              onClick={() => selectDepartment(d.name)}
            >
              <span className={styles.tabDot} style={{ background: color }} />
              {d.label}
            </button>
          );
        })}
      </div>

      <div className={styles.body}>
        {!activeDept ? (
          <ChatWindow
            sessionId={sessionId}
            messages={messages}
            setMessages={setMessages}
            onNewChat={onNewChat}
            streamState={chatStreamState}
            updateStreamState={updateChatStreamState}
            departments={departments}
            reloadJobs={reloadJobs}
          />
        ) : (
          <DepartmentPage
            departmentName={activeDept}
            departments={departments}
            jobs={jobs}
            deptMessages={deptMessages}
            addDeptTurn={addDeptTurn}
            deptStreamStates={deptStreamStates}
            updateDeptStream={updateDeptStream}
            reloadJobs={reloadJobs}
            onJobDone={onJobDone}
            reloadDepartments={reloadDepartments}
          />
        )}
      </div>
    </div>
  );
}
