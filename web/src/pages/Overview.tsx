import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeChange,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Building2,
  Loader2,
  PenTool,
  Search,
  Settings,
  Zap,
  Clock,
} from 'lucide-react';
import { api, type TopologyDepartment, type TopologyResponse } from '../api/client';
import { useI18n } from '../i18n';
import styles from './Overview.module.css';

const ORQESTRA_NODE_ID = 'orqestra-main';
const POSITIONS_KEY = 'orqestra-overview-node-positions';

type PositionMap = Record<string, { x: number; y: number }>;

function loadPositions(): PositionMap {
  try {
    const raw = localStorage.getItem(POSITIONS_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as PositionMap;
  } catch {
    return {};
  }
}

function savePositions(positions: PositionMap): void {
  try {
    localStorage.setItem(POSITIONS_KEY, JSON.stringify(positions));
  } catch {
    // quota exceeded or private mode — silently ignore
  }
}

const ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'pen-tool': PenTool,
  search: Search,
  settings: Settings,
};

function DeptIcon({ name }: { name: string | null }) {
  const Cmp = (name && ICONS[name]) || Building2;
  return <Cmp size={14} />;
}

function OrchestratorNode({ data }: NodeProps) {
  const { t } = useI18n();
  const label = (data.label as string) ?? 'Orqestra';
  return (
    <div className={styles.orchNode}>
      <Handle type="source" position={Position.Bottom} id="src" />
      <div className={styles.orchBanner} />
      <div className={styles.orchBody}>
        <div>
          <span className={styles.orchPulse} />
          <span className={styles.orchLabel}>{label}</span>
        </div>
        <div className={styles.orchSub}>{t('overview.orchestrator')}</div>
      </div>
    </div>
  );
}

function DepartmentFlowNode({ data, selected }: NodeProps) {
  const { t } = useI18n();
  const d = data as unknown as TopologyDepartment;
  const color = d.color ?? '#16a34a';
  const gradId = `grad-${d.id.replace(/[^a-zA-Z0-9]/g, '')}`;
  return (
    <div
      className={styles.deptNode}
      style={{ borderColor: selected ? color : undefined }}
    >
      <Handle type="target" position={Position.Top} id="tgt" />
      <div className={styles.deptBanner}>
        <svg className={styles.deptBannerSvg} viewBox="0 0 200 40" preserveAspectRatio="none">
          <defs>
            <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0.12} />
            </linearGradient>
          </defs>
          <rect width="200" height="40" fill={`url(#${gradId})`} />
        </svg>
      </div>
      <div className={styles.deptBody}>
        <div className={styles.deptHeader}>
          <span className={styles.deptLabel}>{d.label}</span>
          <span
            className={styles.deptIconWrap}
            style={{ borderColor: `${color}44`, color }}
          >
            <DeptIcon name={d.icon} />
          </span>
        </div>
        <div className={styles.deptMeta}>
          {d.proactive?.enabled && (
            <span
              className={styles.deptBadge}
              title={t('overview.proactiveTooltip', {
                schedule: d.proactive.schedule ?? t('overview.proactiveInherit'),
                n: d.proactive.mission_count,
              })}
            >
              <Clock size={10} />
              {t('overview.proactiveShort')}
            </span>
          )}
          <span className={styles.deptBadge}>
            <Zap size={10} />
            {t('overview.skillsCount', { n: d.skills_count })}
          </span>
          {d.active_jobs > 0 && (
            <span className={`${styles.deptBadge} ${styles.deptBadgeActive}`}>
              {t('overview.activeJobs', { n: d.active_jobs })}
            </span>
          )}
        </div>
        <p className={styles.deptHint}>{t('overview.clickToChat')}</p>
      </div>
    </div>
  );
}

const nodeTypes = {
  orchestrator: OrchestratorNode,
  dept: DepartmentFlowNode,
};

