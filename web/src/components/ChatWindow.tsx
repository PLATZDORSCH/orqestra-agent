import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Paperclip, X, MessageSquare, Play, Zap } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, formatUploadUserMessage, type Department, type ProgressEvent, type UploadResult } from '../api/client';
import { useI18n } from '../i18n';
import { JobModePopover } from './JobModePopover';
import styles from './ChatWindow.module.css';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface ToolStep {
  name: string;
  preview: string;
}

export interface ChatStreamState {
  loading: boolean;
  steps: ToolStep[];
  thinkingLabel: string;
}

export const defaultChatStreamState = (): ChatStreamState => ({
  loading: false,
  steps: [],
  thinkingLabel: '',
});

interface Props {
  sessionId: string | null;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  onNewChat: () => void;
  streamState: ChatStreamState;
  updateStreamState: (patch: Partial<ChatStreamState> | ((s: ChatStreamState) => Partial<ChatStreamState>)) => void;
  /** Departments required for orchestrator background jobs (Play). */
  departments: Department[];
  reloadJobs: () => Promise<void>;
}

const TYPEWRITER_CHARS_PER_TICK = 4;
const TYPEWRITER_INTERVAL_MS = 16;

export function ChatWindow({
  sessionId,
  messages,
  setMessages,
  onNewChat,
  streamState,
  updateStreamState,
  departments,
  reloadJobs,
}: Props) {
  const { t } = useI18n();
  const { loading, steps, thinkingLabel } = streamState;
  const [input, setInput] = useState('');
  const [sendModalOpen, setSendModalOpen] = useState(false);
  const [jobSubmitting, setJobSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pendingAttachment, setPendingAttachment] = useState<
    Pick<UploadResult, 'filename' | 'context_text' | 'is_image'> | null
  >(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamControllerRef = useRef<AbortController | null>(null);

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const [typingFull, setTypingFull] = useState<string | null>(null);
  const [typingDisplayed, setTypingDisplayed] = useState('');
  const typingIndexRef = useRef(0);
  const typingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setPendingAttachment(null);
    setInput('');
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, steps, typingDisplayed]);

  useEffect(() => {
    if (typingFull === null) return;
    typingIndexRef.current = 0;
    setTypingDisplayed('');

    typingIntervalRef.current = setInterval(() => {
      typingIndexRef.current = Math.min(
        typingIndexRef.current + TYPEWRITER_CHARS_PER_TICK,
        typingFull.length,
      );
      setTypingDisplayed(typingFull.slice(0, typingIndexRef.current));

      if (typingIndexRef.current >= typingFull.length) {
        clearInterval(typingIntervalRef.current!);
        typingIntervalRef.current = null;
        setMessages((prev) => [...prev, { role: 'assistant', content: typingFull }]);
        setTypingFull(null);
        setTypingDisplayed('');
      }
    }, TYPEWRITER_INTERVAL_MS);

    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current);
        typingIntervalRef.current = null;
        setMessages((prev) => [...prev, { role: 'assistant', content: typingFull }]);
      }
    };
  }, [typingFull, setMessages]);

  const runChatStream = useCallback(
    (userMsg: string) => {
      if (!sessionId) return;
      updateStreamState({ loading: true, steps: [], thinkingLabel: t('chat.thinking') });

      streamControllerRef.current?.abort();
      const ctrl = api.chatStream(sessionId, userMsg, (ev: ProgressEvent) => {
        if (ev.type === 'tool_call') {
          updateStreamState((s) => ({
            steps: [...s.steps, { name: ev.name ?? '', preview: ev.preview ?? '' }],
          }));
        } else if (ev.type === 'thinking') {
          updateStreamState({ thinkingLabel: ev.name ?? '' });
        } else if (ev.type === 'answer') {
          updateStreamState({ loading: false, steps: [], thinkingLabel: '' });
          if (mountedRef.current) {
            setTypingFull(ev.content ?? '');
          } else {
            setMessages((prev) => [...prev, { role: 'assistant', content: ev.content ?? '' }]);
          }
        } else if (ev.type === 'error') {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: `${t('chat.errorPrefix')} ${ev.error}` },
          ]);
          updateStreamState({ loading: false, steps: [], thinkingLabel: '' });
        }
      });
      streamControllerRef.current = ctrl;
    },
    [sessionId, setMessages, updateStreamState, t],
  );

  const handleSend = useCallback(async () => {
    if (!sessionId || loading || uploading) return;
    const userMsg = input.trim();
    if (!userMsg && !pendingAttachment) return;

    let displayContent: string;
    let streamMessage: string;
    if (pendingAttachment) {
      streamMessage = formatUploadUserMessage(
        pendingAttachment.filename,
        pendingAttachment.context_text,
        pendingAttachment.is_image,
        userMsg,
        {
          kindImage: t('upload.kindImage'),
          kindFile: t('upload.kindFile'),
          wikiHint: t('upload.wikiHint'),
          userTaskLabel: t('upload.userTaskLabel'),
        },
      );
      displayContent = userMsg
        ? `${pendingAttachment.filename}\n${userMsg}`
        : pendingAttachment.filename;
    } else {
      streamMessage = userMsg;
      displayContent = userMsg;
    }

    setInput('');
    setPendingAttachment(null);
    setMessages((prev) => [...prev, { role: 'user', content: displayContent }]);
    runChatStream(streamMessage);
  }, [input, sessionId, loading, uploading, pendingAttachment, setMessages, runChatStream, t]);

  const buildDraftForJob = useCallback(() => {
    const parts: string[] = [];
    if (input.trim()) parts.push(input.trim());
    if (pendingAttachment) {
      parts.push(t('chat.attachmentRef', { name: pendingAttachment.filename }));
    }
    const s = parts.join('\n').trim();
    return s || undefined;
  }, [input, pendingAttachment, t]);

  const handleOrchestratorJob = useCallback(
    async (mode: 'single' | 'deep') => {
      if (!sessionId || loading || uploading || jobSubmitting) return;
      if (departments.length === 0) return;
      if (messages.length === 0 && !buildDraftForJob()) return;
      setJobSubmitting(true);
      try {
        const res = await api.createOrchestratorJob(sessionId, mode, buildDraftForJob());
        const deptLabel =
          departments.find((d) => d.name === res.department)?.label ?? res.department;
        const modeLabel = mode === 'deep' ? t('chat.modeDeep') : t('chat.modeSimple');
        setInput('');
        setPendingAttachment(null);
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: t('chat.jobStarted', {
              jobId: res.job_id,
              dept: deptLabel,
              mode: modeLabel,
              summary: res.task_summary ?? '',
            }),
          },
        ]);
        await reloadJobs();
      } catch (e) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `${t('chat.jobStartFailed')} ${e instanceof Error ? e.message : String(e)}`,
          },
        ]);
      } finally {
        setJobSubmitting(false);
      }
    },
    [
      sessionId,
      loading,
      uploading,
      jobSubmitting,
      departments,
      messages.length,
      buildDraftForJob,
      setMessages,
      reloadJobs,
      t,
    ],
  );

  const canStartOrchestratorJob =
    !loading &&
    !uploading &&
    !jobSubmitting &&
    departments.length > 0 &&
    (messages.length > 0 || !!input.trim() || !!pendingAttachment);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !sessionId) return;
    setUploading(true);
    try {
      const res = await api.upload(file, sessionId);
      setPendingAttachment({
        filename: res.filename,
        context_text: res.context_text,
        is_image: res.is_image,
      });
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `${t('chat.uploadFailed')} ${err instanceof Error ? err.message : String(err)}`,
        },
      ]);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.headerTitle}>{t('chat.title')}</span>
        <button className={styles.newBtn} onClick={onNewChat}>
          {t('chat.newConversation')}
        </button>
      </div>

      <div className={styles.messages}>
        {messages.length === 0 && !loading && (
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>{t('chat.orchestratorEmptyTitle')}</p>
            <p className={styles.emptyHint}>{t('chat.orchestratorEmptyHint')}</p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={styles.messageGroup}>
            {m.role === 'user' ? (
              <div className={styles.userMsg}>
                <div className={styles.msgBody}>{m.content}</div>
              </div>
            ) : (
              <div className={styles.assistantMsg}>
                <div className={styles.msgMeta}>
                  <div className={`${styles.msgAvatar} ${styles.msgAvatarOrqestra}`}>O</div>
                  <span className={styles.msgName}>{t('chat.senderName')}</span>
                </div>
                <div className={styles.msgBody}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        ))}

        {typingFull !== null && (
          <div className={styles.messageGroup}>
            <div className={styles.assistantMsg}>
              <div className={styles.msgMeta}>
                <div className={`${styles.msgAvatar} ${styles.msgAvatarOrqestra}`}>O</div>
                <span className={styles.msgName}>{t('chat.senderName')}</span>
              </div>
              <div className={styles.msgBody}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{typingDisplayed}</ReactMarkdown>
                <span className={styles.typingCursor} />
              </div>
            </div>
          </div>
        )}

        {loading && (
          <div className={styles.progress}>
            <div className={styles.progressHeader}>
              <div className={styles.progressDot} />
              <span className={styles.progressLabel}>
                {thinkingLabel || t('chat.processing')}
              </span>
            </div>
            {steps.length > 0 && (
              <div className={styles.stepList}>
                {steps.map((s, i) => (
                  <div key={i} className={styles.step}>
                    <span className={styles.stepTick}>↳</span>
                    <span className={styles.stepName}>{s.name}</span>
                    {s.preview && (
                      <span className={styles.stepPreview}>{s.preview.slice(0, 60)}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
            {thinkingLabel && steps.length === 0 && (
              <div className={styles.thinking}>{thinkingLabel}…</div>
            )}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className={styles.inputArea}>
        <div className={styles.inputInner}>
          {pendingAttachment && (
            <div className={styles.attachmentChip}>
              <span>{pendingAttachment.is_image ? t('chat.attachmentImage') : t('chat.attachmentFile')}</span>
              <span className={styles.attachmentChipName}>{pendingAttachment.filename}</span>
              <button
                type="button"
                className={styles.attachmentChipRemove}
                onClick={() => setPendingAttachment(null)}
                aria-label={t('chat.removeAttachment')}
              >
                <X size={13} />
              </button>
            </div>
          )}
          <div className={styles.inputRow}>
            <input
              ref={fileInputRef}
              type="file"
              className={styles.hiddenFile}
              accept=".pdf,.doc,.docx,.txt,.md,.csv,.json,.yaml,.yml,.html,.htm,.xml,.jpg,.jpeg,.png,.gif,.webp,image/*"
              onChange={handleFileChange}
              disabled={loading || uploading || !sessionId}
            />
            <button
              type="button"
              className={styles.attachBtn}
              onClick={() => fileInputRef.current?.click()}
              disabled={loading || uploading || !sessionId}
              title={t('chat.attachTitle')}
            >
              {uploading
                ? <Loader2 size={15} className={styles.spin} />
                : <Paperclip size={15} />
              }
            </button>
            <input
              className={styles.input}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (!loading && !uploading && sessionId && (input.trim() || pendingAttachment)) {
                    if (canStartOrchestratorJob) {
                      setSendModalOpen(true);
                    } else {
                      handleSend();
                    }
                  }
                }
              }}
              placeholder={pendingAttachment ? t('chat.placeholderTask') : t('chat.placeholderMessage')}
              disabled={loading || uploading || !sessionId}
            />
            <JobModePopover
              triggerClassName={styles.jobPlayBtn}
              title={t('chat.jobFromConversation')}
              disabled={!canStartOrchestratorJob || !sessionId}
              submitting={jobSubmitting}
              onSelect={(mode) => void handleOrchestratorJob(mode)}
            />
            <button
              className={styles.sendBtn}
              onClick={handleSend}
              disabled={loading || uploading || (!input.trim() && !pendingAttachment)}
              aria-label={t('chat.sendAria')}
            >
              <Send size={14} />
            </button>
          </div>
          <p className={styles.inputHint}>{t('chat.hintEnter')}</p>
        </div>
      </div>

      {sendModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setSendModalOpen(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <p className={styles.modalTitle}>{t('chat.sendModalTitle')}</p>
            <div className={styles.modalOptions}>
              <button
                type="button"
                className={styles.modalOption}
                onClick={() => { setSendModalOpen(false); handleSend(); }}
              >
                <span className={styles.modalOptionIcon}><MessageSquare size={18} /></span>
                <span className={styles.modalOptionBody}>
                  <span className={styles.modalOptionTitle}>{t('chat.sendModalChat')}</span>
                  <span className={styles.modalOptionDesc}>{t('chat.sendModalChatDesc')}</span>
                </span>
              </button>
              <button
                type="button"
                className={styles.modalOption}
                onClick={() => { setSendModalOpen(false); void handleOrchestratorJob('single'); }}
              >
                <span className={`${styles.modalOptionIcon} ${styles.modalOptionIconGreen}`}><Zap size={18} /></span>
                <span className={styles.modalOptionBody}>
                  <span className={styles.modalOptionTitle}>{t('jobs.mode.simpleTitle')}</span>
                  <span className={styles.modalOptionDesc}>{t('jobs.mode.simpleDesc')}</span>
                </span>
              </button>
              <button
                type="button"
                className={styles.modalOption}
                onClick={() => { setSendModalOpen(false); void handleOrchestratorJob('deep'); }}
              >
                <span className={`${styles.modalOptionIcon} ${styles.modalOptionIconGreen}`}><Play size={18} /></span>
                <span className={styles.modalOptionBody}>
                  <span className={styles.modalOptionTitle}>{t('jobs.mode.deepTitle')}</span>
                  <span className={styles.modalOptionDesc}>{t('jobs.mode.deepDesc')}</span>
                </span>
              </button>
            </div>
            <button type="button" className={styles.modalCancel} onClick={() => setSendModalOpen(false)}>
              {t('chat.sendModalCancel')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
