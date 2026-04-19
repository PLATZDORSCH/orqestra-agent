export interface DeptStreamState {
  loading: boolean;
  steps: { name: string; preview: string }[];
  thinking: string;
}

export const defaultDeptStreamState = (): DeptStreamState => ({
  loading: false,
  steps: [],
  thinking: '',
});

/** User message that triggered a background job. */
export interface DeptUserTurn {
  id: string;
  kind: 'user';
  task: string;
  jobId: string;
}

/** User message in conversational chat mode (no job). */
export interface DeptChatUserTurn {
  id: string;
  kind: 'chat-user';
  text: string;
}

/** Department engine response in chat mode. */
export interface DeptAssistantTurn {
  id: string;
  kind: 'assistant';
  text: string;
}

/** Short system line (e.g. "Job started"). */
export interface DeptSystemTurn {
  id: string;
  kind: 'system';
  text: string;
}

export type DeptChatTurn = DeptUserTurn | DeptChatUserTurn | DeptAssistantTurn | DeptSystemTurn;

export function isUserDeptTurn(t: DeptChatTurn): t is DeptUserTurn {
  return t.kind === 'user';
}

export function isChatUserTurn(t: DeptChatTurn): t is DeptChatUserTurn {
  return t.kind === 'chat-user';
}

export function isAssistantTurn(t: DeptChatTurn): t is DeptAssistantTurn {
  return t.kind === 'assistant';
}