function buildGraph(
  data: TopologyResponse | null,
  savedPositions: PositionMap,
): { nodes: Node[]; edges: Edge[] } {
  if (!data) {
    return { nodes: [], edges: [] };
  }
  const depts = data.departments;
  const cx = 420;
  const cy = 340;
  const n = depts.length;
  const radius = n === 0 ? 0 : Math.max(200, 140 + n * 28);

  const orqestraDefaultPos = { x: cx - 84, y: cy - 52 };
  const nodes: Node[] = [
    {
      id: ORQESTRA_NODE_ID,
      type: 'orchestrator',
      position: savedPositions[ORQESTRA_NODE_ID] ?? orqestraDefaultPos,
      data: { label: data.orchestrator.label },
      draggable: true,
    },
  ];

  const edges: Edge[] = [];

  depts.forEach((d, i) => {
    const angle = n === 1 ? -Math.PI / 2 : (2 * Math.PI * i) / n - Math.PI / 2;
    const defaultX = cx + radius * Math.cos(angle) - 100;
    const defaultY = cy + radius * Math.sin(angle) - 70;
    const color = d.color ?? '#16a34a';
    nodes.push({
      id: d.id,
      type: 'dept',
      position: savedPositions[d.id] ?? { x: defaultX, y: defaultY },
      data: { ...d } as Record<string, unknown>,
      draggable: true,
    });
    edges.push({
      id: `e-${ORQESTRA_NODE_ID}-${d.id}`,
      source: ORQESTRA_NODE_ID,
      sourceHandle: 'src',
      target: d.id,
      targetHandle: 'tgt',
      animated: true,
      style: { stroke: color, strokeOpacity: 0.45 },
    });
  });

  return { nodes, edges };
}

export function Overview() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [topology, setTopology] = useState<TopologyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Stable ref so buildGraph always uses the latest saved positions without
  // being part of the useMemo dependency array (avoids re-building the whole
  // graph on every drag).
  const savedPositionsRef = useRef<PositionMap>(loadPositions());

  const load = useCallback(async () => {
    try {
      setError(null);
      const topo = await api.topology();
      setTopology(topo);
    } catch (e) {
      setTopology(null);
      setError(e instanceof Error ? e.message : t('overview.topologyError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => buildGraph(topology, savedPositionsRef.current),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [topology],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Persist positions on every drag-stop event
  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      onNodesChange(changes);
      const positionChanges = changes.filter(
        (c): c is NodeChange & { type: 'position'; id: string; position?: { x: number; y: number } } =>
          c.type === 'position' && 'position' in c && c.position != null,
      );
      if (positionChanges.length > 0) {
        const updated = { ...savedPositionsRef.current };
        for (const c of positionChanges) {
          if (c.position) updated[c.id] = c.position;
        }
        savedPositionsRef.current = updated;
        savePositions(updated);
      }
    },
    [onNodesChange],
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.type === 'dept') {
        navigate(`/chat?dept=${encodeURIComponent(node.id)}`);
      }
    },
    [navigate],
  );

  if (loading) {
    return (
      <div className={styles.shell}>
        <div className={styles.topBar}>
          <span className={styles.topBarTitle}>{t('overview.title')}</span>
        </div>
        <div className={styles.loadingState}>
          <Loader2 size={20} className={styles.spin} />
          <span>{t('overview.loadingTopology')}</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.shell}>
        <div className={styles.topBar}>
          <span className={styles.topBarTitle}>{t('overview.title')}</span>
        </div>
        <div className={styles.errorState}>{error}</div>
      </div>
    );
  }

  return (
    <div className={styles.shell}>
      <div className={styles.topBar}>
        <span className={styles.topBarTitle}>{t('overview.title')}</span>
        <span className={styles.topBarHint}>{t('overview.hint')}</span>
      </div>
      <div className={styles.flowWrap}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.4}
          maxZoom={1.4}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} size={1} color="var(--border)" />
          <Controls showInteractive={false} />
          <MiniMap
            nodeStrokeWidth={2}
            zoomable
            pannable
            maskColor="rgba(14, 14, 15, 0.85)"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
