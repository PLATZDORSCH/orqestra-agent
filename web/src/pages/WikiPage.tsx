import { useState, useEffect, useCallback, useRef, useMemo, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Search,
  Loader2,
  BookOpen,
  ChevronRight,
  FolderOpen,
  FileText,
  Share2,
  Home,
  Clock,
  Trash2,
  Briefcase,
  Plus,
  ChevronsDownUp,
  ChevronsUpDown,
  Download,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ForceGraph2D from 'react-force-graph-2d';
import {
  api,
  type WikiTree,
  type WikiTreeSection,
  type WikiPage as WikiPageData,
  type WikiSearchHit,
  type WikiGraph,
  type WikiGraphNode,
  type WikiHome,
} from '../api/client';
import { useI18n } from '../i18n';
import styles from './WikiPage.module.css';

function cleanSnippet(s: string): string {
  return s.replace(/>>|<</g, '');
}

type Tab = 'pages' | 'graph';

const DEPT_COLORS: Record<string, string> = {};
const COLOR_PALETTE = [
  '#22c55e', '#3b82f6', '#f59e0b', '#ef4444',
  '#16a34a', '#ec4899', '#14b8a6', '#f97316',
];

function colorForDept(dept: string | null): string {
  if (!dept) return '#22c55e';
  if (!DEPT_COLORS[dept]) {
    DEPT_COLORS[dept] = COLOR_PALETTE[Object.keys(DEPT_COLORS).length % COLOR_PALETTE.length];
  }
  return DEPT_COLORS[dept];
}

/* localStorage keys for sidebar state persistence */
const LS_EXPANDED_SECTIONS = 'orq.wiki.expandedSections';
const LS_EXPANDED_FOLDERS = 'orq.wiki.expandedFolders';

function loadSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? new Set(arr.filter((x): x is string => typeof x === 'string')) : new Set();
  } catch {
    return new Set();
  }
}

function saveSet(key: string, set: Set<string>) {
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(set)));
  } catch {
    /* ignore quota / disabled */
  }
}

/** Count total pages across every folder of a section. */
function sectionPageCount(section: WikiTreeSection): number {
  let total = 0;
  for (const entries of Object.values(section.folders)) total += entries.length;
  return total;
}

/** Resolve which folder contains a given page path. Returns folder key or null. */
function findFolderOfPath(section: WikiTreeSection, path: string): string | null {
  for (const [folder, entries] of Object.entries(section.folders)) {
    if (entries.some((e) => e.path === path)) return folder;
  }
  return null;
}

