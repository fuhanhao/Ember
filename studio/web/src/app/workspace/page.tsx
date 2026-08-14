'use client';
import { useEffect, useState, useRef, useMemo } from 'react';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import Link from 'next/link';

// ============ TYPES ============
interface Article {
  id: string; title: string; url: string; source_id: string;
  category: string; tags: string[]; importance_score: number;
  content_signal?: number; published_at: string | null;
  content?: string; author?: string; feed_score?: number;
}

interface DigestGroup {
  category: string; label: string; icon: string;
  total: number; top_importance: number; preview: Article[];
}

interface CanvasCard {
  id: string;
  type: 'article' | 'mindmap' | 'kg' | 'blog' | 'podcast' | 'category';
  x: number;
  y: number;
  // article card
  article?: Article;
  // category card
  categoryLabel?: string;
  categoryIcon?: string;
  articles?: Article[];
  // generated card
  label?: string;
  data?: any;
  content?: string;
  loading?: boolean;
  sourceCardId?: string;
}

interface Workspace {
  id: string;
  name: string;
  cards: CanvasCard[];
  camera: { x: number; y: number; z: number };
}

// ============ MAIN PAGE ============
export default function WorkspacePage() {
  const { user, loading, logout } = useAuth();

  // Source panel
  const [articles, setArticles] = useState<Article[]>([]);
  const [category, setCategory] = useState('');
  const [activeCategories, setActiveCategories] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [sidebarTab, setSidebarTab] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [floatMenuOpen, setFloatMenuOpen] = useState(false);
  const [logoMenuOpen, setLogoMenuOpen] = useState(false);
  const [priorityFilter, setPriorityFilter] = useState(0);
  const [fetching, setFetching] = useState(false);
  const [digestGroups, setDigestGroups] = useState<DigestGroup[]>([]);
  const [bookmarks, setBookmarks] = useState<Article[]>([]);
  const [notebooks, setNotebooks] = useState<{ id: string; title: string; description?: string | null }[]>([]);

  // Workspaces — persisted to localStorage
  const defaultWs: Workspace[] = [{ id: 'ws-1', name: '工作区 1', cards: [], camera: { x: 0, y: 0, z: 1 } }];
  const [workspaces, setWorkspaces] = useState<Workspace[]>(defaultWs);
  const [activeWsId, setActiveWsId] = useState('ws-1');
  const [wsLoaded, setWsLoaded] = useState(false);

  // Load from localStorage after mount (avoids hydration mismatch)
  useEffect(() => {
    try {
      const saved = localStorage.getItem('ember_workspaces');
      if (saved) setWorkspaces(JSON.parse(saved));
      const activeId = localStorage.getItem('ember_active_ws');
      if (activeId) setActiveWsId(activeId);
    } catch {}
    setWsLoaded(true);
  }, []);

  // Save to localStorage on change
  useEffect(() => {
    if (!wsLoaded) return;
    try {
      localStorage.setItem('ember_workspaces', JSON.stringify(workspaces));
      localStorage.setItem('ember_active_ws', activeWsId);
    } catch {}
  }, [workspaces, activeWsId, wsLoaded]);
  const activeWs = workspaces.find(w => w.id === activeWsId)!;

  // Derived from active workspace
  const cards = activeWs.cards;
  const setCards = (updater: CanvasCard[] | ((prev: CanvasCard[]) => CanvasCard[])) => {
    setWorkspaces(prev => prev.map(w => w.id === activeWsId
      ? { ...w, cards: typeof updater === 'function' ? updater(w.cards) : updater }
      : w
    ));
  };

  // Canvas
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draggingOver, setDraggingOver] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [dragState, setDragState] = useState<{ cardId: string; startX: number; startY: number; cx: number; cy: number } | null>(null);
  const [expandedCardId, setExpandedCardId] = useState<string | null>(null);
  const [detailArticle, setDetailArticle] = useState<Article | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatModel, setChatModel] = useState<'flash' | 'balanced' | 'think'>('balanced');
  const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'ai'; text: string }[]>([]);
  const [chatStreaming, setChatStreaming] = useState(false);
  const [chatPanelOpen, setChatPanelOpen] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const chatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [marquee, setMarquee] = useState<{ startX: number; startY: number; curX: number; curY: number } | null>(null);

  // Auto scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);
  const [editingWsId, setEditingWsId] = useState<string | null>(null);
  const [wsDragId, setWsDragId] = useState<string | null>(null);
  const [wsDragOverId, setWsDragOverId] = useState<string | null>(null);
  const [expandedWsIds, setExpandedWsIds] = useState<Set<string>>(new Set());
  const toggleWsExpand = (id: string) => setExpandedWsIds(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
  const [expandedCardIds, setExpandedCardIds] = useState<Set<string>>(new Set());
  const toggleCardExpand = (id: string) => setExpandedCardIds(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  // Camera synced with active workspace
  const camera = activeWs.camera;
  const setCamera = (updater: { x: number; y: number; z: number } | ((prev: { x: number; y: number; z: number }) => { x: number; y: number; z: number })) => {
    setWorkspaces(prev => prev.map(w => w.id === activeWsId
      ? { ...w, camera: typeof updater === 'function' ? updater(w.camera) : updater }
      : w
    ));
  };
  const [panDrag, setPanDrag] = useState<{ startX: number; startY: number; camX: number; camY: number } | null>(null);

  // Sidebar split
  const [splitY, setSplitY] = useState(250);
  const [splitDrag, setSplitDrag] = useState<{ startY: number; startSplit: number } | null>(null);
  useEffect(() => {
    if (!splitDrag) return;
    const onMove = (e: MouseEvent) => {
      const newY = splitDrag.startSplit + e.clientY - splitDrag.startY;
      setSplitY(Math.max(100, Math.min(newY, window.innerHeight - 200)));
    };
    const onUp = () => setSplitDrag(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [splitDrag]);

  // === SINGLE unified handler for ALL zoom/pan ===
  // Blocks browser zoom everywhere. Applies canvas zoom only when over canvas.
  // Safari pinch-to-zoom uses gesture events (not wheel), so handle them here.
  const gestureCb = useRef<{ start: (e: any) => void; change: (e: any) => void }>({
    start: () => {}, change: () => {},
  });
  const lastGestureScale = useRef(1);
  gestureCb.current.start = (e: any) => {
    e.preventDefault();
    lastGestureScale.current = e.scale;
  };
  gestureCb.current.change = (e: any) => {
    e.preventDefault();
    const overCanvas = canvasRef.current?.contains(e.target as Node);
    if (!overCanvas) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const delta = e.scale / lastGestureScale.current;
    lastGestureScale.current = e.scale;
    setCamera(c => {
      const nz = Math.min(Math.max(c.z * delta, 0.2), 3);
      const s = nz / c.z;
      return { x: mx - s * (mx - c.x), y: my - s * (my - c.y), z: nz };
    });
  };
  useEffect(() => {
    const onStart = (e: any) => gestureCb.current.start(e);
    const onChange = (e: any) => gestureCb.current.change(e);
    const prevent = (e: Event) => e.preventDefault();
    document.addEventListener('gesturestart', onStart, { passive: false });
    document.addEventListener('gesturechange', onChange, { passive: false });
    document.addEventListener('gestureend', prevent, { passive: false });
    return () => {
      document.removeEventListener('gesturestart', onStart);
      document.removeEventListener('gesturechange', onChange);
      document.removeEventListener('gestureend', prevent);
    };
  }, []);

  // ============ DATA LOADING ============
  useEffect(() => { loadDigest(); }, []);
  useEffect(() => { if (category) loadFeed(); }, [category]);
  useEffect(() => {
    api.getBookmarks({ limit: '100' }).then((d: any) => setBookmarks(d.items || [])).catch(() => {});
    api.getNotebooks().then((d: any) => setNotebooks(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  const todayParams = () => {
    const today = new Date().toISOString().slice(0, 10);
    return { since: today + 'T00:00:00', until: today + 'T23:59:59' };
  };

  const loadDigest = async () => {
    try {
      const data = await api.getDigest(todayParams());
      setDigestGroups(data.groups || []);
      if (data.groups?.length > 0 && !category) setCategory(data.groups[0].category);
    } catch {}
  };

  const loadFeed = async () => {
    setFetching(true);
    try {
      const tp = todayParams();
      const cats = activeCategories.length > 0 ? activeCategories : (category ? [category] : []);
      let allItems: Article[] = [];
      if (cats.length > 0) {
        const results = await Promise.all(cats.map(c => api.getFeed({ limit: '50', category: c, ...tp }).catch(() => ({ items: [] }))));
        allItems = results.flatMap((r: any) => r.items || []);
        allItems.sort((a, b) => (b.importance_score || 0) - (a.importance_score || 0));
      } else {
        const data = await api.getFeed({ limit: '100', ...tp });
        allItems = data.items || [];
      }
      setArticles(allItems);
    } catch {}
    setFetching(false);
  };

  const doSearch = async () => {
    if (!searchQuery.trim()) { loadFeed(); return; }
    setFetching(true);
    try {
      const data = await api.search({ q: searchQuery, limit: '100' });
      setArticles(data.items || []);
    } catch {}
    setFetching(false);
  };

  const wsCounter = useRef(workspaces.length);
  const newWorkspace = () => {
    wsCounter.current += 1;
    const id = `ws-${Date.now()}`;
    const ws: Workspace = { id, name: `工作区 ${wsCounter.current}`, cards: [], camera: { x: 0, y: 0, z: 1 } };
    setWorkspaces(prev => [...prev, ws]);
    setActiveWsId(id);
    setSelectedIds(new Set());
    setActiveId(null);
  };

  const switchWorkspace = (id: string) => {
    setActiveWsId(id);
    setSelectedIds(new Set());
    setActiveId(null);
  };

  const renameWorkspace = (id: string, name: string) => {
    setWorkspaces(prev => prev.map(w => w.id === id ? { ...w, name } : w));
  };

  const deleteWorkspace = (id: string) => {
    if (workspaces.length <= 1) return;
    setWorkspaces(prev => prev.filter(w => w.id !== id));
    if (activeWsId === id) setActiveWsId(workspaces.find(w => w.id !== id)!.id);
  };

  // ============ DRAG FROM SOURCE ============
  const onDragStart = (e: React.DragEvent, article: Article) => {
    e.dataTransfer.setData('application/json', JSON.stringify(article));
    e.dataTransfer.effectAllowed = 'copy';
  };
  const onCanvasDragOver = (e: React.DragEvent) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; setDraggingOver(true); };
  const onCanvasDragLeave = () => setDraggingOver(false);
  const onCanvasDrop = async (e: React.DragEvent) => {
    e.preventDefault(); setDraggingOver(false);
    const rect = canvasRef.current?.getBoundingClientRect();
    const dropX = (e.clientX - (rect?.left || 0) - camera.x) / camera.z;
    const dropY = (e.clientY - (rect?.top || 0) - camera.y) / camera.z;

    // Category drop
    const catData = e.dataTransfer.getData('application/ember-category');
    if (catData) {
      try {
        const { category: cat, label, icon } = JSON.parse(catData);
        if (cards.some(c => c.id === `cat-${cat}`)) return;
        // Fetch articles for this category (today only)
        const data = await api.getFeed({ limit: '100', category: cat, ...todayParams() });
        const items: Article[] = data.items || [];
        setCards(prev => [...prev, {
          id: `cat-${cat}`, type: 'category',
          categoryLabel: label, categoryIcon: icon, articles: items,
          x: dropX - 200, y: dropY - 20,
        }]);
      } catch {}
      return;
    }

    // Article drop
    try {
      const article: Article = JSON.parse(e.dataTransfer.getData('application/json'));
      if (cards.some(c => c.id === article.id)) return;
      let full = article;
      try { full = await api.getArticle(article.id); } catch {}
      setCards(prev => [
        // Remove article from any category card that contains it
        ...prev.map(c => c.type === 'category' && c.articles
          ? { ...c, articles: c.articles.filter(a => a.id !== full.id) }
          : c
        ),
        { id: full.id, type: 'article', article: full, x: dropX - 120, y: dropY - 40 },
      ]);
      api.recordAction(article.id, 'view').catch(() => {});
    } catch {}
  };

  // ============ CARD DRAG WITHIN CANVAS ============
  const wasDragged = useRef(false);
  const onCardMouseDown = (e: React.MouseEvent, card: CanvasCard) => {
    const el = e.target as HTMLElement;
    if (el.closest('button') || el.closest('[data-draggable-article]')) return;
    wasDragged.current = false;
    setDragState({ cardId: card.id, startX: e.clientX, startY: e.clientY, cx: card.x, cy: card.y });
  };
  useEffect(() => {
    if (!dragState) return;
    const onMove = (e: MouseEvent) => {
      const dx = e.clientX - dragState.startX;
      const dy = e.clientY - dragState.startY;
      if (!wasDragged.current && Math.abs(dx) < 5 && Math.abs(dy) < 5) return;
      wasDragged.current = true;
      setCards(prev => prev.map(c => c.id === dragState.cardId
        ? { ...c, x: dragState.cx + dx, y: dragState.cy + dy } : c));
    };
    const onUp = () => setDragState(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [dragState]);

  // ============ SELECTION ============
  const selectCard = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedIds(new Set([id]));
    setActiveId(id);
  };
  const removeCard = (id: string) => {
    setCards(prev => prev.filter(c => c.id !== id));
    setSelectedIds(prev => { const n = new Set(prev); n.delete(id); return n; });
    if (activeId === id) setActiveId(null);
  };
  const marqueeUsed = useRef(false);
  const onCanvasClick = () => {
    if (marqueeUsed.current) { marqueeUsed.current = false; return; }
    setSelectedIds(new Set()); setActiveId(null); setDetailArticle(null);
  };

  // Pan: mousedown on empty canvas area (not on a card)
  const cameraRef = useRef(camera);
  cameraRef.current = camera;

  const onCanvasMouseDown = (e: React.MouseEvent) => {
    const el = e.target as HTMLElement;
    if (el.closest('[data-card]') || el.closest('button') || el.closest('input') || el.closest('textarea')) return;
    e.preventDefault();
    // Middle mouse button or space held: pan canvas
    if (e.button === 1) {
      const cam = cameraRef.current;
      setPanDrag({ startX: e.clientX, startY: e.clientY, camX: cam.x, camY: cam.y });
    } else {
      // Left click: start marquee selection
      setMarquee({ startX: e.clientX, startY: e.clientY, curX: e.clientX, curY: e.clientY });
    }
  };
  const canvasInnerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!panDrag) return;
    const onMove = (e: MouseEvent) => {
      setCamera(c => ({ ...c, x: panDrag.camX + e.clientX - panDrag.startX, y: panDrag.camY + e.clientY - panDrag.startY }));
    };
    const onUp = () => setPanDrag(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [panDrag]);

  // Marquee box-select
  const cardsRef = useRef(cards);
  cardsRef.current = cards;
  useEffect(() => {
    if (!marquee) return;
    const onMove = (e: MouseEvent) => {
      setMarquee(m => m ? { ...m, curX: e.clientX, curY: e.clientY } : null);
    };
    const onUp = (e: MouseEvent) => {
      // Calculate selection rect in canvas coordinates
      const rect = canvasRef.current?.getBoundingClientRect();
      if (rect && marquee) {
        const cam = cameraRef.current;
        const toCanvas = (sx: number, sy: number) => ({
          x: (sx - rect.left - cam.x) / cam.z,
          y: (sy - rect.top - cam.y) / cam.z,
        });
        const p1 = toCanvas(marquee.startX, marquee.startY);
        const p2 = toCanvas(e.clientX, e.clientY);
        const selRect = {
          left: Math.min(p1.x, p2.x), top: Math.min(p1.y, p2.y),
          right: Math.max(p1.x, p2.x), bottom: Math.max(p1.y, p2.y),
        };
        // Only select if dragged a meaningful distance (> 5px)
        if (Math.abs(e.clientX - marquee.startX) > 5 || Math.abs(e.clientY - marquee.startY) > 5) {
          const hit = new Set<string>();
          for (const card of cardsRef.current) {
            const cw = card.type === 'category' ? 420 : card.type === 'article' ? 260 : 320;
            const ch = 200; // approximate card height
            const cardRight = card.x + cw;
            const cardBottom = card.y + ch;
            if (card.x < selRect.right && cardRight > selRect.left && card.y < selRect.bottom && cardBottom > selRect.top) {
              hit.add(card.id);
            }
          }
          setSelectedIds(hit);
          setActiveId(null);
          marqueeUsed.current = true;
        }
      }
      setMarquee(null);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [marquee]);

  // Delete selected cards with Delete/Backspace key
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (expandedCardId) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedIds.size > 0) {
        e.preventDefault();
        setCards(prev => prev.filter(c => !selectedIds.has(c.id)));
        setSelectedIds(new Set());
        setActiveId(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedIds]);

  // Single document-level wheel handler: blocks browser zoom + handles canvas pan/zoom
  const wheelCb = useRef<(e: WheelEvent) => void>(() => {});
  wheelCb.current = (e: WheelEvent) => {
    const isZoom = e.ctrlKey || e.metaKey;
    const overCanvas = canvasRef.current?.contains(e.target as Node);

    // Always block browser zoom
    if (isZoom) e.preventDefault();

    // Only apply canvas transform when over canvas
    if (!overCanvas) return;

    // If over a selected card, manually scroll the card's scrollable area instead of panning
    if (!isZoom) {
      const el = e.target as HTMLElement;
      const card = el.closest('[data-card]') as HTMLElement | null;
      if (card && card.dataset.card === activeId) {
        // Find scrollable child inside card
        const scrollable = card.querySelector('.overflow-y-auto') as HTMLElement | null;
        if (scrollable && scrollable.scrollHeight > scrollable.clientHeight + 1) {
          scrollable.scrollTop += e.deltaY;
        }
        e.preventDefault();
        return;
      }
    }

    e.preventDefault();

    if (isZoom) {
      const rect = canvasRef.current!.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const factor = 1 - e.deltaY * 0.005;
      setCamera(c => {
        const nz = Math.min(Math.max(c.z * factor, 0.2), 3);
        const s = nz / c.z;
        return { x: mx - s * (mx - c.x), y: my - s * (my - c.y), z: nz };
      });
    } else {
      setCamera(c => ({ ...c, x: c.x - e.deltaX, y: c.y - e.deltaY }));
    }
  };
  useEffect(() => {
    const handler = (e: WheelEvent) => wheelCb.current(e);
    document.addEventListener('wheel', handler, { passive: false });
    return () => document.removeEventListener('wheel', handler);
  }, []);

  // ============ GENERATE → NEW CARD ============
  const getActiveArticleCard = () => {
    if (!activeId) return null;
    const c = cards.find(c => c.id === activeId);
    return c?.type === 'article' ? c : null;
  };

  const addGenCard = (sourceCard: CanvasCard, type: CanvasCard['type'], label: string): string => {
    const id = `${type}-${sourceCard.id}-${Date.now()}`;
    // Place to the right of source card, accounting for its width
    const sourceW = sourceCard.type === 'mindmap' ? 560 : sourceCard.type === 'category' ? 420 : sourceCard.type === 'article' ? 260 : 320;
    const newCard: CanvasCard = {
      id, type, label,
      x: sourceCard.x + sourceW + 30, y: sourceCard.y,
      loading: true, sourceCardId: sourceCard.id,
    };
    setCards(prev => [...prev, newCard]);
    return id;
  };

  const updateGenCard = (id: string, updates: Partial<CanvasCard>) => {
    setCards(prev => prev.map(c => c.id === id ? { ...c, ...updates } : c));
  };

  const generateMindmap = async () => {
    const src = getActiveArticleCard(); if (!src) return;
    const cid = addGenCard(src, 'mindmap', '🧠 思维导图');
    try {
      const res = await api.generateMindmap({ source_type: 'article', source_id: src.article!.id });
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          for (const line of decoder.decode(value).split('\n')) {
            if (!line.startsWith('data: ')) continue;
            try {
              const d = JSON.parse(line.slice(6));
              if (d.partial) updateGenCard(cid, { data: d.partial });
              if (d.done && d.mindmap) updateGenCard(cid, { data: d.mindmap, loading: false });
            } catch {}
          }
        }
      }
      // Ensure loading is off
      updateGenCard(cid, { loading: false });
    } catch (e: any) { updateGenCard(cid, { content: '生成失败: ' + e.message, loading: false }); }
  };

  const generateKG = async () => {
    const src = getActiveArticleCard(); if (!src) return;
    const cid = addGenCard(src, 'kg', '🔗 知识图谱');
    try {
      const res = await api.generateKG({ source_type: 'article', source_id: src.article!.id });
      updateGenCard(cid, { data: res.graph, loading: false });
    } catch (e: any) { updateGenCard(cid, { content: '生成失败: ' + e.message, loading: false }); }
  };

  const generateBlog = async () => {
    const src = getActiveArticleCard(); if (!src) return;
    const cid = addGenCard(src, 'blog', '📝 公众号文章');
    try {
      const res = await api.generateBlog({
        source_type: 'article', source_id: src.article!.id,
        style: '技术深度', tone: '专业严谨', length: '中篇2000字',
        target_platform: '微信公众号', language: 'zh',
      });
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let text = '';
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          for (const line of decoder.decode(value).split('\n')) {
            if (line.startsWith('data: ')) {
              try { const d = JSON.parse(line.slice(6)); if (d.text) { text += d.text; updateGenCard(cid, { content: text }); } } catch {}
            }
          }
        }
      }
      updateGenCard(cid, { content: text, loading: false });
    } catch (e: any) { updateGenCard(cid, { content: '生成失败: ' + e.message, loading: false }); }
  };

  const generatePodcast = async () => {
    const src = getActiveArticleCard(); if (!src) return;
    const cid = addGenCard(src, 'podcast', '🎙️ 播客脚本');
    updateGenCard(cid, { content: '播客脚本生成功能开发中...', loading: false });
  };

  if (loading) return null;

  const summarizeCategory = async (cardId: string) => {
    const card = cards.find(c => c.id === cardId);
    if (!card || card.type !== 'category' || !card.articles) return;
    const cid = addGenCard(card, 'blog', `📊 ${card.categoryLabel} 总结`);
    try {
      const res = await api.generateCategorySummary({
        category: card.categoryLabel || '',
        article_titles: card.articles.map(a => a.title),
        article_snippets: card.articles.slice(0, 10).map(a => a.content || a.title),
      });
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let text = '';
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          for (const line of decoder.decode(value).split('\n')) {
            if (!line.startsWith('data: ')) continue;
            try { const d = JSON.parse(line.slice(6)); if (d.text) { text += d.text; updateGenCard(cid, { content: text }); } } catch {}
          }
        }
      }
      updateGenCard(cid, { content: text, loading: false });
    } catch (e: any) { updateGenCard(cid, { content: '生成失败: ' + e.message, loading: false }); }
  };

  const explodeCategory = async (cardId: string) => {
    const card = cards.find(c => c.id === cardId);
    if (!card || card.type !== 'category' || !card.articles) return;
    const cols = 3;
    const newCards: CanvasCard[] = [];
    for (let i = 0; i < card.articles.length; i++) {
      const a = card.articles[i];
      if (cards.some(c => c.id === a.id)) continue;
      let full = a;
      try { full = await api.getArticle(a.id); } catch {}
      const col = i % cols;
      const row = Math.floor(i / cols);
      newCards.push({
        id: full.id, type: 'article', article: full,
        x: card.x + col * 280, y: card.y + row * 160,
      });
    }
    setCards(prev => [...prev.filter(c => c.id !== cardId), ...newCards]);
  };

  const activeArticleCard = getActiveArticleCard();
  const getActiveCategoryCard = () => {
    if (!activeId) return null;
    const c = cards.find(c => c.id === activeId);
    return c?.type === 'category' ? c : null;
  };
  const activeCategoryCard = getActiveCategoryCard();
  const hasCanvas = cards.length > 0;

  const MODEL_MAP: Record<string, string> = {
    flash: 'gemini-3.1-flash-lite-preview',
    balanced: 'gemini-3-flash-preview',
    think: 'gemini-3.1-pro-preview-search',
  };

  const handleChatSubmit = async () => {
    const rawInput = chatInput.trim();
    const input = rawInput.toLowerCase();
    if (!input) return;
    setChatInput('');

    const model = MODEL_MAP[chatModel] || MODEL_MAP.balanced;

    // Get selected card context
    const articleCard = getActiveArticleCard();
    const categoryCard = getActiveCategoryCard();

    if (!articleCard && !categoryCard) {
      // Free chat — show in right panel
      setChatPanelOpen(true);
      setChatCollapsed(false);
      setChatMessages(prev => [...prev, { role: 'user', text: rawInput }]);
      setChatStreaming(true);
      let aiText = '';
      setChatMessages(prev => [...prev, { role: 'ai', text: '' }]);

      try {
        const resp = await api.generateArticle({ prompt: rawInput, context: '', model });
        const reader = resp.body?.getReader();
        if (!reader) return;
        const decoder = new TextDecoder();
        let rafPending = false;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split('\n')) {
            if (line.startsWith('data: ')) {
              try {
                const d = JSON.parse(line.slice(6));
                if (d.text) aiText += d.text;
              } catch {}
            }
          }
          if (!rafPending) {
            rafPending = true;
            requestAnimationFrame(() => {
              setChatMessages(prev => {
                const msgs = [...prev];
                msgs[msgs.length - 1] = { role: 'ai', text: aiText };
                return msgs;
              });
              rafPending = false;
            });
          }
        }
        // Final update
        setChatMessages(prev => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = { role: 'ai', text: aiText };
          return msgs;
        });
        if (!aiText) {
          setChatMessages(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = { role: 'ai', text: '暂无回复' };
            return msgs;
          });
        }
      } catch {
        setChatMessages(prev => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = { role: 'ai', text: '抱歉，AI 暂时无法回答，请稍后再试。' };
          return msgs;
        });
      } finally {
        setChatStreaming(false);
      }
      return;
    }

    // Fire-and-forget: card generation runs in background, chat stays available
    if (articleCard) {
      if (input.includes('思维导图') || input.includes('mindmap') || input.includes('脑图')) {
        generateMindmap();
      } else if (input.includes('知识图谱') || input.includes('图谱') || input.includes('实体')) {
        generateKG();
      } else if (input.includes('公众号') || input.includes('微信') || input.includes('文章')) {
        generateBlog();
      } else if (input.includes('播客') || input.includes('podcast') || input.includes('脚本')) {
        generatePodcast();
      } else {
        // Free-form: send as custom blog with user instruction
        const src = articleCard;
        const cid = addGenCard(src, 'blog', '💬 ' + input.slice(0, 15));
        const customInstructions = chatInput.trim();
        api.generateBlog({
          source_type: 'article', source_id: src.article!.id,
          style: '技术深度', tone: '专业严谨', length: '中篇2000字',
          target_platform: '通用Markdown', language: 'zh',
          custom_instructions: customInstructions,
        }).then(async (res) => {
          const reader = res.body?.getReader();
          const decoder = new TextDecoder();
          let text = '';
          if (reader) {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              for (const line of decoder.decode(value).split('\n')) {
                if (!line.startsWith('data: ')) continue;
                try { const d = JSON.parse(line.slice(6)); if (d.text) { text += d.text; updateGenCard(cid, { content: text }); } } catch {}
              }
            }
          }
          updateGenCard(cid, { content: text, loading: false });
        }).catch((e: any) => { updateGenCard(cid, { content: '生成失败: ' + e.message, loading: false }); });
      }
    } else if (categoryCard) {
      if (input.includes('总结') || input.includes('summary') || input.includes('分析') || input.includes('概览')) {
        summarizeCategory(categoryCard.id);
      } else if (input.includes('解体') || input.includes('展开') || input.includes('拆开') || input.includes('散开')) {
        explodeCategory(categoryCard.id);
      } else {
        summarizeCategory(categoryCard.id);
      }
    }
  };

  const navTabs = [
    { href: '/', label: '全球AI动态' },
    { href: '/workspace', label: '工作区' },
    { href: '/knowledge', label: '知识库' },
  ];

  return (
    <div className="h-screen flex flex-col bg-[#faf6f0] dark:bg-[#17120e]">
      {/* Top Nav Bar */}
      <header className="shrink-0 h-[52px] hidden bg-white dark:bg-[#211a13] border-b border-[#e7dcc9] dark:border-[#3a2e1f] flex items-center px-5 gap-5 z-30">
        {false && (
          <button onClick={() => setSidebarOpen(true)} className="w-7 h-7 rounded-lg flex items-center justify-center text-[#84735f] dark:text-[#a08d74] hover:bg-[#f3ece1] dark:hover:bg-[#2b2218] hover:text-[#e0703a] transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12h18M3 6h18M3 18h18"/></svg>
          </button>
        )}
        <a href="/" className="flex items-center gap-2">
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="url(#fg)"/>
            <path d="M16 4c2 5 7 8.4 7 13.8a7 7 0 1 1-14 0c0-2.5 1.2-4.7 2.8-6.6.3 1.6 1 3 2.2 4-.3-4 1-8.8 2-11.2z" fill="#fff" fillOpacity="0.95"/>
            <circle cx="23.5" cy="9.5" r="1.5" fill="#f0b34a"/>
            <defs><linearGradient id="fg" x1="0" y1="0" x2="32" y2="32"><stop stopColor="#e0703a"/><stop offset="1" stopColor="#f0b34a"/></linearGradient></defs>
          </svg>
          <span className="text-[17px] font-bold tracking-tight" style={{ background: 'var(--gradient)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>Ember</span>
        </a>
        <nav className="flex items-center gap-1">
          {navTabs.map(t => (
            <a key={t.href} href={t.href}
              className={`px-3 py-1.5 rounded-md text-[13px] transition-colors ${
                t.href === '/workspace' ? 'bg-[#f3ece1] dark:bg-[#2b2218] text-[#33291f] dark:text-white font-medium' : 'text-[#84735f] dark:text-[#a08d74] hover:text-[#e0703a]'
              }`}>{t.label}</a>
          ))}
        </nav>
      </header>

      <div className="flex-1 flex overflow-hidden">
      {/* ============ LEFT PANEL ============ */}
      {/* Floating toolbar when sidebar collapsed */}
      {false && (
        <div className="absolute left-4 top-[60px] z-20">
          <div className="flex items-center gap-1 bg-white dark:bg-[#211a13] rounded-xl shadow-lg border border-[#e7dcc9] dark:border-[#3a2e1f] px-2 py-1.5 relative">
            {/* Logo menu button - hidden, using nav bar instead */}
            <button onClick={() => setFloatMenuOpen(p => !p)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[#e0703a] hover:bg-[#f3ece1] dark:hover:bg-[#33261a] transition-colors">
              <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
                <path d="M16 4c2 5 7 8.4 7 13.8a7 7 0 1 1-14 0c0-2.5 1.2-4.7 2.8-6.6.3 1.6 1 3 2.2 4-.3-4 1-8.8 2-11.2z" fill="#e0703a"/><circle cx="23.5" cy="9.5" r="1.5" fill="#f0b34a"/>
              </svg>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M6 9l6 6 6-6"/></svg>
            </button>
            <div className="w-px h-5 bg-[#e7dcc9] dark:bg-[#3a2e1f]" />
            <button onClick={() => setSidebarOpen(true)} className="px-2 py-1 rounded-lg text-[13px] font-medium text-[#33291f] dark:text-white hover:bg-[#f3ece1] dark:hover:bg-[#33261a] hover:text-[#e0703a] transition-colors">
              工作台
            </button>
            <div className="w-px h-5 bg-[#e7dcc9] dark:bg-[#3a2e1f]" />
            <button onClick={() => setSidebarOpen(true)} className="px-2 py-1 rounded-lg text-[#84735f] dark:text-[#a08d74] hover:bg-[#f3ece1] dark:hover:bg-[#33261a] hover:text-[#e0703a] transition-colors">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/></svg>
            </button>
          </div>
          {/* Dropdown menu */}
          {floatMenuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setFloatMenuOpen(false)} />
              <div className="absolute left-0 top-full mt-2 w-[200px] bg-white dark:bg-[#211a13] rounded-xl shadow-xl border border-[#e7dcc9] dark:border-[#3a2e1f] py-1.5 z-20">
                <a href="/" onClick={() => { localStorage.setItem('ember_tab', 'workspace'); }}
                  className="flex items-center gap-2.5 px-4 py-2.5 text-[13px] text-[#33291f] dark:text-white hover:bg-[#f3ece1] dark:hover:bg-[#2b2218] transition-colors">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#84735f" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>
                  返回工作区
                </a>
                <a href="/"
                  className="flex items-center gap-2.5 px-4 py-2.5 text-[13px] text-[#33291f] dark:text-white hover:bg-[#f3ece1] dark:hover:bg-[#2b2218] transition-colors">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#84735f" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
                  返回主页
                </a>
                <div className="h-px bg-[#e7dcc9] dark:bg-[#3a2e1f] my-1.5" />
                <div className="px-4 py-1.5 text-[10px] text-[#b7a68e] dark:text-[#6e5f4b] uppercase tracking-wider">信息优先级</div>
                {['全部信息', '高优先级', '仅重要'].map((label, i) => (
<button key={label} onClick={() => setPriorityFilter(i)}
className="w-full flex items-center gap-2.5 px-4 py-2 text-[13px] text-[#33291f] dark:text-white hover:bg-[#f3ece1] dark:hover:bg-[#2b2218] transition-colors text-left">
<span className={`w-2 h-2 rounded-full ${priorityFilter === i ? 'bg-[#e0703a]' : 'bg-transparent border border-[#d4c4a8] dark:border-[#3a2e1f]'}`} />
{label}
</button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
      <aside className={`bg-white/80 backdrop-blur-xl border-r border-[#e7dcc9] dark:border-[#3a2e1f] flex flex-col shrink-0 transition-all duration-300 ${sidebarOpen ? 'w-[280px]' : 'w-0 overflow-hidden border-none'}`}>
        <div className="px-4 pt-4 pb-2 flex items-center justify-between relative z-50">
          <button onClick={() => setLogoMenuOpen(p => !p)} className="flex items-center gap-0.5">
            <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
              <path d="M8 25V7h11v4H12.5v4.5h5.5v4h-5.5v5.5H8z" stroke="#33291f" strokeWidth="1.2"/>
              <path d="M21 14l3-1.5v10L21 24V14z" stroke="#33291f" strokeWidth="1.2" opacity="0.4"/>
            </svg>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#84735f" strokeWidth="2"><path d="M6 9l6 6 6-6"/></svg>
          </button>
          {logoMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setLogoMenuOpen(false)} />
              <div className="fixed left-4 top-12 w-[220px] bg-white dark:bg-[#211a13] rounded-xl shadow-xl border border-[#e7dcc9] dark:border-[#3a2e1f] py-1.5 z-50">
                <a href="/"
                  className="flex items-center gap-2.5 px-4 py-2.5 text-[13px] text-[#33291f] dark:text-white hover:bg-[#f3ece1] dark:hover:bg-[#2b2218] transition-colors">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#84735f" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
                  回到主页
                </a>
              </div>
            </>
          )}
          <button onClick={() => setSidebarOpen(false)}
            className="w-6 h-6 rounded-md flex items-center justify-center text-[#b7a68e] dark:text-[#6e5f4b] hover:text-[#e0703a] hover:bg-[#f3ece1] dark:hover:bg-[#33261a] transition-colors">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/></svg>
          </button>
        </div>
        {/* Current workspace name */}
        <div className="px-4 pb-3 border-b border-[#e7dcc9] dark:border-[#3a2e1f]">
          <p className="text-[14px] font-semibold text-[#33291f] dark:text-white truncate">{workspaces.find(w => w.id === activeWsId)?.name || '工作台'}</p>
        </div>

        {/* Workspaces — hidden, keep state functional */}
        <div className="hidden">
          <div className="flex-1 overflow-y-auto">
            {workspaces.map(ws => {
              const isExpanded = expandedWsIds.has(ws.id);
              const rootCards = ws.cards.filter(c => !c.sourceCardId);
              const childrenOf = (parentId: string) => ws.cards.filter(c => c.sourceCardId === parentId);
              const cardLabel = (c: CanvasCard) =>
                c.type === 'article' ? c.article?.title?.slice(0, 20) || '文章'
                : c.type === 'category' ? c.categoryLabel || '分类'
                : c.label || c.type;
              const cardIcon = (c: CanvasCard) =>
                c.type === 'article' ? '□' : c.type === 'category' ? '▤' : c.type === 'mindmap' ? '◇' : c.type === 'kg' ? '⬡' : c.type === 'blog' ? '≡' : '◎';

              return (
                <div key={ws.id}>
                  {/* Workspace row */}
                  <div
                    draggable
                    onDragStart={e => { setWsDragId(ws.id); e.dataTransfer.effectAllowed = 'move'; }}
                    onDragOver={e => { e.preventDefault(); setWsDragOverId(ws.id); }}
                    onDragLeave={() => { if (wsDragOverId === ws.id) setWsDragOverId(null); }}
                    onDrop={e => {
                      e.preventDefault();
                      if (wsDragId && wsDragId !== ws.id) {
                        setWorkspaces(prev => {
                          const arr = [...prev];
                          const fromIdx = arr.findIndex(w => w.id === wsDragId);
                          const toIdx = arr.findIndex(w => w.id === ws.id);
                          const [moved] = arr.splice(fromIdx, 1);
                          arr.splice(toIdx, 0, moved);
                          return arr;
                        });
                      }
                      setWsDragId(null); setWsDragOverId(null);
                    }}
                    onDragEnd={() => { setWsDragId(null); setWsDragOverId(null); }}
                    onClick={() => switchWorkspace(ws.id)}
                    onDoubleClick={e => { e.stopPropagation(); setEditingWsId(ws.id); }}
                    className={`group flex items-center gap-2 px-3 py-2 mx-2 rounded-lg text-[13px] cursor-grab active:cursor-grabbing transition-all ${
                      activeWsId === ws.id ? 'bg-[#e0703a]/10 text-[#e0703a] font-medium' : 'text-[#4a3d2e] dark:text-[#b7a68e] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218]'
                    } ${wsDragOverId === ws.id && wsDragId !== ws.id ? 'border-t-2 border-[#e0703a]' : 'border-t-2 border-transparent'}
                      ${wsDragId === ws.id ? 'opacity-40' : ''}`}>
                    {ws.cards.length > 0 ? (
                      <span className={`text-[10px] text-[#b7a68e] dark:text-[#6e5f4b] transition-transform cursor-pointer ${isExpanded ? 'rotate-90' : ''}`}
                        onClick={e => { e.stopPropagation(); toggleWsExpand(ws.id); }}>▶</span>
                    ) : (
                      <span className="text-[10px] text-transparent">▶</span>
                    )}
                    {editingWsId === ws.id ? (
                      <input
                        autoFocus
                        defaultValue={ws.name}
                        className="flex-1 min-w-0 bg-transparent text-[13px] outline-none border-b border-[#e0703a] py-0"
                        onClick={e => e.stopPropagation()}
                        onBlur={e => { renameWorkspace(ws.id, e.target.value || ws.name); setEditingWsId(null); }}
                        onKeyDown={e => {
                          if (e.key === 'Enter') { renameWorkspace(ws.id, (e.target as HTMLInputElement).value || ws.name); setEditingWsId(null); }
                          if (e.key === 'Escape') setEditingWsId(null);
                        }}
                      />
                    ) : (
                      <span className="flex-1 truncate">{ws.name}</span>
                    )}
                    <span className="text-[10px] text-[#84735f] dark:text-[#a08d74]">{ws.cards.length > 0 ? ws.cards.length : ''}</span>
                    {workspaces.length > 1 && (
                      <button onClick={e => { e.stopPropagation(); deleteWorkspace(ws.id); }}
                        className="text-[#b7a68e] dark:text-[#6e5f4b] hover:text-[#c84b33] text-[10px] opacity-0 group-hover:opacity-100">✕</button>
                    )}
                  </div>

                  {/* Card tree */}
                  {isExpanded && ws.cards.length > 0 && (
                    <div className="ml-5 mr-2 mb-1">
                      {rootCards.map(card => {
                        const children = childrenOf(card.id);
                        const hasChildren = children.length > 0;
                        const isCardExpanded = expandedCardIds.has(card.id);
                        return (
                          <div key={card.id}>
                            <div
                              onClick={e => { e.stopPropagation(); switchWorkspace(ws.id); setSelectedIds(new Set([card.id])); setActiveId(card.id); }}
                              className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] cursor-pointer transition-colors ${
                                activeId === card.id && activeWsId === ws.id ? 'bg-[#e0703a]/8 text-[#e0703a]' : 'text-[#84735f] dark:text-[#a08d74] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218] hover:text-[#4a3d2e]'
                              }`}>
                              {hasChildren ? (
                                <span className={`text-[9px] shrink-0 text-[#b7a68e] dark:text-[#6e5f4b] cursor-pointer transition-transform ${isCardExpanded ? 'rotate-90' : ''}`}
                                  onClick={e => { e.stopPropagation(); toggleCardExpand(card.id); }}>▶</span>
                              ) : (
                                <span className="text-[9px] shrink-0 text-transparent">▶</span>
                              )}
                              <span className="text-[11px] shrink-0">{cardIcon(card)}</span>
                              <span className="flex-1 truncate">{cardLabel(card)}</span>
                              {hasChildren && <span className="text-[9px] text-[#b7a68e] dark:text-[#6e5f4b]">{children.length}</span>}
                            </div>
                            {hasChildren && isCardExpanded && (
                              <div className="ml-4 border-l border-[#e7dcc9] dark:border-[#3a2e1f]">
                                {children.map(child => (
                                  <div key={child.id}
                                    onClick={e => { e.stopPropagation(); switchWorkspace(ws.id); setSelectedIds(new Set([child.id])); setActiveId(child.id); }}
                                    className={`flex items-center gap-1.5 px-2 py-1 ml-1 rounded-md text-[11px] cursor-pointer transition-colors ${
                                      activeId === child.id && activeWsId === ws.id ? 'bg-[#e0703a]/8 text-[#e0703a]' : 'text-[#84735f] dark:text-[#a08d74] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218] hover:text-[#4a3d2e]'
                                    }`}>
                                    <span className="text-[11px] shrink-0">{cardIcon(child)}</span>
                                    <span className="flex-1 truncate">{cardLabel(child)}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Sidebar tabs: 今日信息 / 收藏信息 / 知识库 */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-2 pt-2 pb-0 flex gap-1 border-b border-[#e7dcc9] dark:border-[#3a2e1f]">
            {['今日信息', '收藏', '知识库'].map((label, i) => (
              <button key={label}
                onClick={() => setSidebarTab(i)}
                className={`flex-1 text-[11px] py-2 rounded-t-lg transition-colors ${
                  sidebarTab === i ? 'text-[#e0703a] font-medium bg-[#e0703a]/5 border-b-2 border-[#e0703a] -mb-px' : 'text-[#84735f] dark:text-[#a08d74] hover:text-[#84735f]'
                }`}>{label}</button>
            ))}
          </div>

          {/* Search */}
          <div className="px-3 py-2">
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && doSearch()} placeholder="搜索文章..."
              className="w-full bg-[#f3ece1] dark:bg-[#17120e] border border-[#e7dcc9] dark:border-[#3a2e1f] rounded-lg px-3 py-1.5 text-[12px] text-[#33291f] dark:text-white placeholder-[#b7a68e] dark:placeholder-[#6e5f4b] focus:border-[#e0703a] focus:outline-none" />
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto">
            {sidebarTab === 0 && (
              /* 今日信息 - merged categories */
              (() => {
                const mergeMap: Record<string, { label: string; cats: string[] }> = {
                  'model_release': { label: '模型', cats: ['model_release'] },
                  'paper':         { label: '技术', cats: ['paper', 'open_source', 'api_update', 'tutorial'] },
                  'product_launch':{ label: '产品', cats: ['product_launch', 'tool_review'] },
                  'funding':       { label: '商业', cats: ['funding', 'industry_report', 'market_data', 'policy'] },
                  'opinion':       { label: '观点', cats: ['opinion'] },
                };
                const merged = Object.entries(mergeMap).map(([key, { label, cats }]) => {
                  const matched = digestGroups.filter(g => cats.includes(g.category));
                  const total = matched.reduce((s, g) => s + g.total, 0);
                  const preview = matched.flatMap(g => g.preview || []);
                  const topImp = Math.max(0, ...matched.map(g => g.top_importance));
                  return { category: cats[0], categories: cats, label, total, top_importance: topImp, preview, icon: matched[0]?.icon || '📰' } as DigestGroup & { categories: string[] };
                }).filter(g => g.total > 0);
                // Add uncategorized
                const allMergedCats = Object.values(mergeMap).flatMap(m => m.cats);
                const other = digestGroups.filter(g => !allMergedCats.includes(g.category));
                if (other.length > 0) {
                  const total = other.reduce((s, g) => s + g.total, 0);
                  merged.push({ category: other[0].category, categories: other.map(g => g.category), label: '其他', total, top_importance: 0, preview: other.flatMap(g => g.preview || []), icon: '📰' } as any);
                }
                return merged;
              })().map(g => (
                <div key={g.category}>
                  <button
                    draggable
                    onDragStart={e => {
                      e.dataTransfer.setData('application/ember-category', JSON.stringify({ category: g.category, label: g.label, icon: g.icon }));
                      e.dataTransfer.effectAllowed = 'copy';
                    }}
                    onClick={() => {
                      const cats = (g as any).categories || [g.category];
                      if (category === g.category) { setCategory(''); setActiveCategories([]); }
                      else { setCategory(g.category); setActiveCategories(cats); }
                    }}
                    className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-[13px] text-left transition-colors border-b border-[#faf6f0] dark:border-[#2b2218] cursor-grab active:cursor-grabbing ${
                      category === g.category ? 'bg-[#e0703a]/8 text-[#e0703a] font-medium' : 'text-[#4a3d2e] dark:text-[#b7a68e] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218]'
                    }`}>
                    <span className={`text-[10px] text-[#b7a68e] dark:text-[#6e5f4b] transition-transform ${category === g.category ? 'rotate-90' : ''}`}>▶</span>
                    <span className="flex-1 truncate">{g.label}</span>
                    <span className="text-[11px] text-[#84735f] dark:text-[#a08d74] tabular-nums">{g.total}</span>
                  </button>
                  {category === g.category && (
                    <div className="bg-[#faf6f0] dark:bg-[#211a13]">
                      {fetching ? <div className="text-center text-[#84735f] dark:text-[#a08d74] py-3 text-[11px]">加载中...</div>
: articles.filter(a => priorityFilter === 0 || (priorityFilter === 1 ? (a.importance_score || 0) >= 0.55 : (a.importance_score || 0) >= 0.75)).map(a => {
                        const inCanvas = cards.some(c => c.id === a.id);
                        return (
                          <div key={a.id} draggable={!inCanvas} onDragStart={e => onDragStart(e, a)}
                            className={`flex items-center gap-2 pl-9 pr-3 py-1.5 transition-colors ${
                              inCanvas ? 'opacity-30 cursor-default' : 'cursor-grab hover:bg-[#e7dcc9]/50 active:cursor-grabbing'
                            }`}>
                            <span className="text-[10px] text-[#b7a68e] dark:text-[#6e5f4b] shrink-0">—</span>
                            <span className="text-[12px] text-[#4a3d2e] dark:text-[#b7a68e]/80 truncate">{a.title}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))
            )}
            {sidebarTab === 1 && (
              <div className="px-3 py-2">
                {bookmarks.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="w-10 h-10 rounded-xl bg-[#f3ece1] dark:bg-[#33261a] flex items-center justify-center mb-3">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#33291f" strokeWidth="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
                    </div>
                    <p className="text-[12px] text-[#84735f] dark:text-[#a08d74]">收藏的文章将在这里显示</p>
                  </div>
                ) : bookmarks.map(a => (
                  <div key={a.id} draggable onDragStart={e => onDragStart(e, a)}
                    className="flex items-center gap-2 px-2 py-2 rounded-lg cursor-grab hover:bg-[#f3ece1] dark:hover:bg-[#33261a] transition-colors">
                    <span className="text-[11px] text-[#e0703a] shrink-0">★</span>
                    <span className="text-[12px] text-[#4a3d2e] dark:text-[#b7a68e]/80 truncate">{a.title}</span>
                  </div>
                ))}
              </div>
            )}
            {sidebarTab === 2 && (
              <div className="px-3 py-2">
                {notebooks.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="w-10 h-10 rounded-xl bg-[#f3ece1] dark:bg-[#33261a] flex items-center justify-center mb-3">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#33291f" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                    </div>
                    <p className="text-[12px] text-[#84735f] dark:text-[#a08d74]">知识库内容将在这里显示</p>
                  </div>
                ) : notebooks.map(n => (
                  <div key={n.id} className="flex items-center gap-2 px-2 py-2 rounded-lg">
                    <span className="text-[11px] text-[#b7a68e] dark:text-[#6e5f4b] shrink-0">📓</span>
                    <span className="text-[12px] text-[#4a3d2e] dark:text-[#b7a68e]/80 truncate">{n.title}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </aside>

      {/* ============ CANVAS ============ */}
      <main className="flex-1 relative overflow-hidden bg-[#faf6f0] dark:bg-[#17120e] canvas-grid">
        <div ref={canvasRef}
          className={`w-full h-full overflow-hidden ${draggingOver ? 'bg-[#e0703a]/5' : ''}`}
          style={{ cursor: panDrag ? 'grabbing' : 'default' }}
          onDragOver={onCanvasDragOver} onDragLeave={onCanvasDragLeave} onDrop={onCanvasDrop}
          onClick={onCanvasClick} onMouseDown={onCanvasMouseDown}>

          {cards.length === 0 ? (
            <div className="w-full h-full" />
          ) : (
            <div ref={canvasInnerRef} className="relative origin-top-left"
              style={{ transform: `translate3d(${camera.x}px, ${camera.y}px, 0) scale(${camera.z})`, willChange: 'transform' }}>

              {/* Connection lines between source and generated cards */}
              <svg className="absolute top-0 left-0 pointer-events-none overflow-visible" style={{ width: 1, height: 1 }}>
                {cards.filter(c => c.sourceCardId).map(card => {
                  const src = cards.find(s => s.id === card.sourceCardId);
                  if (!src) return null;
                  const srcW = src.type === 'mindmap' ? 560 : src.type === 'category' ? 420 : src.type === 'article' ? 260 : 320;
                  const cardW = card.type === 'mindmap' ? 560 : card.type === 'category' ? 420 : card.type === 'article' ? 260 : 320;
                  const srcH = 100;
                  const cardH = 100;
                  // Right edge of source → left edge of generated
                  const x1 = src.x + srcW;
                  const y1 = src.y + srcH / 2;
                  const x2 = card.x;
                  const y2 = card.y + cardH / 2;
                  const dx = Math.abs(x2 - x1) * 0.4;
                  return (
                    <path key={`line-${card.id}`}
                      d={`M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`}
                      fill="none" stroke="#b7a68e" strokeWidth="1.5" strokeDasharray="6 4" />
                  );
                })}
              </svg>

              {cards.map(card => {
                const isActive = activeId === card.id;
                const isSelected = selectedIds.has(card.id);
                const w = card.type === 'mindmap' ? 560 : card.type === 'category' ? 420 : card.type === 'article' ? 260 : 320;

                return (
                  <div key={card.id} data-card={card.id}
                    className={`absolute rounded-2xl border bg-white dark:bg-[#211a13] select-none transition-shadow ${
                      isActive ? 'border-[#e0703a] shadow-lg shadow-[#e0703a]/10 z-20'
                      : isSelected ? 'border-[#e0703a]/40 z-10'
                      : 'border-[#e7dcc9] dark:border-[#3a2e1f] hover:border-[#b7a68e] shadow-sm'
                    }`}
                    style={{ left: card.x, top: card.y, width: w }}
                    onMouseDown={e => onCardMouseDown(e, card)}
                    onClick={e => { if (!wasDragged.current) selectCard(card.id, e); }}
                    onDoubleClick={e => { e.stopPropagation(); setExpandedCardId(card.id); }}>

                    {/* Floating toolbar */}
                    {isActive && (card.type === 'article' || card.type === 'category') && (
                      <div className="absolute -top-12 left-1/2 -translate-x-1/2 z-30 flex items-center gap-0.5 bg-white/95 backdrop-blur-xl rounded-xl shadow-lg shadow-black/8 border border-[#e7dcc9] dark:border-[#3a2e1f] px-1 py-1"
                        onClick={e => e.stopPropagation()} onMouseDown={e => e.stopPropagation()}>
                        {card.type === 'article' && <>
                          <button onClick={() => generateMindmap()} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] text-[#4a3d2e] dark:text-[#b7a68e] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218] transition-colors whitespace-nowrap">
                            <span className="text-[14px]">◇</span>思维导图
                          </button>
                          <button onClick={() => generateKG()} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] text-[#4a3d2e] dark:text-[#b7a68e] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218] transition-colors whitespace-nowrap">
                            <span className="text-[14px]">⬡</span>知识图谱
                          </button>
                          <button onClick={() => generateBlog()} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] text-[#4a3d2e] dark:text-[#b7a68e] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218] transition-colors whitespace-nowrap">
                            <span className="text-[14px]">▤</span>生成文章
                          </button>
                          <button onClick={() => generatePodcast()} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] text-[#4a3d2e] dark:text-[#b7a68e] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218] transition-colors whitespace-nowrap">
                            <span className="text-[14px]">◎</span>播客脚本
                          </button>
                        </>}
                        {card.type === 'category' && <>
                          <button onClick={() => summarizeCategory(card.id)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] text-[#4a3d2e] dark:text-[#b7a68e] hover:bg-[#faf6f0] dark:hover:bg-[#2b2218] transition-colors whitespace-nowrap">
                            <span className="text-[14px]">≡</span>总结概览
                          </button>
                        </>}
                        <div className="w-px h-5 bg-[#e7dcc9] mx-0.5" />
                        <button onClick={e => { e.stopPropagation(); removeCard(card.id); }}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] text-[#c84b33] hover:bg-[#c84b33]/8 transition-colors whitespace-nowrap">
                          <span className="text-[14px]">⊘</span>删除
                        </button>
                      </div>
                    )}

                    {/* Card header */}
                    <div className="px-3 py-2 border-b border-[#faf6f0] dark:border-[#2b2218] flex items-center justify-between">
                      <span className={`text-[10px] px-1.5 py-px rounded-md font-medium ${
                        card.type === 'article' ? 'bg-[#e0703a]/10 text-[#e0703a]'
                        : card.type === 'category' ? 'bg-[#e0703a]/10 text-[#e0703a]'
                        : card.type === 'mindmap' ? 'bg-[#7fa05c]/10 text-[#7fa05c]'
                        : card.type === 'kg' ? 'bg-[#b98a2f]/10 text-[#b98a2f]'
                        : card.type === 'blog' ? 'bg-[#d9a441]/10 text-[#d9a441]'
                        : 'bg-[#d9a441]/10 text-[#d9a441]'
                      }`}>
                        {card.type === 'article' ? card.article?.category
                          : card.type === 'category' ? card.categoryLabel
                          : card.label}
                      </span>
                      <div className="flex items-center gap-2">
                        <button onClick={e => { e.stopPropagation(); removeCard(card.id); }}
                          className="text-[#b7a68e] dark:text-[#6e5f4b] hover:text-[#c84b33] text-xs leading-none">✕</button>
                      </div>
                    </div>

                    {/* Card body */}
                    <div className={`${card.type === 'mindmap' ? 'h-[320px]' : card.type === 'category' ? 'px-3 py-2.5 max-h-[500px] overflow-y-auto' : 'px-3 py-2.5 max-h-[400px] overflow-y-auto'}`}>
                      {card.type === 'article' && card.article && (
                        <>
                          <p className="text-[13px] leading-snug font-medium text-[#33291f] dark:text-white line-clamp-3">{card.article.title}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-[10px] text-[#84735f] dark:text-[#a08d74]">{card.article.source_id}</span>
                            <span className="text-[10px] text-[#84735f] dark:text-[#a08d74]">{timeAgo(card.article.published_at)}</span>
                            <div className="ml-auto"><ScoreBar value={card.article.importance_score} /></div>
                          </div>
                          {card.article.tags?.length > 0 && (
                            <div className="flex gap-1 mt-2 flex-wrap">
                              {card.article.tags.slice(0, 3).map(t => (
                                <span key={t} className="px-1.5 py-px rounded-md text-[9px] bg-[#faf6f0] dark:bg-[#17120e] text-[#84735f] dark:text-[#a08d74]">{t}</span>
                              ))}
                            </div>
                          )}
                        </>
                      )}

                      {card.type === 'mindmap' && (
                        card.data ? <MindmapTree data={card.data.root || card.data} onUpdate={(newData: any) => {
                          const wrapped = card.data.root ? { ...card.data, root: newData } : newData;
                          updateGenCard(card.id, { data: wrapped });
                        }} />
                        : card.loading ? <LoadingDots />
                        : <p className="text-xs text-[#c84b33] pointer-events-none">{card.content}</p>
                      )}

                      {card.type === 'kg' && (
                        card.loading ? <LoadingDots /> :
                        card.data ? (
                          <div className="space-y-3">
                            <div className="flex flex-wrap gap-1">
                              {card.data.nodes?.map((n: any) => (
                                <span key={n.id} className="px-1.5 py-0.5 rounded-md text-[10px] border border-[#e7dcc9] dark:border-[#3a2e1f] text-[#4a3d2e] dark:text-[#b7a68e]">{n.name}</span>
                              ))}
                            </div>
                            <div className="space-y-1">
                              {card.data.edges?.map((e: any, i: number) => (
                                <div key={i} className="text-[10px] text-[#84735f] dark:text-[#a08d74]">
                                  <span className="text-[#33291f] dark:text-white">{e.source}</span>
                                  <span className="text-[#e0703a] mx-1">→ {e.relation} →</span>
                                  <span className="text-[#33291f] dark:text-white">{e.target}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : <p className="text-xs text-[#c84b33] pointer-events-none">{card.content}</p>
                      )}

                      {(card.type === 'blog' || card.type === 'podcast') && (
                        card.loading && !card.content ? <LoadingDots /> :
                        card.content && card.content.includes('<h') ?
                        <div className="text-[11px] leading-5 text-[#4a3d2e] dark:text-[#b7a68e] pointer-events-none [&_h2]:text-[12px] [&_h2]:font-bold [&_h2]:my-2 [&_h3]:text-[11px] [&_h3]:font-bold [&_h3]:my-1 [&_p]:mb-1 [&_strong]:font-semibold [&_blockquote]:border-l-2 [&_blockquote]:border-[#e0703a] [&_blockquote]:pl-2 [&_blockquote]:text-[10px] [&_blockquote]:text-[#a08d74] [&_hr]:my-2 [&_ul]:pl-3 [&_li]:text-[10px]" dangerouslySetInnerHTML={{ __html: card.content }} /> :
                        <MarkdownContent text={card.content || ''} className="text-[11px] leading-5 text-[#4a3d2e] dark:text-[#b7a68e] pointer-events-none" />
                      )}

                      {card.type === 'category' && card.articles && (
                        <div className="space-y-0.5">
                          <div className="text-[11px] text-[#84735f] dark:text-[#a08d74] mb-2">{card.articles.length} 篇文章</div>
                          {card.articles.map((a, i) => (
                            <div key={a.id}
                              data-draggable-article
                              draggable
                              onDragStart={e => { e.stopPropagation(); onDragStart(e, a); }}
                              className="flex items-start gap-2 py-1.5 px-2 rounded-lg hover:bg-[#faf6f0] dark:hover:bg-[#2b2218] cursor-grab active:cursor-grabbing transition-colors">
                              <span className="text-[10px] text-[#b7a68e] dark:text-[#6e5f4b] mt-0.5 shrink-0">{i + 1}</span>
                              <div className="flex-1 min-w-0">
                                <p className="text-[12px] text-[#4a3d2e] dark:text-[#b7a68e] leading-snug line-clamp-2">{a.title}</p>
                                <div className="flex items-center gap-2 mt-1">
                                  <span className="text-[9px] text-[#84735f] dark:text-[#a08d74]">{a.source_id}</span>
                                  <span className="text-[9px] text-[#84735f] dark:text-[#a08d74]">{timeAgo(a.published_at)}</span>
                                  <div className="ml-auto"><ScoreBar value={a.importance_score} /></div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Bounding box around multi-selected cards */}
              {selectedIds.size > 1 && (() => {
                const selCards = cards.filter(c => selectedIds.has(c.id));
                if (selCards.length < 2) return null;
                const PAD = 12;
                let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                for (const c of selCards) {
                  const cw = c.type === 'category' ? 420 : c.type === 'article' ? 260 : 320;
                  minX = Math.min(minX, c.x);
                  minY = Math.min(minY, c.y);
                  maxX = Math.max(maxX, c.x + cw);
                  maxY = Math.max(maxY, c.y + 200);
                }
                return (
                  <div className="absolute pointer-events-none z-30 border-2 border-dashed border-[#e0703a]/40 rounded-2xl"
                    style={{ left: minX - PAD, top: minY - PAD, width: maxX - minX + PAD * 2, height: maxY - minY + PAD * 2 }}>
                    <div className="absolute -top-7 left-1/2 -translate-x-1/2 bg-[#e0703a] text-white text-[11px] px-3 py-1 rounded-full whitespace-nowrap font-medium">
                      已选择 {selCards.length} 个卡片 · 按 Delete 删除
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {draggingOver && <div className="absolute inset-0 border-2 border-dashed border-[#e0703a]/30 rounded-2xl pointer-events-none z-50" />}

          {/* Marquee selection rectangle */}
          {marquee && Math.abs(marquee.curX - marquee.startX) + Math.abs(marquee.curY - marquee.startY) > 5 && (() => {
            const rect = canvasRef.current?.getBoundingClientRect();
            if (!rect) return null;
            const left = Math.min(marquee.startX, marquee.curX) - rect.left;
            const top = Math.min(marquee.startY, marquee.curY) - rect.top;
            const width = Math.abs(marquee.curX - marquee.startX);
            const height = Math.abs(marquee.curY - marquee.startY);
            return <div className="absolute border border-[#e0703a] bg-[#e0703a]/8 rounded-lg pointer-events-none z-50" style={{ left, top, width, height }} />;
          })()}
        </div>

        {/* ============ RIGHT CHAT BUBBLES ============ */}
        {(!chatPanelOpen || chatMessages.length === 0 || chatCollapsed) ? (
            <button className="absolute top-3 right-4 z-[35] px-3.5 py-1.5 rounded-full transition-transform hover:scale-105"
              style={{ background: 'rgba(255,255,255,0.7)', backdropFilter: 'saturate(180%) blur(20px)', WebkitBackdropFilter: 'saturate(180%) blur(20px)', boxShadow: '0 2px 12px rgba(0,0,0,0.1), inset 0 0 0 1px rgba(0,0,0,0.12)' }}
              onClick={e => { e.stopPropagation(); if (chatMessages.length > 0) { setChatCollapsed(false); setChatPanelOpen(true); } }}>
              <svg width="72" height="16" viewBox="0 0 72 16">
                <defs><linearGradient id="fcg" x1="0" y1="0" x2="72" y2="16" gradientUnits="userSpaceOnUse"><stop stopColor="#e0703a"/><stop offset="1" stopColor="#f0b34a"/></linearGradient></defs>
                <text x="0" y="13" fill="none" stroke="url(#fcg)" strokeWidth="0.6" fontSize="13" fontWeight="700" fontFamily="-apple-system,BlinkMacSystemFont,sans-serif" letterSpacing="-0.3">Ember.ai</text>
              </svg>
            </button>
        ) : (
            /* Expanded: floating bubbles */
            <div className="absolute top-3 right-4 w-[320px] max-h-[55vh] z-[35] flex flex-col gap-2.5 overflow-y-auto pointer-events-none pr-1">
              <div className="flex justify-end pointer-events-auto">
                <button onClick={e => { e.stopPropagation(); setChatCollapsed(true); }} className="w-6 h-6 rounded-full flex items-center justify-center transition-opacity hover:opacity-70"
                  style={{ background: 'rgba(255,255,255,0.5)', backdropFilter: 'saturate(180%) blur(20px)', WebkitBackdropFilter: 'saturate(180%) blur(20px)', boxShadow: '0 1px 4px rgba(0,0,0,0.08)', color: 'rgba(0,0,0,0.3)', fontSize: 11 }}>&times;</button>
              </div>
              {chatMessages.map((msg, i) => (
                <div key={i} className="flex justify-end pointer-events-auto">
                  <div className="max-w-[90%] rounded-[16px] px-4 py-3 text-[13px] leading-[1.75]"
                    style={{
                      background: msg.role === 'user' ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.55)',
                      backdropFilter: 'saturate(180%) blur(20px)',
                      WebkitBackdropFilter: 'saturate(180%) blur(20px)',
                      color: 'rgba(0,0,0,0.8)',
                      boxShadow: '0 1px 6px rgba(0,0,0,0.06), inset 0 0 0 0.5px rgba(255,255,255,0.5)',
                    }}>
                    {msg.role === 'user' && (
                      <div className="text-[11px] mb-1.5" style={{ color: 'rgba(0,0,0,0.3)' }}>你</div>
                    )}
                    {msg.role === 'ai' && (
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <svg width="12" height="12" viewBox="0 0 32 32" fill="none"><rect width="32" height="32" rx="7" fill="url(#fp2)"/><path d="M16 4c2 5 7 8.4 7 13.8a7 7 0 1 1-14 0c0-2.5 1.2-4.7 2.8-6.6.3 1.6 1 3 2.2 4-.3-4 1-8.8 2-11.2z" fill="#fff" fillOpacity="0.95"/><circle cx="23.5" cy="9.5" r="1.4" fill="#f0b34a"/><defs><linearGradient id="fp2" x1="0" y1="0" x2="32" y2="32"><stop stopColor="#e0703a"/><stop offset="1" stopColor="#f0b34a"/></linearGradient></defs></svg>
                        <span className="text-[11px]" style={{ color: 'rgba(0,0,0,0.3)' }}>Ember AI</span>
                      </div>
                    )}
                    {msg.role === 'ai' && !msg.text && chatStreaming && (
                      <span style={{ color: 'rgba(0,0,0,0.35)' }}>思考中...</span>
                    )}
                    {msg.text && <MarkdownContent text={msg.text} className="text-[13px] leading-[1.7]" />}
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
        )}

        {/* ============ BOTTOM CHAT BAR ============ */}
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 z-30 w-[680px] max-w-[80%]" onClick={e => e.stopPropagation()}>
          <div className="bg-white/90 backdrop-blur-xl rounded-2xl shadow-lg shadow-black/8 border border-[#e7dcc9] dark:border-[#3a2e1f] px-5 pt-3 pb-3">
            <textarea
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSubmit(); } }}
              rows={1}
              placeholder={activeArticleCard || activeCategoryCard
                ? '针对选中内容提问...'
                : '和 AI 聊聊，问任何关于 AI 行业的问题...'}
              className="w-full resize-none bg-transparent text-[14px] text-[#33291f] dark:text-white placeholder-[#b7a68e] focus:outline-none leading-6"
              style={{ minHeight: 28, maxHeight: 120 }}
              onInput={e => { const t = e.target as HTMLTextAreaElement; t.style.height = '28px'; t.style.height = t.scrollHeight + 'px'; }}
            />
            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-2">
                {(activeArticleCard || activeCategoryCard) && (
                  <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#faf6f0] dark:bg-[#17120e] text-[12px] text-[#4a3d2e] dark:text-[#b7a68e]">
                    ◉ {activeArticleCard ? '文章' : '分类'}
                    <span className="text-[#84735f] dark:text-[#a08d74] max-w-[120px] truncate">
                      {activeArticleCard ? activeArticleCard.article?.title?.slice(0, 12) : activeCategoryCard?.categoryLabel}
                    </span>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center bg-[#faf6f0] dark:bg-[#17120e] rounded-full p-0.5">
                  {([
                    { id: 'flash' as const, label: '闪电', icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> },
                    { id: 'balanced' as const, label: '均衡', icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v18"/><path d="M5 6h14"/><path d="M3 10l4-4v6a2 2 0 0 1-4 0z"/><path d="M17 10l4-4v6a2 2 0 0 1-4 0z"/></svg> },
                    { id: 'think' as const, label: '深思', icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/><path d="M8 12a4 4 0 0 1 8 0"/></svg> },
                  ]).map(m => (
                    <button key={m.id} onClick={() => setChatModel(m.id)}
                      className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] transition-all ${
                        chatModel === m.id
                          ? 'bg-white dark:bg-[#211a13] shadow-sm text-[#33291f] dark:text-white font-medium'
                          : 'text-[#84735f] dark:text-[#a08d74] hover:text-[#4a3d2e]'
                      }`}>
                      {m.icon}{m.label}
                    </button>
                  ))}
                </div>
                <button onClick={handleChatSubmit}
                    disabled={!chatInput.trim()}
                    className="w-8 h-8 flex items-center justify-center rounded-full bg-[#e0703a] text-white hover:bg-[#f08a52] disabled:opacity-40 transition-all">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="19" x2="12" y2="5" /><polyline points="5 12 12 5 19 12" />
                    </svg>
                  </button>
              </div>
            </div>
          </div>
        </div>

        {/* Zoom controls */}
        <div className="absolute bottom-5 right-5 z-30 flex items-center gap-0.5 bg-white/90 backdrop-blur-xl border border-[#e7dcc9] dark:border-[#3a2e1f] rounded-xl px-1 py-0.5 shadow-sm"
          onClick={e => e.stopPropagation()}>
          <button onClick={() => setCamera(c => ({ ...c, z: Math.min(c.z * 1.2, 3) }))}
            className="text-[#4a3d2e] dark:text-[#b7a68e] hover:text-[#e0703a] px-2 py-1 text-sm">+</button>
          <button onClick={() => setCamera({ x: 0, y: 0, z: 1 })}
            className="text-[10px] text-[#84735f] dark:text-[#a08d74] hover:text-[#e0703a] px-1 py-1 min-w-[40px] text-center tabular-nums">
            {Math.round(camera.z * 100)}%
          </button>
          <button onClick={() => setCamera(c => ({ ...c, z: Math.max(c.z * 0.8, 0.2) }))}
            className="text-[#4a3d2e] dark:text-[#b7a68e] hover:text-[#e0703a] px-2 py-1 text-sm">−</button>
        </div>

        {/* ============ EXPANDED CARD OVERLAY ============ */}
        {expandedCardId && (() => {
          const card = cards.find(c => c.id === expandedCardId);
          if (!card) return null;

          // Mindmap
          if (card.type === 'mindmap' && card.data) {
            return (
              <div className="absolute inset-0 z-50 bg-white/95 backdrop-blur-xl flex flex-col"
                onClick={() => setExpandedCardId(null)}>
                <div className="h-12 border-b border-[#e7dcc9] dark:border-[#3a2e1f] flex items-center justify-between px-6 shrink-0"
                  onClick={e => e.stopPropagation()}>
                  <span className="text-sm font-medium text-[#33291f] dark:text-white">{card.label || '思维导图'}</span>
                  <button onClick={() => setExpandedCardId(null)}
                    className="text-xs text-[#84735f] dark:text-[#a08d74] hover:text-[#e0703a] px-3 py-1.5 rounded-lg border border-[#e7dcc9] dark:border-[#3a2e1f] hover:border-[#b7a68e] transition-colors">
                    关闭
                  </button>
                </div>
                <div className="flex-1" onClick={e => e.stopPropagation()}>
                  <MindmapTree data={card.data.root || card.data} />
                </div>
              </div>
            );
          }

          // Blog / KG / Category / any content card
          return <ExpandedCardOverlay card={card} onClose={() => setExpandedCardId(null)} />;
        })()}

        {/* ============ ARTICLE DETAIL CARD ============ */}
        {detailArticle && (
          <div className="absolute top-4 right-4 w-[360px] z-40">
            <div className="max-h-[75vh] bg-white dark:bg-[#211a13] rounded-2xl shadow-2xl shadow-black/10 border border-[#e7dcc9] dark:border-[#3a2e1f] flex flex-col">
              <div className="flex items-center justify-between px-5 py-3 border-b border-[#faf6f0] dark:border-[#2b2218] shrink-0">
                <span className="text-[13px] font-semibold text-[#33291f] dark:text-white truncate">{detailArticle.source_id}</span>
                <div className="flex items-center gap-3">
                  {detailArticle.url && (
                    <a href={detailArticle.url} target="_blank" rel="noopener noreferrer"
                      className="text-[11px] text-[#e0703a] hover:underline">原文链接 ↗</a>
                  )}
                  <button onClick={() => setDetailArticle(null)}
                    className="text-[#b7a68e] dark:text-[#6e5f4b] hover:text-[#4a3d2e] text-sm">✕</button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-5 py-4">
                <h2 className="text-[16px] font-semibold text-[#33291f] dark:text-white leading-snug mb-3">{detailArticle.title}</h2>
                <div className="flex items-center gap-2 mb-4 flex-wrap">
                  <span className="text-[11px] text-[#84735f] dark:text-[#a08d74]">{detailArticle.source_id}</span>
                  <span className="text-[11px] text-[#84735f] dark:text-[#a08d74]">{timeAgo(detailArticle.published_at)}</span>
                  {detailArticle.tags?.slice(0, 4).map(t => (
                    <span key={t} className="px-1.5 py-px rounded-md text-[9px] bg-[#faf6f0] dark:bg-[#17120e] text-[#84735f] dark:text-[#a08d74]">{t}</span>
                  ))}
                </div>
                <div className="text-[13px] leading-7 text-[#4a3d2e] dark:text-[#b7a68e] whitespace-pre-wrap">
                  {detailArticle.content || '暂无正文内容'}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
    </div>
  );
}

// ============ COMPONENTS ============
function ExpandedCardOverlay({ card, onClose }: { card: any; onClose: () => void; onSave?: (content: string) => void }) {
  const [translated, setTranslated] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showDownload, setShowDownload] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(card.article?.content || card.content || '');

  const title = card.article?.title || card.label || card.categoryLabel || 'article';
  const originalText = card.article?.content || card.content || '暂无内容';
  const hasEnglish = originalText.replace(/[^a-zA-Z]/g, '').length > originalText.length * 0.3;
  const displayText = translated || originalText;

  const handleTranslate = async () => {
    if (translated) { setTranslated(null); return; }
    setTranslating(true);
    setTranslated('');
    try {
      const res = await api.translate(originalText);
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of decoder.decode(value).split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6));
              if (d.text) { buf += d.text; setTranslated(buf); }
            } catch {}
          }
        }
      }
    } catch {} finally { setTranslating(false); }
  };

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center animate-[fadeIn_0.15s_ease]" style={{ background: 'rgba(0,0,0,0.25)' }}
      onClick={onClose}>
      <div className="w-[680px] max-w-[88%] max-h-[80vh] rounded-2xl flex flex-col overflow-hidden animate-[scaleIn_0.2s_ease]"
        style={{ background: 'rgba(255,255,255,0.88)', backdropFilter: 'saturate(180%) blur(20px)', WebkitBackdropFilter: 'saturate(180%) blur(20px)', boxShadow: '0 8px 40px rgba(0,0,0,0.12)' }}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 shrink-0" style={{ borderBottom: '0.5px solid rgba(0,0,0,0.06)' }}>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <svg width="14" height="14" viewBox="0 0 32 32" fill="none" className="shrink-0">
              <rect width="32" height="32" rx="7" fill="url(#fex)"/>
              <path d="M16 4c2 5 7 8.4 7 13.8a7 7 0 1 1-14 0c0-2.5 1.2-4.7 2.8-6.6.3 1.6 1 3 2.2 4-.3-4 1-8.8 2-11.2z" fill="#fff" fillOpacity="0.95"/>
              <circle cx="23.5" cy="9.5" r="1.4" fill="#f0b34a"/>
              <defs><linearGradient id="fex" x1="0" y1="0" x2="32" y2="32"><stop stopColor="#e0703a"/><stop offset="1" stopColor="#f0b34a"/></linearGradient></defs>
            </svg>
            <span className="text-[14px] font-semibold truncate" style={{ color: 'rgba(0,0,0,0.85)' }}>{card.article?.title || card.label || card.categoryLabel || 'AI 生成内容'}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {hasEnglish && !editing && (
              <button onClick={handleTranslate} className="px-2.5 py-1 rounded-lg text-[11px] transition-colors"
                style={{ background: translated ? 'rgba(224,112,58,0.15)' : 'rgba(0,0,0,0.04)', color: translated ? '#e0703a' : 'rgba(0,0,0,0.45)' }}>
                {translating ? '翻译中...' : translated ? '查看原文' : '翻译为中文'}
              </button>
            )}
            {(card.type === 'blog' || card.type === 'podcast') && (
              <>
                <button onClick={() => {
                  if (editing) {
                    card.content = editContent;
                    setEditing(false);
                  } else {
                    setEditing(true);
                    setEditContent(translated || card.content || '');
                  }
                }} className="px-2.5 py-1 rounded-lg text-[11px] transition-colors"
                  style={{ background: editing ? 'rgba(224,112,58,0.15)' : 'rgba(0,0,0,0.04)', color: editing ? '#e0703a' : 'rgba(0,0,0,0.45)' }}>
                  {editing ? '保存' : '编辑'}
                </button>
                {editing && (
                  <button onClick={() => setEditing(false)} className="px-2.5 py-1 rounded-lg text-[11px] transition-colors"
                    style={{ background: 'rgba(0,0,0,0.04)', color: 'rgba(0,0,0,0.45)' }}>
                    取消
                  </button>
                )}
              </>
            )}
            <button onClick={onClose} className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70"
              style={{ background: 'rgba(0,0,0,0.06)', color: 'rgba(0,0,0,0.3)', fontSize: 12 }}>&times;</button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {editing ? (
            <div
              contentEditable
              suppressContentEditableWarning
              onBlur={e => setEditContent(e.currentTarget.innerHTML)}
              onInput={e => setEditContent(e.currentTarget.innerHTML)}
              className="text-[14px] leading-[1.85] focus:outline-none min-h-[200px]"
              style={{ color: 'rgba(0,0,0,0.8)', cursor: 'text' }}
              dangerouslySetInnerHTML={{ __html: editContent }}
            />
          ) : (
            displayText.includes('<h') || displayText.includes('<p')
              ? <div className="text-[14px] leading-[1.85]" dangerouslySetInnerHTML={{ __html: displayText }} />
              : <MarkdownContent text={displayText} className="text-[14px] leading-[1.85]" />
          )}
        </div>
        {/* Action bar */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 shrink-0" style={{ borderTop: '0.5px solid rgba(0,0,0,0.06)' }}>
          <button onClick={() => {
            const plain = displayText.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
            navigator.clipboard.writeText(displayText.includes('<') ? displayText : plain);
            setCopied(true); setTimeout(() => setCopied(false), 2000);
          }} className="px-3 py-1.5 rounded-lg text-[12px] flex items-center gap-1.5 transition-colors"
            style={{ background: copied ? 'rgba(224,112,58,0.15)' : 'rgba(0,0,0,0.04)', color: copied ? '#e0703a' : 'rgba(0,0,0,0.5)' }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            {copied ? '已复制' : '复制'}
          </button>
          <div className="relative">
            <button onClick={() => setShowDownload(p => !p)} className="px-3 py-1.5 rounded-lg text-[12px] flex items-center gap-1.5 transition-colors"
              style={{ background: 'rgba(0,0,0,0.04)', color: 'rgba(0,0,0,0.5)' }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              下载
            </button>
            {showDownload && (
              <div className="absolute bottom-full right-0 mb-1 rounded-xl overflow-hidden shadow-lg" style={{ background: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(20px)', border: '0.5px solid rgba(0,0,0,0.08)' }}>
                {[
                  { label: 'Markdown', ext: 'md', fn: () => {
                    let md = displayText;
                    if (md.includes('<')) {
                      md = md
                        .replace(/<h1[^>]*>(.*?)<\/h1>/gi, '\n# $1\n')
                        .replace(/<h2[^>]*>(.*?)<\/h2>/gi, '\n## $1\n')
                        .replace(/<h3[^>]*>(.*?)<\/h3>/gi, '\n### $1\n')
                        .replace(/<h4[^>]*>(.*?)<\/h4>/gi, '\n#### $1\n')
                        .replace(/<strong[^>]*>(.*?)<\/strong>/gi, '**$1**')
                        .replace(/<b[^>]*>(.*?)<\/b>/gi, '**$1**')
                        .replace(/<em[^>]*>(.*?)<\/em>/gi, '*$1*')
                        .replace(/<i[^>]*>(.*?)<\/i>/gi, '*$1*')
                        .replace(/<blockquote[^>]*>(.*?)<\/blockquote>/gis, '\n> $1\n')
                        .replace(/<li[^>]*>(.*?)<\/li>/gi, '- $1')
                        .replace(/<hr[^>]*\/?>/gi, '\n---\n')
                        .replace(/<br\s*\/?>/gi, '\n')
                        .replace(/<p[^>]*>(.*?)<\/p>/gis, '$1\n\n')
                        .replace(/<ul[^>]*>|<\/ul>|<ol[^>]*>|<\/ol>/gi, '\n')
                        .replace(/<[^>]+>/g, '')
                        .replace(/\n{3,}/g, '\n\n')
                        .trim();
                    }
                    const blob = new Blob([md], { type: 'text/markdown' });
                    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
                    a.download = (title || 'article') + '.md'; a.click();
                  }},
                  { label: 'HTML (Doc)', ext: 'html', fn: () => {
                    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title><style>body{font-family:-apple-system,sans-serif;max-width:700px;margin:40px auto;padding:0 20px;line-height:1.8;color:#333}h1,h2,h3{color:#1a1a1a}blockquote{border-left:3px solid #e0703a;padding-left:14px;color:#6e5f4b;margin:16px 0}</style></head><body>${displayText.includes('<') ? displayText : '<p>' + displayText.replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>') + '</p>'}</body></html>`;
                    const blob = new Blob([html], { type: 'text/html' });
                    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
                    a.download = (title || 'article') + '.html'; a.click();
                  }},
                  { label: 'PDF', ext: 'pdf', fn: () => {
                    const w = window.open('', '_blank');
                    if (w) {
                      w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title><style>body{font-family:-apple-system,sans-serif;max-width:700px;margin:40px auto;padding:0 20px;line-height:1.8;color:#333}h1,h2,h3{color:#1a1a1a}blockquote{border-left:3px solid #e0703a;padding-left:14px;color:#6e5f4b}</style></head><body>${displayText.includes('<') ? displayText : '<p>' + displayText.replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>') + '</p>'}</body></html>`);
                      w.document.close();
                      setTimeout(() => { w.print(); }, 500);
                    }
                  }},
                ].map(item => (
                  <button key={item.ext} onClick={() => { item.fn(); setShowDownload(false); }}
                    className="w-full px-4 py-2 text-[12px] text-left hover:bg-black/5 transition-colors flex items-center justify-between gap-4"
                    style={{ color: 'rgba(0,0,0,0.7)' }}>
                    <span>{item.label}</span>
                    <span className="text-[10px]" style={{ color: 'rgba(0,0,0,0.3)' }}>.{item.ext}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MarkdownContent({ text, className }: { text: string; className?: string }) {
  const html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h4 style="font-size:13px;font-weight:700;margin:12px 0 4px;color:var(--ink)">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="font-size:14px;font-weight:700;margin:14px 0 6px;color:var(--ink)">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="font-size:15px;font-weight:700;margin:16px 0 6px;color:var(--ink)">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight:600">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid rgba(0,0,0,0.06);margin:10px 0"/>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:16px;margin-bottom:2px;list-style:disc">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left:16px;margin-bottom:2px;list-style:decimal">$1. $2</li>')
    .replace(/\n{2,}/g, '</p><p style="margin-bottom:6px">')
    .replace(/\n/g, '<br/>');
  return <div className={className} dangerouslySetInnerHTML={{ __html: `<p style="margin-bottom:6px">${html}</p>` }} />;
}

function LoadingDots() {
  return (
    <div className="flex items-center gap-1.5 py-2">
      <div className="w-3 h-3 border-2 border-[#e0703a] border-t-transparent rounded-full animate-spin" />
      <span className="text-xs text-[#84735f] dark:text-[#a08d74]">生成中...</span>
    </div>
  );
}


function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.7 ? '#7fa05c' : value >= 0.4 ? '#d9a441' : '#c84b33';
  return (
    <div className="flex items-center gap-1">
      <div className="w-8 h-1 bg-[#e7dcc9] rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[9px] text-[#84735f] dark:text-[#a08d74]">{value.toFixed(1)}</span>
    </div>
  );
}

function timeAgo(iso: string | null) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return Math.floor(diff / 60) + 'm';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h';
  return Math.floor(diff / 86400) + 'd';
}

// ============ MINDMAP (markmap) ============
function jsonToMarkdown(node: any, depth = 1): string {
  const prefix = '#'.repeat(Math.min(depth, 6));
  const text = (node.text || '').replace(/\n/g, ' ');
  let md = `${prefix} ${text}\n`;
  if (Array.isArray(node.children)) {
    for (const child of node.children) md += jsonToMarkdown(child, depth + 1);
  }
  return md;
}


// ============ XMIND-STYLE MIND MAP ============
const XM_COLORS = ['#e8504a','#f0883e','#f5c518','#4caf7d','#e0703a','#f0b34a','#ec4899','#06b6d4'];
const XM_LEVEL_GAP = [0, 80, 64, 52];  // horizontal gap between levels
const XM_NODE_H   = [48, 36, 28, 24];  // node height per depth
const XM_NODE_W   = [160,128,104, 88]; // node width per depth (approx, text may override)
const XM_GAP_Y    = [0,  20, 14, 10];  // vertical gap between siblings

interface XMNode {
  text: string; depth: number; side: 'root'|'left'|'right';
  color: string; branchIdx: number;
  x: number; y: number; w: number; h: number;
  children: XMNode[];
}

function xmNodeW(text: string, depth: number) {
  const base = Math.min(Math.max(text.length * (depth === 0 ? 8.5 : depth === 1 ? 7.5 : 6.5) + 28, XM_NODE_W[Math.min(depth,3)]), 220);
  return base;
}
function xmNodeH(depth: number) { return XM_NODE_H[Math.min(depth, 3)]; }
function xmGapY(depth: number) { return XM_GAP_Y[Math.min(depth, 3)]; }
function xmLevelGap(depth: number) { return XM_LEVEL_GAP[Math.min(depth, 3)]; }

// Measure subtree total height
function xmSubtreeH(node: any, depth: number): number {
  const nh = xmNodeH(depth);
  if (!node.children?.length) return nh;
  const gap = xmGapY(depth + 1);
  const childTotal = node.children.reduce((s: number, c: any) => s + xmSubtreeH(c, depth + 1), 0)
    + gap * (node.children.length - 1);
  return Math.max(nh, childTotal);
}

function xmLayout(
  node: any, depth: number, side: 'left'|'right'|'root',
  cx: number, cy: number, color: string, branchIdx: number
): XMNode {
  const w = xmNodeW(node.text || '', depth);
  const h = xmNodeH(depth);
  const x = side === 'left'  ? cx - w
           : side === 'right' ? cx
           : cx - w / 2;
  const y = cy - h / 2;

  const childGap = xmGapY(depth + 1);
  const children: XMNode[] = [];
  if (node.children?.length) {
    const totalH = node.children.reduce((s: number, c: any) => s + xmSubtreeH(c, depth + 1), 0)
      + childGap * (node.children.length - 1);
    let childY = cy - totalH / 2;
    const nextX = side === 'left'  ? cx - w - xmLevelGap(depth + 1)
                : side === 'right' ? cx + w + xmLevelGap(depth + 1)
                : cx;
    for (const child of node.children) {
      const sh = xmSubtreeH(child, depth + 1);
      children.push(xmLayout(child, depth + 1, side === 'root' ? 'right' : side, nextX, childY + sh / 2, color, branchIdx));
      childY += sh + childGap;
    }
  }
  return { text: node.text || '', depth, side, color, branchIdx, x, y, w, h, children };
}

function buildXMindLayout(data: any): XMNode {
  const children = data.children || [];
  const half = Math.ceil(children.length / 2);
  const rightKids = children.slice(0, half);
  const leftKids  = children.slice(half);

  // Measure sides
  const rootW = xmNodeW(data.text || '', 0);
  const rootH = xmNodeH(0);
  const origin = { x: 0, y: 0 };

  const layoutSide = (kids: any[], side: 'left'|'right', startColorIdx: number) => {
    const gap = xmGapY(1);
    const totalH = kids.reduce((s: any, c: any) => s + xmSubtreeH(c, 1), 0) + gap * (kids.length - 1);
    let cy = -totalH / 2;
    return kids.map((kid, i) => {
      const sh = xmSubtreeH(kid, 1);
      const color = XM_COLORS[(startColorIdx + i) % XM_COLORS.length];
      const cx = side === 'right' ? rootW / 2 + xmLevelGap(1) : -rootW / 2 - xmLevelGap(1);
      const node = xmLayout(kid, 1, side, cx, cy + sh / 2, color, startColorIdx + i);
      cy += sh + gap;
      return node;
    });
  };

  const rightNodes = layoutSide(rightKids, 'right', 0);
  const leftNodes  = layoutSide(leftKids,  'left',  rightKids.length);

  return {
    text: data.text || '', depth: 0, side: 'root',
    color: '#e0703a', branchIdx: -1,
    x: -rootW / 2, y: -rootH / 2, w: rootW, h: rootH,
    children: [...rightNodes, ...leftNodes],
  };
}

// SVG edge: organic bezier from parent connector point to child connector
function XMEdge({ parent, child }: { parent: XMNode; child: XMNode }) {
  const px = child.side === 'right' ? parent.x + parent.w : parent.x;
  const py = parent.y + parent.h / 2;
  const cx = child.side === 'right' ? child.x : child.x + child.w;
  const cy = child.y + child.h / 2;
  const mx = (px + cx) / 2;
  const strokeW = child.depth === 1 ? 2.5 : 1.5;
  return <path d={`M${px},${py} C${mx},${py} ${mx},${cy} ${cx},${cy}`}
    fill="none" stroke={child.color} strokeWidth={strokeW} opacity={child.depth === 1 ? 0.9 : 0.6} />;
}

// Single node rendering
function XMNodeEl({ node, all }: { node: XMNode; all: XMNode[] }) {
  const { x, y, w, h, depth, color, text, side, children } = node;
  const isRoot = depth === 0;
  const isL1   = depth === 1;
  const fontSize = isRoot ? 14 : isL1 ? 12.5 : 11.5;

  return (
    <>
      {/* Edges to children */}
      {children.map((child, i) => (
        <XMEdge key={i} parent={node} child={child} />
      ))}
      {/* Node shape */}
      <g>
        {isRoot ? (
          <>
            <defs>
              <linearGradient id="xm-root-g" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#e0703a" />
                <stop offset="100%" stopColor="#f0b34a" />
              </linearGradient>
            </defs>
            <rect x={x} y={y} width={w} height={h} rx={h/2}
              fill="url(#xm-root-g)" filter="url(#xm-shadow)" />
            <text x={x+w/2} y={y+h/2} textAnchor="middle" dominantBaseline="middle"
              fill="#fff" fontSize={fontSize} fontWeight={700} style={{ userSelect:'none' }}>
              {text.length > 20 ? text.slice(0,19)+'…' : text}
            </text>
          </>
        ) : isL1 ? (
          <>
            <rect x={x} y={y} width={w} height={h} rx={h/2}
              fill={color} opacity={0.92} />
            <text x={x+w/2} y={y+h/2} textAnchor="middle" dominantBaseline="middle"
              fill="#fff" fontSize={fontSize} fontWeight={600} style={{ userSelect:'none' }}>
              {text.length > 16 ? text.slice(0,15)+'…' : text}
            </text>
          </>
        ) : (
          <>
            <rect x={x} y={y} width={w} height={h} rx={4}
              fill="#fff" stroke={color} strokeWidth={1} opacity={0.15} />
            {/* Colored underline */}
            <line x1={x+6} y1={y+h-1} x2={x+w-6} y2={y+h-1} stroke={color} strokeWidth={2} />
            <text x={side==='right'?x+10:x+w-10} y={y+h/2}
              textAnchor={side==='right'?'start':'end'} dominantBaseline="middle"
              fill="#33291f" fontSize={fontSize} fontWeight={depth===2?500:400} style={{ userSelect:'none' }}>
              {text.length > 18 ? text.slice(0,17)+'…' : text}
            </text>
          </>
        )}
      </g>
      {/* Recurse */}
      {children.map((child, i) => <XMNodeEl key={i} node={child} all={all} />)}
    </>
  );
}

function getXMBounds(node: XMNode): { minX: number; minY: number; maxX: number; maxY: number } {
  let b = { minX: node.x, minY: node.y, maxX: node.x + node.w, maxY: node.y + node.h };
  for (const child of node.children) {
    const cb = getXMBounds(child);
    b = { minX: Math.min(b.minX, cb.minX), minY: Math.min(b.minY, cb.minY), maxX: Math.max(b.maxX, cb.maxX), maxY: Math.max(b.maxY, cb.maxY) };
  }
  return b;
}

function MindmapTree({ data }: { data: any; onUpdate?: (d: any) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const dragging = useRef(false);
  const lastPos  = useRef({ x: 0, y: 0 });

  const root = useMemo(() => buildXMindLayout(data), [data]);
  const bounds = useMemo(() => getXMBounds(root), [root]);
  const pad = 48;

  // Auto-fit — defer with rAF so container has real dimensions
  const fit = useRef<(() => void) | null>(null);
  fit.current = () => {
    const el = containerRef.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    if (width === 0 || height === 0) return;
    const bw = bounds.maxX - bounds.minX + pad * 2;
    const bh = bounds.maxY - bounds.minY + pad * 2;
    const scale = Math.min(width / bw, height / bh, 1);
    setTransform({
      x: width  / 2 - (bounds.minX + (bounds.maxX - bounds.minX) / 2) * scale,
      y: height / 2 - (bounds.minY + (bounds.maxY - bounds.minY) / 2) * scale,
      scale,
    });
  };
  useEffect(() => {
    const id = requestAnimationFrame(() => fit.current?.());
    return () => cancelAnimationFrame(id);
  }, [bounds]);

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    setTransform(t => ({ ...t, scale: Math.min(Math.max(t.scale * factor, 0.2), 3) }));
  };
  const onMouseDown = (e: React.MouseEvent) => { dragging.current = true; lastPos.current = { x: e.clientX, y: e.clientY }; };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragging.current) return;
    const dx = e.clientX - lastPos.current.x, dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setTransform(t => ({ ...t, x: t.x + dx, y: t.y + dy }));
  };
  const onMouseUp = () => { dragging.current = false; };

  return (
    <div ref={containerRef} style={{ width:'100%', height:'100%', overflow:'hidden', cursor:'grab', background:'#fafbfd' }}
      onWheel={onWheel} onMouseDown={onMouseDown} onMouseMove={onMouseMove}
      onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
      <svg width="100%" height="100%" style={{ display:'block' }}>
        <defs>
          <filter id="xm-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="#e0703a" floodOpacity="0.25" />
          </filter>
        </defs>
        <g transform={`translate(${transform.x},${transform.y}) scale(${transform.scale})`}>
          <XMNodeEl node={root} all={[root]} />
        </g>
      </svg>
    </div>
  );
}