export function WikiPage() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>('pages');
  const [tree, setTree] = useState<WikiTree | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState<WikiPageData | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const [activePath, setActivePath] = useState<{ path: string; dept?: string } | null>(null);
  const [showHome, setShowHome] = useState(true);
  const [home, setHome] = useState<WikiHome | null>(null);

  // Auto-index: rendered when a section has no index_path
  const [autoIndex, setAutoIndex] = useState<{ section: WikiTreeSection; dept?: string } | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<WikiSearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // PDF export
  const [exportingPdf, setExportingPdf] = useState(false);

  // Tree expand state — persisted in localStorage
  const [expandedSections, setExpandedSectionsState] = useState<Set<string>>(() => loadSet(LS_EXPANDED_SECTIONS));
  const [expandedFolders, setExpandedFoldersState] = useState<Set<string>>(() => loadSet(LS_EXPANDED_FOLDERS));

  const setExpandedSections = useCallback((updater: Set<string> | ((prev: Set<string>) => Set<string>)) => {
    setExpandedSectionsState((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      saveSet(LS_EXPANDED_SECTIONS, next);
      return next;
    });
  }, []);

  const setExpandedFolders = useCallback((updater: Set<string> | ((prev: Set<string>) => Set<string>)) => {
    setExpandedFoldersState((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      saveSet(LS_EXPANDED_FOLDERS, next);
      return next;
    });
  }, []);

  // Graph
  const [graph, setGraph] = useState<WikiGraph | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<WikiGraphNode | null>(null);
  const [showGraphLabels, setShowGraphLabels] = useState(true);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const [graphDimensions, setGraphDimensions] = useState({ width: 800, height: 600 });

  /** Last wiki-ingest job id (shown as banner link to /jobs) */
  const [ingestJobId, setIngestJobId] = useState<string | null>(null);

  // Load tree + home on mount; open page from URL params (?path=...&dept=...)
  useEffect(() => {
    const urlPath = searchParams.get('path');
    const urlDept = searchParams.get('dept') || undefined;
    Promise.all([api.wikiTree(), api.wikiHome()])
      .then(([t, h]) => {
        setTree(t);
        setHome(h);

        // Smart-open: if URL points to a specific page/dept, open just that
        // section + the folder containing the page. Otherwise keep whatever
        // state was persisted in localStorage.
        if (urlPath) {
          const deptKey = urlDept ?? 'main';
          const section =
            urlDept === '__personal__'
              ? t.personal
              : urlDept
              ? t.departments[urlDept]
              : t.main;
          if (section) {
            const folder = findFolderOfPath(section, urlPath);
            setExpandedSections((prev) => new Set([...prev, deptKey]));
            if (folder) {
              setExpandedFolders((prev) => new Set([...prev, `${deptKey}/${folder}`]));
            }
          }
          setShowHome(false);
          loadPage(urlPath, urlDept);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Resize graph
  useEffect(() => {
    if (tab !== 'graph' || !graphContainerRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setGraphDimensions({ width, height });
    });
    ro.observe(graphContainerRef.current);
    return () => ro.disconnect();
  }, [tab]);

  // Load graph when switching to graph tab
  useEffect(() => {
    if (tab !== 'graph' || graph) return;
    setGraphLoading(true);
    api.wikiGraph()
      .then(setGraph)
      .catch(() => {})
      .finally(() => setGraphLoading(false));
  }, [tab, graph]);

  // Search with debounce
  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    searchTimeout.current = setTimeout(async () => {
      try {
        const hits = await api.wikiSearch(searchQuery.trim());
        setSearchResults(hits);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => { if (searchTimeout.current) clearTimeout(searchTimeout.current); };
  }, [searchQuery]);

  const loadPage = useCallback((path: string, department?: string) => {
    setActivePath({ path, dept: department });
    setPageLoading(true);
    setSearchResults(null);
    setSearchQuery('');
    setShowHome(false);
    setAutoIndex(null);
    api.wikiRead(path, department)
      .then(setPage)
      .catch(() => setPage(null))
      .finally(() => setPageLoading(false));
  }, []);

  // Auto-expand sidebar section+folder when active page changes
  useEffect(() => {
    if (!activePath || !tree) return;
    const dept = activePath.dept;
    const sectionKey = dept ?? 'main';
    const section =
      dept === '__personal__' ? tree.personal
        : dept ? tree.departments[dept]
        : tree.main;
    if (!section) return;
    const folder = findFolderOfPath(section, activePath.path);
    setExpandedSections((prev) => (prev.has(sectionKey) ? prev : new Set([...prev, sectionKey])));
    if (folder) {
      const folderKey = `${sectionKey}/${folder}`;
      setExpandedFolders((prev) => (prev.has(folderKey) ? prev : new Set([...prev, folderKey])));
    }
  }, [activePath, tree, setExpandedSections, setExpandedFolders]);

  const reloadTree = useCallback(() => {
    Promise.all([api.wikiTree(), api.wikiHome()])
      .then(([t, h]) => {
        setTree(t);
        setHome(h);
        setGraph(null);
      })
      .catch(() => {});
  }, []);

  const handleWikiIngest = useCallback(
    async (files: FileList, department?: string) => {
      let lastJobId: string | null = null;
      for (const file of Array.from(files)) {
        try {
          const res = await api.wikiIngest(file, department);
          lastJobId = res.job_id;
        } catch (err) {
          console.error('wikiIngest failed', file.name, err);
        }
      }
      if (lastJobId) setIngestJobId(lastJobId);
      reloadTree();
    },
    [reloadTree],
  );

  const goHome = useCallback(() => {
    setShowHome(true);
    setPage(null);
    setActivePath(null);
    setSearchResults(null);
    setSearchQuery('');
    setAutoIndex(null);
  }, []);

  const handleExportPdf = useCallback(async () => {
    if (!activePath || !page) return;
    setExportingPdf(true);
    try {
      const blob = await api.wikiExportPdf(activePath.path, activePath.dept);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const base = (page.title || activePath.path.split('/').pop() || 'page')
        .trim()
        .toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s-]+/g, '-') || 'page';
      a.download = `${base}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('wikiExportPdf failed', err);
    } finally {
      setExportingPdf(false);
    }
  }, [activePath, page]);

  const handleDelete = useCallback(async () => {
    if (!activePath) return;
    setDeleting(true);
    try {
      await api.wikiDelete(activePath.path, activePath.dept);
      setShowDeleteConfirm(false);
      setPage(null);
      setActivePath(null);
      setShowHome(true);
      reloadTree();
    } catch {
      /* ignore */
    } finally {
      setDeleting(false);
    }
  }, [activePath, reloadTree]);

  /**
   * Open a section's overview: prefer its index page; fall back to a
   * client-side auto-generated outline when no index exists.
   */
  const openSection = useCallback((deptKey: string | null) => {
    if (!tree) return;
    const section =
      deptKey === null ? tree.main
        : deptKey === '__personal__' ? tree.personal
        : tree.departments[deptKey];
    if (!section) return;
    setExpandedSections((prev) => new Set([...prev, deptKey ?? 'main']));
    if (section.index_path) {
      const dept = deptKey === null ? undefined : deptKey;
      loadPage(section.index_path, dept);
    } else {
      setShowHome(false);
      setPage(null);
      setActivePath(null);
      setSearchResults(null);
      setSearchQuery('');
      setAutoIndex({ section, dept: deptKey === null ? undefined : deptKey });
    }
  }, [tree, loadPage, setExpandedSections]);

  const toggleSection = (key: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const toggleFolder = (key: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const collapseAll = useCallback(() => {
    setExpandedSections(new Set());
    setExpandedFolders(new Set());
  }, [setExpandedSections, setExpandedFolders]);

  const expandAll = useCallback(() => {
    if (!tree) return;
    const sections = new Set<string>(['main']);
    const folders = new Set<string>();
    const collect = (key: string, section: WikiTreeSection) => {
      sections.add(key);
      for (const folder of Object.keys(section.folders)) folders.add(`${key}/${folder}`);
    };
    collect('main', tree.main);
    if (tree.personal) collect('__personal__', tree.personal);
    for (const [name, section] of Object.entries(tree.departments)) collect(name, section);
    setExpandedSections(sections);
    setExpandedFolders(folders);
  }, [tree, setExpandedSections, setExpandedFolders]);

  // Make Markdown links within wiki pages clickable and navigate internally
  const markdownComponents = useMemo(() => ({
    a: ({ href, children }: { href?: string; children?: ReactNode }) => {
      if (!href) return <a>{children}</a>;
      if (href.startsWith('/wiki?')) {
        const handleDeptWikiClick = (e: React.MouseEvent) => {
          e.preventDefault();
          try {
            const u = new URL(href, window.location.origin);
            const dept = u.searchParams.get('dept') || undefined;
            const path = u.searchParams.get('path');
            if (path) loadPage(path, dept);
          } catch {
            /* ignore */
          }
        };
        return (
          <a href={href} onClick={handleDeptWikiClick} style={{ cursor: 'pointer' }}>
            {children}
          </a>
        );
      }
      if (href.endsWith('.md') && !href.startsWith('http')) {
        const handleClick = (e: React.MouseEvent) => {
          e.preventDefault();
          let resolvedPath = href;
          if (activePath && href.startsWith('../')) {
            const baseParts = activePath.path.split('/').slice(0, -1);
            const hrefParts = href.split('/');
            for (const part of hrefParts) {
              if (part === '..') baseParts.pop();
              else baseParts.push(part);
            }
            resolvedPath = baseParts.join('/');
          } else if (activePath && !href.startsWith('wiki/')) {
            const baseParts = activePath.path.split('/').slice(0, -1);
            resolvedPath = [...baseParts, href].join('/');
          }
          loadPage(resolvedPath, activePath?.dept);
        };
        return (
          <a href={href} onClick={handleClick} style={{ cursor: 'pointer' }}>
            {children}
          </a>
        );
      }
      return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
    },
  }), [activePath, loadPage]);

  // Graph data
  const graphData = useMemo(() => {
    if (!graph) return { nodes: [], links: [] };
    return {
      nodes: graph.nodes.map((n) => ({ ...n, color: colorForDept(n.department) })),
      links: graph.edges.map((e) => ({
        source: e.source,
        target: e.target,
        type: e.type,
      })),
    };
  }, [graph]);

  const deptLabels = useMemo(() => {
    if (!graph) return [];
    const seen = new Map<string | null, string>();
    for (const n of graph.nodes) {
      if (!seen.has(n.department)) seen.set(n.department, n.department_label);
    }
    return Array.from(seen.entries()).map(([dept, label]) => ({
      dept, label, color: colorForDept(dept),
    }));
  }, [graph]);

  // Breadcrumbs for the current view
  const breadcrumbs = useMemo(() => {
    if (!tree) return [] as { label: string; onClick?: () => void }[];
    const crumbs: { label: string; onClick?: () => void }[] = [
      { label: 'Wissensdatenbank', onClick: goHome },
    ];
    const deptOfView = activePath?.dept ?? autoIndex?.dept;
    if (deptOfView || activePath || autoIndex) {
      let sectionLabel = tree.main.label;
      let deptKey: string | null = null;
      if (deptOfView === '__personal__' && tree.personal) {
        sectionLabel = tree.personal.label;
        deptKey = '__personal__';
      } else if (deptOfView && tree.departments[deptOfView]) {
        sectionLabel = tree.departments[deptOfView].label;
        deptKey = deptOfView;
      }
      crumbs.push({ label: sectionLabel, onClick: () => openSection(deptKey) });
    }
    if (activePath) {
      const sectionKey = activePath.dept ?? 'main';
      const section =
        activePath.dept === '__personal__' ? tree.personal
          : activePath.dept ? tree.departments[activePath.dept]
          : tree.main;
      if (section) {
        const folder = findFolderOfPath(section, activePath.path);
        if (folder && folder !== '_root') {
          crumbs.push({
            label: folder,
            onClick: () => {
              setExpandedSections((prev) => new Set([...prev, sectionKey]));
              setExpandedFolders((prev) => new Set([...prev, `${sectionKey}/${folder}`]));
            },
          });
        }
        const entry = Object.values(section.folders)
          .flat()
          .find((e) => e.path === activePath.path);
        if (entry) crumbs.push({ label: entry.title });
      }
    }
    return crumbs;
  }, [tree, activePath, autoIndex, goHome, openSection, setExpandedSections, setExpandedFolders]);

  if (loading) {
    return (
      <div className={styles.shell}>
        <div className={styles.loadingState}>
          <Loader2 size={20} className={styles.spin} />
          <span>{t('wiki.loading')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.shell}>
      {/* Top bar */}
      <header className={styles.topBar}>
        <button type="button" className={styles.iconBtn} onClick={goHome} title={t('wiki.homeTitle')}>
          <Home size={15} />
        </button>
        <span className={styles.topBarTitle}>{t('wiki.title')}</span>
        {tab !== 'graph' && (
          <div className={styles.searchWrap}>
            <Search size={14} className={styles.searchIcon} />
            <input
              className={styles.searchInput}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('wiki.searchPlaceholder')}
            />
          </div>
        )}
        <div className={styles.topBarSpacer} />
        <button
          type="button"
          className={`${styles.iconBtn} ${tab === 'graph' ? styles.iconBtnActive : ''}`}
          onClick={() => setTab(tab === 'graph' ? 'pages' : 'graph')}
          title={tab === 'graph' ? 'Seitenansicht' : 'Link-Graph'}
          aria-label="Graph umschalten"
        >
          {tab === 'graph' ? <FileText size={14} /> : <Share2 size={14} />}
        </button>
      </header>

      {ingestJobId && (
        <div className={styles.ingestJobBanner} role="status">
          <Briefcase size={13} aria-hidden />
          <span>Import-Job gestartet:</span>
          <Link
            to={`/jobs?expand=${encodeURIComponent(ingestJobId)}`}
            className={styles.jobLinkBannerLink}
            onClick={() => setIngestJobId(null)}
          >
            {ingestJobId}
          </Link>
          <button
            type="button"
            className={styles.ingestJobBannerClose}
            onClick={() => setIngestJobId(null)}
            aria-label={t('wiki.close')}
          >
            ×
          </button>
        </div>
      )}

      {tab === 'pages' && (
        <div className={styles.body}>
          {/* Tree sidebar */}
          <aside className={styles.treeCol}>
            <div className={styles.treeToolbar}>
              <button
                type="button"
                className={`${styles.treeItem} ${showHome && !activePath && !autoIndex ? styles.treeItemActive : ''}`}
                style={{ paddingLeft: 10, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}
                onClick={goHome}
              >
                <Home size={12} />
                Startseite
              </button>
              <button
                type="button"
                className={styles.treeToolbarBtn}
                onClick={collapseAll}
                title="Alle einklappen"
                aria-label="Alle einklappen"
              >
                <ChevronsDownUp size={13} />
              </button>
              <button
                type="button"
                className={styles.treeToolbarBtn}
                onClick={expandAll}
                title="Alle ausklappen"
                aria-label="Alle ausklappen"
              >
                <ChevronsUpDown size={13} />
              </button>
            </div>

            {tree && (
              <>
                <TreeSection
                  sectionKey="main"
                  label={tree.main.label}
                  folders={tree.main.folders}
                  indexPath={tree.main.index_path ?? undefined}
                  expanded={expandedSections.has('main')}
                  expandedFolders={expandedFolders}
                  activePath={activePath}
                  onToggleSection={toggleSection}
                  onToggleFolder={toggleFolder}
                  onSelect={(p) => loadPage(p)}
                  onIngest={(files) => { void handleWikiIngest(files); }}
                />
                {tree.personal && (
                  <TreeSection
                    sectionKey="__personal__"
                    label={tree.personal.label}
                    folders={tree.personal.folders}
                    indexPath={tree.personal.index_path ?? undefined}
                    expanded={expandedSections.has('__personal__')}
                    expandedFolders={expandedFolders}
                    activePath={activePath}
                    department="__personal__"
                    onToggleSection={toggleSection}
                    onToggleFolder={toggleFolder}
                    onSelect={(p) => loadPage(p, '__personal__')}
                    onIngest={(files) => { void handleWikiIngest(files, '__personal__'); }}
                  />
                )}
                {Object.entries(tree.departments).map(([deptName, section]) => (
                  <TreeSection
                    key={deptName}
                    sectionKey={deptName}
                    label={section.label}
                    folders={section.folders}
                    indexPath={section.index_path ?? undefined}
                    expanded={expandedSections.has(deptName)}
                    expandedFolders={expandedFolders}
                    activePath={activePath}
                    department={deptName}
                    onToggleSection={toggleSection}
                    onToggleFolder={toggleFolder}
                    onSelect={(p) => loadPage(p, deptName)}
                    onIngest={(files) => { void handleWikiIngest(files, deptName); }}
                  />
                ))}
              </>
            )}
          </aside>

          {/* Content */}
          <div className={styles.contentCol}>
            {/* Breadcrumbs — visible once we leave the home screen */}
            {(activePath || autoIndex) && breadcrumbs.length > 1 && (
              <nav className={styles.breadcrumbs} aria-label="Breadcrumbs">
                {breadcrumbs.map((c, i) => {
                  const isLast = i === breadcrumbs.length - 1;
                  return (
                    <span key={i} className={styles.breadcrumbItem}>
                      {c.onClick && !isLast ? (
                        <button type="button" className={styles.breadcrumbBtn} onClick={c.onClick}>
                          {c.label}
                        </button>
                      ) : (
                        <span className={isLast ? styles.breadcrumbCurrent : undefined}>{c.label}</span>
                      )}
                      {!isLast && <ChevronRight size={12} className={styles.breadcrumbSep} />}
                    </span>
                  );
                })}
              </nav>
            )}

            {searching && (
              <div className={styles.loadingState}>
                <Loader2 size={16} className={styles.spin} />
                <span>Suche…</span>
              </div>
            )}

            {!searching && searchResults && (
              <div className={styles.searchResults}>
                {searchResults.length === 0 && (
                  <p style={{ color: 'var(--text-dim)', fontSize: 14 }}>Keine Treffer.</p>
                )}
                {searchResults.map((hit, i) => (
                  <button
                    key={i}
                    type="button"
                    className={styles.searchResultCard}
                    onClick={() => loadPage(hit.path, hit.department ?? undefined)}
                  >
                    <div className={styles.searchResultTitle}>{hit.title || hit.path}</div>
                    <div className={styles.searchResultMeta}>
                      <span className={styles.pageDeptBadge}>{hit.department_label}</span>
                      {hit.category && <span>{hit.category}</span>}
                    </div>
                    {hit.snippet && (
                      <div className={styles.searchResultSnippet}>{cleanSnippet(hit.snippet)}</div>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Home / start page */}
            {!searchResults && showHome && !page && !pageLoading && home && (
              <div className={styles.homeWrap}>
                <div>
                  <h1 className={styles.homeGreeting}>Wissensdatenbank</h1>
                  <p className={styles.homeSubtitle}>
                    {t('wiki.deptBoardIntro')}
                  </p>
                </div>

                <div className={styles.homeGrid}>
                  <button
                    type="button"
                    className={styles.homeCard}
                    onClick={() => openSection(null)}
                  >
                    <span className={styles.homeCardLabel}>{home.main.label}</span>
                    <span className={styles.homeCardCount}>
                      {home.main.page_count}
                      <span className={styles.homeCardUnit}> Seiten</span>
                    </span>
                  </button>

                  {home.personal && tree?.personal && (
                    <button
                      type="button"
                      className={styles.homeCard}
                      onClick={() => openSection('__personal__')}
                    >
                      <span className={styles.homeCardLabel}>{home.personal.label}</span>
                      <span className={styles.homeCardCount}>
                        {home.personal.page_count}
                        <span className={styles.homeCardUnit}> Seiten</span>
                      </span>
                    </button>
                  )}

                  {home.departments.map((d) => (
                    <button
                      key={d.name}
                      type="button"
                      className={styles.homeCard}
                      onClick={() => openSection(d.name)}
                    >
                      <span className={styles.homeCardLabel}>{d.label}</span>
                      <span className={styles.homeCardCount}>
                        {d.page_count}
                        <span className={styles.homeCardUnit}> Seiten</span>
                      </span>
                    </button>
                  ))}
                </div>

                {/* Recent pages */}
                {home.recent.length > 0 && (
                  <div>
                    <p className={styles.homeSectionTitle} style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Clock size={13} />
                      Zuletzt aktualisiert
                    </p>
                    <div className={styles.recentList}>
                      {home.recent.map((r, i) => (
                        <button
                          key={i}
                          type="button"
                          className={styles.recentRow}
                          onClick={() => loadPage(r.path, r.department ?? undefined)}
                        >
                          <span className={styles.recentIcon}>
                            <FileText size={13} />
                          </span>
                          <span className={styles.recentTitle}>{r.title}</span>
                          <span className={styles.recentDept}>{r.department_label}</span>
                          <span className={styles.recentDate}>{r.updated}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Auto-Index fallback: section without an index_path */}
            {!searchResults && autoIndex && !page && !pageLoading && (
              <AutoIndex
                section={autoIndex.section}
                dept={autoIndex.dept}
                onSelect={(p) => loadPage(p, autoIndex.dept)}
              />
            )}

            {/* Empty state */}
            {!searchResults && !showHome && !autoIndex && !pageLoading && !page && (
              <div className={styles.emptyState}>
                <BookOpen size={36} strokeWidth={1.2} />
                <p>{t('wiki.pickPage')}</p>
              </div>
            )}

            {pageLoading && (
              <div className={styles.loadingState}>
                <Loader2 size={16} className={styles.spin} />
                <span>{t('wiki.loadingPage')}</span>
              </div>
            )}

            {!searchResults && !pageLoading && page && (
              <>
                <div className={styles.pageHeader}>
                  <div className={styles.pageHeaderRow}>
                    <h1 className={styles.pageTitle}>{page.title || page.path}</h1>
                    <div className={styles.pageHeaderActions}>
                      <button
                        type="button"
                        className={styles.exportBtn}
                        onClick={handleExportPdf}
                        disabled={exportingPdf}
                        title={t('wiki.exportPdfBtn')}
                        aria-label={t('wiki.exportPdfBtn')}
                      >
                        {exportingPdf ? (
                          <Loader2 size={14} className={styles.spin} />
                        ) : (
                          <Download size={14} />
                        )}
                      </button>
                      {page.category !== 'meta' && (
                        <button
                          type="button"
                          className={styles.deleteBtn}
                          onClick={() => setShowDeleteConfirm(true)}
                          title={t('wiki.deleteTitleBtn')}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className={styles.pageMeta}>
                    {page.category && <span>{page.category}</span>}
                    {page.updated && <span>Aktualisiert: {page.updated}</span>}
                    {page.tags.map((t) => (
                      <span key={t} className={styles.pageTag}>{t}</span>
                    ))}
                  </div>
                  {page.job_id && (
                    <div className={styles.jobLinkBanner}>
                      <Briefcase size={14} aria-hidden />
                      <span>{t('wiki.deptJob')}</span>
                      <Link
                        to={`/jobs?expand=${encodeURIComponent(page.job_id)}`}
                        className={styles.jobLinkBannerLink}
                      >
                        {page.job_id}
                      </Link>
                      {page.job_role && (
                        <span className={styles.jobRoleBadge}>
                          {page.job_role === 'deliverable' ? 'Ergebnis' : 'Material'}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {showDeleteConfirm && (
                  <div className={styles.deleteConfirm}>
                    <p>
                      {t('wiki.deleteConfirm', { title: page.title || page.path })}
                      Alle Querverweise in anderen Seiten werden automatisch entfernt.
                    </p>
                    <div className={styles.deleteConfirmActions}>
                      <button
                        type="button"
                        className={styles.deleteConfirmCancel}
                        onClick={() => setShowDeleteConfirm(false)}
                        disabled={deleting}
                      >
                        {t('wiki.cancel')}
                      </button>
                      <button
                        type="button"
                        className={styles.deleteConfirmDelete}
                        onClick={handleDelete}
                        disabled={deleting}
                      >
                        {deleting ? (
                          <>
                            <Loader2 size={13} className={styles.spin} />
                            {t('wiki.deleting')}
                          </>
                        ) : (
                          <>
                            <Trash2 size={13} />
                            {t('wiki.delete')}
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )}

                <div className={styles.pageBody}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{page.content}</ReactMarkdown>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {tab === 'graph' && (
        <div className={styles.graphContainer} ref={graphContainerRef}>
          {graphLoading && (
            <div className={styles.loadingState}>
              <Loader2 size={20} className={styles.spin} />
              <span>{t('wiki.graphLoading')}</span>
            </div>
          )}
          {!graphLoading && graph && (
            <>
              <ForceGraph2D
                width={graphDimensions.width}
                height={graphDimensions.height}
                graphData={graphData}
                nodeLabel=""
                nodeRelSize={6}
                nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
                  const label = node.title || '';
                  const isDeliverable = node.job_role === 'deliverable';
                  const radius = isDeliverable ? 7 : 5;
                  const fontSize = Math.max(11 / globalScale, 1.5);
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
                  ctx.fillStyle = node.color || '#22c55e';
                  ctx.fill();
                  if (isDeliverable) {
                    ctx.strokeStyle = '#d4d4d6';
                    ctx.lineWidth = 1.5 / globalScale;
                    ctx.stroke();
                  }
                  if (showGraphLabels && globalScale > 0.7) {
                    ctx.font = `${isDeliverable ? 'bold ' : ''}${fontSize}px sans-serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'top';
                    ctx.fillStyle = isDeliverable ? '#d4d4d6' : '#a1a1aa';
                    ctx.fillText(label.slice(0, 30), node.x, node.y + radius + 2);
                  }
                }}
                linkColor={(link: any) => link.type === 'job' ? 'rgba(160,160,165,0.35)' : 'rgba(100,100,100,0.2)'}
                linkWidth={(link: any) => link.type === 'link' ? 1.5 : link.type === 'job' ? 1.2 : 0.5}
                linkLineDash={(link: any) => link.type === 'job' ? [4, 3] : []}
                onNodeHover={(node: any) => {
                  setHoveredNode(node ?? null);
                }}
                onNodeClick={(node: any) => {
                  if (!node) return;
                  const id = node.id as string;
                  const deptSep = id.indexOf('::');
                  if (deptSep > -1) {
                    loadPage(id.slice(deptSep + 2), id.slice(0, deptSep));
                  } else {
                    loadPage(id);
                  }
                  setTab('pages');
                }}
                onNodeDrag={() => setHoveredNode(null)}
                cooldownTicks={100}
                d3AlphaDecay={0.03}
                d3VelocityDecay={0.3}
                enableNodeDrag
                enableZoomInteraction
              />
              {hoveredNode && (
                <div className={styles.graphTooltip} style={{ left: 14, top: 14 }}>
                  <strong>{hoveredNode.title}</strong>
                  <br />
                  <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                    {hoveredNode.department_label}
                    {hoveredNode.category ? ` / ${hoveredNode.category}` : ''}
                  </span>
                  {hoveredNode.job_role && (
                    <>
                      <br />
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {hoveredNode.job_role === 'deliverable' ? 'Ergebnis' : 'Material'}
                      </span>
                    </>
                  )}
                </div>
              )}
              <div className={styles.graphLegend}>
                {deptLabels.map((d) => (
                  <span key={d.dept ?? '__main'}>
                    <span className={styles.legendDot} style={{ background: d.color }} />
                    {d.label}
                  </span>
                ))}
              </div>
              <button
                type="button"
                className={styles.graphLabelToggle}
                onClick={() => setShowGraphLabels((v) => !v)}
                title={showGraphLabels ? 'Labels ausblenden' : 'Labels einblenden'}
              >
                {showGraphLabels ? 'Labels aus' : 'Labels an'}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Tree section component ─────────────────────────────────────────────── */

interface TreeSectionProps {
  sectionKey: string;
  label: string;
  folders: Record<string, { path: string; title: string; category: string }[]>;
  indexPath?: string;
  expanded: boolean;
  expandedFolders: Set<string>;
  activePath: { path: string; dept?: string } | null;
  department?: string;
  onToggleSection: (key: string) => void;
  onToggleFolder: (key: string) => void;
  onSelect: (path: string) => void;
  onIngest?: (files: FileList) => void;
}

function TreeSection({
  sectionKey,
  label,
  folders,
  indexPath,
  expanded,
  expandedFolders,
  activePath,
  department,
  onToggleSection,
  onToggleFolder,
  onSelect,
  onIngest,
}: TreeSectionProps) {
  const ingestInputRef = useRef<HTMLInputElement>(null);

  const sortedFolders = useMemo(() => {
    const entries = Object.entries(folders);
    const root = entries.find(([k]) => k === '_root');
    const rest = entries.filter(([k]) => k !== '_root').sort(([a], [b]) => a.localeCompare(b));
    return root ? [root, ...rest] : rest;
  }, [folders]);

  const totalPages = useMemo(
    () => Object.values(folders).reduce((s, e) => s + e.length, 0),
    [folders],
  );

  return (
    <div className={styles.treeSection}>
      <div className={styles.treeSectionHeader} onClick={() => onToggleSection(sectionKey)}>
        <ChevronRight
          size={12}
          className={`${styles.treeSectionHeaderIcon} ${expanded ? styles.treeSectionHeaderIconOpen : ''}`}
        />
        <span className={styles.treeSectionLabel}>{label}</span>
        <span className={styles.treeSectionCount}>{totalPages}</span>
        {onIngest && (
          <>
            <button
              type="button"
              className={styles.ingestBtn}
              title="Dokumente hochladen (wiki-ingest)"
              aria-label="Dokumente hochladen"
              onClick={(e) => {
                e.stopPropagation();
                ingestInputRef.current?.click();
              }}
            >
              <Plus size={12} />
            </button>
            <input
              ref={ingestInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md,.csv,.html,.htm,.json,.yaml,.yml,.xml,.rst"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files?.length) onIngest(e.target.files);
                e.target.value = '';
              }}
            />
          </>
        )}
      </div>
      {expanded && indexPath && (() => {
        const isActive =
          activePath?.path === indexPath &&
          (activePath.dept ?? undefined) === department;
        return (
          <button
            key={`${sectionKey}::index`}
            type="button"
            className={`${styles.treeItem} ${isActive ? styles.treeItemActive : ''}`}
            style={{ paddingLeft: 24, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={() => onSelect(indexPath)}
            title={indexPath}
          >
            <BookOpen size={12} />
            Index
          </button>
        );
      })()}
      {expanded && sortedFolders.map(([folder, entries]) => {
        const folderKey = `${sectionKey}/${folder}`;
        const folderOpen = expandedFolders.has(folderKey);
        const isRoot = folder === '_root';
        const folderLabel = isRoot ? 'Allgemein' : folder;

        return (
          <div key={folderKey} className={styles.treeFolder}>
            <div className={styles.treeFolderHeader} onClick={() => onToggleFolder(folderKey)}>
              <ChevronRight
                size={10}
                className={`${styles.treeSectionHeaderIcon} ${folderOpen ? styles.treeSectionHeaderIconOpen : ''}`}
              />
              <FolderOpen size={12} />
              <span className={styles.treeFolderLabel}>{folderLabel}</span>
              <span className={styles.treeFolderCount}>{entries.length}</span>
            </div>
            {folderOpen && entries.map((e, idx) => {
              const isActive =
                activePath?.path === e.path &&
                (activePath.dept ?? undefined) === department;
              return (
                <button
                  key={`${folderKey}::${e.path}::${idx}`}
                  type="button"
                  className={`${styles.treeItem} ${isActive ? styles.treeItemActive : ''}`}
                  onClick={() => onSelect(e.path)}
                  title={e.path}
                >
                  {e.title}
                </button>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Auto-Index (fallback when a section has no index_path) ─────────────── */

interface AutoIndexProps {
  section: WikiTreeSection;
  dept?: string;
  onSelect: (path: string) => void;
}

function AutoIndex({ section, onSelect }: AutoIndexProps) {
  const { t } = useI18n();
  const sorted = useMemo(() => {
    const entries = Object.entries(section.folders);
    const root = entries.find(([k]) => k === '_root');
    const rest = entries.filter(([k]) => k !== '_root').sort(([a], [b]) => a.localeCompare(b));
    return root ? [root, ...rest] : rest;
  }, [section.folders]);

  const totalPages = sectionPageCount(section);

  return (
    <div className={styles.autoIndexWrap}>
      <div className={styles.autoIndexHeader}>
        <BookOpen size={20} />
        <h1 className={styles.autoIndexTitle}>{section.label}</h1>
        <span className={styles.autoIndexCount}>{t('wiki.pageCount', { n: totalPages })}</span>
      </div>
      <p className={styles.autoIndexHint}>
        {t('wiki.deptIndexMissing')}
      </p>

      {totalPages === 0 && (
        <p style={{ color: 'var(--text-dim)', fontSize: 14 }}>{t('wiki.noPagesYet')}</p>
      )}

      {sorted.map(([folder, entries]) => {
        if (entries.length === 0) return null;
        const label = folder === '_root' ? 'Allgemein' : folder;
        return (
          <section key={folder} className={styles.autoIndexSection}>
            <h2 className={styles.autoIndexSectionTitle}>
              <FolderOpen size={14} />
              {label}
              <span className={styles.autoIndexSectionCount}>{entries.length}</span>
            </h2>
            <div className={styles.autoIndexList}>
              {entries.map((e) => (
                <button
                  key={e.path}
                  type="button"
                  className={styles.autoIndexRow}
                  onClick={() => onSelect(e.path)}
                >
                  <FileText size={13} className={styles.autoIndexRowIcon} />
                  <span className={styles.autoIndexRowTitle}>{e.title}</span>
                  {e.category && <span className={styles.autoIndexRowCat}>{e.category}</span>}
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
