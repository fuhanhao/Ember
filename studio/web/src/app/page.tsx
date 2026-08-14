'use client';
import { useEffect, useState, useRef, useMemo } from 'react';
import { api } from '@/lib/api';
import Link from 'next/link';

interface Article {
  id: string; title: string; url: string; source_id: string;
  category: string; tags: string[]; importance_score: number;
  content_signal?: number; published_at: string | null; author?: string;
}
interface Stats { total: number; today: number; categories: Record<string, number>; }

const CAT: Record<string, string> = {
  paper:'论文', model_release:'模型发布', open_source:'开源项目', funding:'融资动态',
  product_launch:'产品发布', opinion:'观点洞察', industry_report:'行业报告', tutorial:'教程资源',
  policy:'政策法规', market_data:'市场数据', api_update:'API 更新', tool_review:'工具测评',
};
const CAT_EN: Record<string, string> = {
  paper:'论文', model_release:'模型发布', open_source:'开源项目', funding:'融资动态',
  product_launch:'产品发布', opinion:'观点洞察', industry_report:'行业报告',
  tutorial:'教程资源', policy:'政策法规', market_data:'市场数据',
  api_update:'API 更新', tool_review:'工具测评',
};

function timeAgo(iso: string | null) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
  return Math.floor(diff / 86400) + '天前';
}

function sinceDate(tab: string): string {
  const d = new Date();
  if (tab === 'weekly') d.setDate(d.getDate() - 7);
  else if (tab === 'monthly') d.setDate(d.getDate() - 30);
  else d.setHours(0,0,0,0);
  return d.toISOString().split('T')[0];
}

const S = {
  bg: '#17120e', navy: '#f3e9da', gray: '#a08d74', coral: '#e0703a',
  border: '#3a2e1f', card: '#211a13', accent: '#2b2218', green: '#7fa05c',
  text: '#e8dcc8',
  serif: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
  sans: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
};

export default function Page() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats|null>(null);
  const [insight, setInsight] = useState('');
  const [tab, setTab] = useState<'daily'|'weekly'|'monthly'>('daily');
  const [sideTab, setSideTab] = useState('aggregation');
  const [catFilter, setCatFilter] = useState<string|null>(null);
  const [search, setSearch] = useState('');
  const [articleCount, setArticleCount] = useState(0);
  const [allArticles, setAllArticles] = useState<Article[]>([]);
  const [hoveredArticle, setHoveredArticle] = useState<Article|null>(null);
  const [articleDetail, setArticleDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [briefing, setBriefing] = useState<any>(null);
  const [briefingLoading, setBriefingLoading] = useState(true);
  const [phaseIdx, setPhaseIdx] = useState(4);
  const [heroIdx, setHeroIdx] = useState(0);
  const [heroFade, setHeroFade] = useState(true);

  const [keywords, setKeywords] = useState<{keyword: string; score: number; count: number}[]>([]);
  const [activeKeyword, setActiveKeyword] = useState<string|null>(null);
  const [searchResults, setSearchResults] = useState<Article[]|null>(null);
  const catSectionRef = useRef<HTMLDivElement|null>(null);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summaryText, setSummaryText] = useState('');
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [bookmarkedIds, setBookmarkedIds] = useState<Set<string>>(new Set());
  const heatSectionRef = useRef<HTMLDivElement|null>(null);

  const PHASES = [
    { label: '规则系统', pct: 8, title: '规则与专家系统时代', desc: '基于人工编写的 if-else 规则和知识库，AI 只能处理预定义场景。代表：MYCIN 医疗诊断系统、国际象棋程序。', keywords: '专家系统 · 知识库 · 符号推理 · 决策树' },
    { label: '机器学习', pct: 24, title: '统计机器学习时代', desc: '从数据中自动学习模式，无需显式编程。SVM、随机森林、推荐系统开始大规模商用。', keywords: '监督学习 · 特征工程 · SVM · 随机森林' },
    { label: '深度学习', pct: 40, title: '深度学习革命', desc: 'CNN/RNN 突破图像和语音识别瓶颈，GPU 算力驱动模型规模跃升。AlphaGo 击败人类棋手。', keywords: 'CNN · RNN · GPU · AlphaGo · ImageNet' },
    { label: '基础大模型', pct: 56, title: '基础大模型涌现', desc: 'Transformer 架构统一 NLP/CV，GPT/BERT 开启预训练+微调范式，涌现出通用语言理解能力。', keywords: 'Transformer · GPT · BERT · 预训练 · 涌现' },
    { label: '智能体 AI', pct: 72, title: '智能体 AI 与基础大模型时代', desc: 'AI 正从单一模型推理走向多智能体协作，具身智能开始落地。基础模型能力持续突破，开源与闭源路线分化加剧。端侧推理与云端协同成为新战场。', keywords: '多智能体 · 具身智能 · 开闭源分化 · 端云协同' },
    { label: '通用智能', pct: 92, title: '通用人工智能（AGI）', desc: '尚未到达。目标：AI 具备跨领域的通用推理、自主学习和创造能力，达到或超越人类认知水平。', keywords: '跨领域推理 · 自主学习 · 意识 · 对齐问题' },
  ];
  const currentPhase = PHASES[phaseIdx];

  // Load all data (unfiltered) for heat/keywords/topstory
  const loadAll = async () => {
    try {
      // Fetch daily briefing for right panel
      api.getDailyBriefing().then(d => { setBriefing(d); setBriefingLoading(false); }).catch(() => setBriefingLoading(false));
      const [allData, statsData, insightData, kwData] = await Promise.all([
        api.getFeed({ limit: '50', page: '1', since: sinceDate(tab) }),
        api.getStats(),
        api.getDailyInsight().catch(() => ({ insight: '', article_count: 0 })),
        api.getKeywords({ hours: tab === 'daily' ? '24' : '168' }).catch(() => ({ keywords: [] })),
      ]);
      setAllArticles(allData.items || []);
      setStats(statsData);
      setInsight(insightData.insight || '');
      setKeywords(kwData.keywords || []);
    } catch {}
  };
  // Load filtered data for article grid
  const loadFiltered = async () => {
    try {
      const feedData = await api.getFeed({ limit: '50', page: '1', since: sinceDate(tab), ...(catFilter ? { category: catFilter } : {}), ...(activeKeyword ? { tag: activeKeyword } : {}) });
      setArticles(feedData.items || []);
      setArticleCount(feedData.total || 0);
    } catch {}
  };

  useEffect(() => { loadAll(); const t = setInterval(loadAll, 60000); return () => clearInterval(t); }, [tab]);
  useEffect(() => { loadFiltered(); }, [tab, catFilter, activeKeyword]);

  // These use allArticles (unfiltered) - stable regardless of category filter
  const topStories = useMemo(() => [...allArticles].filter(a => a.importance_score >= 0.5).slice(0, 8), [allArticles]);
  const hero = topStories[heroIdx % Math.max(topStories.length, 1)] || allArticles[0];
  const topHeat = useMemo(() => [...allArticles].sort((a,b) => b.importance_score - a.importance_score).slice(0, 6), [allArticles]);
  const topKeywords = useMemo(() => {
    if (keywords.length) return keywords.map(k => [k.keyword, k.count] as [string, number]);
    const kw: Record<string, number> = {};
    allArticles.forEach(a => a.tags?.forEach(t => { kw[t] = (kw[t] || 0) + 1; }));
    return Object.entries(kw).sort((a,b) => b[1] - a[1]).slice(0, 20) as [string, number][];
  }, [keywords, allArticles]);
  // These use articles (filtered by category)
  const gridArticles = useMemo(() => searchResults || articles.slice(0, 49), [searchResults, articles]);
  const cats = useMemo(() => stats ? Object.entries(stats.categories).sort((a,b) => b[1] - a[1]) : [], [stats]);

  const generateSummary = async () => {
    setSummaryOpen(true); setSummaryLoading(true); setSummaryText('');
    const topCat = cats[0]?.[0];
    if (!topCat) { setSummaryText('暂无文章可总结'); setSummaryLoading(false); return; }
    try {
      const data = await api.getFeed({ limit: '50', category: topCat, since: sinceDate(tab) });
      const titles = (data.items || []).slice(0, 30).map((a: any) => a.title);
      const resp = await api.generateCategorySummary({ category: topCat, article_titles: titles, article_snippets: [] });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: '生成失败，请稍后重试' }));
        throw new Error(err.detail || '生成失败，请稍后重试');
      }
      const reader = resp.body?.getReader();
      if (!reader) throw new Error('无法读取生成结果');
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        decoder.decode(value, { stream: true }).split('\n').forEach(line => {
          if (line.startsWith('data: ')) {
            try {
              const payload = JSON.parse(line.slice(6));
              if (payload.text) setSummaryText(prev => prev + payload.text);
            } catch {}
          }
        });
      }
    } catch (e: any) {
      setSummaryText(e?.message || '生成失败，请稍后重试');
    }
    setSummaryLoading(false);
  };

  const toggleBookmark = async (id: string) => {
    if (bookmarkedIds.has(id)) {
      await api.removeBookmark(id).catch(() => {});
      setBookmarkedIds(prev => { const n = new Set(prev); n.delete(id); return n; });
    } else {
      await api.addBookmark(id).catch(() => {});
      setBookmarkedIds(prev => new Set(prev).add(id));
    }
  };

  return (
    <div style={{ background: S.bg, minHeight: '100vh', fontFamily: S.sans, color: S.navy, display: 'flex' }}>
      {/* ===== LEFT NAV (Column 1) ===== */}
      <aside style={{ width: 170, minHeight: '100vh', borderRight: `1px solid ${S.border}`, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', flexShrink: 0 }}>
        {/* Logo */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 20px', borderBottom: `1px solid ${S.border}` }}>
            <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="9" fill="url(#emberg)"/>
              <path d="M16 4c2 5 7 8.4 7 13.8a7 7 0 1 1-14 0c0-2.5 1.2-4.7 2.8-6.6.3 1.6 1 3 2.2 4-.3-4 1-8.8 2-11.2z" fill="#fff" fillOpacity="0.95"/>
              <circle cx="23.5" cy="9.5" r="1.5" fill="#f0b34a"/>
              <defs><linearGradient id="emberg" x1="6" y1="4" x2="26" y2="26"><stop stopColor="#e0703a"/><stop offset="1" stopColor="#f0b34a"/></linearGradient></defs>
            </svg>
            <span style={{ fontFamily: S.serif, fontWeight: 800, fontSize: 17, letterSpacing: 3 }}>Ember</span>
          </div>
          {/* Nav items */}
          <div style={{ paddingTop: 8 }}>
            {[
              { key: 'aggregation', label: '信息聚合' },
              { key: 'processing', label: '信息处理' },
              { key: 'knowledge', label: '知识库' },
              { key: 'api', label: '各类接口' },
            ].map(item => (
<button key={item.key} onClick={() => { if (item.key === 'knowledge') { window.location.href = '/knowledge'; } else { setSideTab(item.key as any); } }} style={{
                display: 'block', width: '100%', padding: '11px 20px',
                background: sideTab === item.key ? '#2b2218' : 'transparent',
                color: S.navy,
                border: 'none', borderLeft: sideTab === item.key ? `3px solid ${S.navy}` : '3px solid transparent',
                cursor: 'pointer', fontSize: 15, fontWeight: sideTab === item.key ? 800 : 400,
                fontFamily: S.sans, textAlign: 'left', letterSpacing: '0.03em',
              }}>
                {item.label}
              </button>
            ))}
          </div>
        </div>{/* end top section */}
        <div style={{ padding: '0 16px' }}>
          <button onClick={generateSummary} style={{
            width: '100%', padding: '10px 0', background: S.coral, color: '#fff', border: 'none',
            borderRadius: 10, fontSize: 12, fontWeight: 700, cursor: 'pointer', marginBottom: 16, letterSpacing: '0.05em',
          }}>一键生成摘要</button>
          <Link href="/settings" style={{ color: S.gray, fontSize: 12, cursor: 'pointer', textAlign: 'center', display: 'block', textDecoration: 'none' }}>设置</Link>
        </div>
      </aside>

      {/* ===== RIGHT SECTION (Column 2+3): Header + Content ===== */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        {/* Header - only show for aggregation */}
        {sideTab === 'aggregation' && (
          <header style={{ background: S.bg, borderBottom: `1px solid ${S.border}`, display: 'flex', alignItems: 'center', padding: '10px 32px', height: 52, flexShrink: 0 }}>
            <nav style={{ display: 'flex', gap: 28, flex: 1 }}>
              {(['daily','weekly','monthly'] as const).map(t => (
                <button key={t} onClick={() => setTab(t)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', fontFamily: S.sans,
                  fontSize: 14, fontWeight: tab === t ? 600 : 400, color: S.navy, padding: '4px 0',
                  borderBottom: tab === t ? `2px solid ${S.navy}` : '2px solid transparent',
                }}>{t === 'daily' ? '今日' : t === 'weekly' ? '本周' : '本月'}</button>
              ))}
              <button onClick={() => catSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: S.gray, fontWeight: 400 }}>分类</button>
            </nav>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ position: 'relative' }}>
                <input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={async (e) => { if (e.key === 'Enter' && search.trim()) { try { const data = await api.search({ q: search.trim(), limit: '100' }); setSearchResults(data.items || []); } catch { setSearchResults([]); } } else if (e.key === 'Escape') { setSearchResults(null); setSearch(''); } }} placeholder="搜索文章..." style={{
                  padding: '7px 14px 7px 34px', border: `1px solid ${S.border}`, borderRadius: 10, fontSize: 13,
                  background: '#211a13', width: 190, outline: 'none', fontFamily: S.sans, color: S.navy,
                }}/>
                <svg style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)' }} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6e5f4b" strokeWidth="2.5"><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/></svg>
              </div>
               <div onClick={() => { window.location.href = '/settings'; }} title="设置" style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={S.navy} strokeWidth="2.2" strokeLinecap="square" strokeLinejoin="miter"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><rect x="8" y="3" width="8" height="8"/></svg>
              </div>
            </div>
          </header>
        )}

        {/* Content area - fills remaining height */}
        {sideTab === 'processing' ? (
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <iframe src="/workspace" style={{ width: '100%', height: '100%', border: 'none', display: 'block' }} />
          </div>
        ) : sideTab === 'knowledge' ? (
          <div style={{ flex: 1, padding: '60px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: S.gray }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>📚</div>
              <div style={{ fontFamily: S.serif, fontSize: 24, fontWeight: 700, color: S.navy, marginBottom: 8 }}>知识库</div>
              <div style={{ fontSize: 14 }}>管理和检索您的 AI 知识资产，即将上线</div>
            </div>
          </div>
        ) : sideTab === 'api' ? (
          <div style={{ flex: 1, padding: '60px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: S.gray }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🔌</div>
              <div style={{ fontFamily: S.serif, fontSize: 24, fontWeight: 700, color: S.navy, marginBottom: 8 }}>各类接口</div>
              <div style={{ fontSize: 14 }}>API 管理与数据对接配置，即将上线</div>
            </div>
          </div>
        ) : (
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <main style={{ flex: 1, padding: '32px 40px', overflow: 'auto' }}>

          {/* spacer */}
          <div style={{ marginBottom: 8 }} />

          {/* ===== AI Development Pulse ===== */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 28, marginBottom: 48, alignItems: 'stretch' }}>
            {/* LEFT COLUMN - single flex column */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>

              {/* AI 发展历程 */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <span style={{ fontFamily: S.serif, fontSize: 24, fontWeight: 700, color: S.navy }}>AI 发展历程</span>
                <span style={{ fontSize: 10, color: S.gray }}>更新于 {new Date().toLocaleDateString('zh-CN')}</span>
              </div>
              <div style={{ position: 'relative', marginBottom: 12, marginTop: 8, cursor: 'pointer' }}
                onClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  const pct = ((e.clientX - rect.left) / rect.width) * 100;
                  const closest = PHASES.reduce((prev, curr, idx) => Math.abs(curr.pct - pct) < Math.abs(PHASES[prev].pct - pct) ? idx : prev, 0);
                  setPhaseIdx(closest);
                }}>
                <div style={{ height: 10, background: S.border, position: 'relative' }}>
                  <div style={{ height: '100%', width: `${currentPhase.pct}%`, background: `linear-gradient(90deg, #e0703a 0%, #f0b34a 100%)`, transition: 'width 0.3s' }}/>
                  <div style={{ position: 'absolute', top: -6, left: `${currentPhase.pct}%`, width: 22, height: 22, background: S.coral, borderRadius: 8, border: '3px solid #fff', boxShadow: '0 0 0 1.5px ' + S.coral, transform: 'translateX(-50%)', transition: 'left 0.3s', cursor: 'grab' }}/>
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, letterSpacing: '0.05em', fontWeight: 600, marginBottom: 24 }}>
                {PHASES.map((p, i) => (
                  <span key={p.label} onClick={() => setPhaseIdx(i)} style={{ cursor: 'pointer', transition: 'color 0.2s', color: i === phaseIdx ? S.coral : i < phaseIdx ? S.navy : '#4a3b28', fontWeight: i === phaseIdx ? 800 : 600 }}>{p.label}</span>
                ))}
              </div>
              <div style={{ background: S.accent, borderRadius: 10, padding: '24px 28px', marginBottom: 24, color: '#fff', transition: 'all 0.3s' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                  <span style={{ background: phaseIdx === 4 ? S.coral : '#6e5f4b', color: '#fff', padding: '4px 12px', borderRadius: 10, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em' }}>{phaseIdx === 4 ? '当前阶段' : phaseIdx < 4 ? '已过去' : '未来'}</span>
                  <span style={{ fontFamily: S.serif, fontSize: 20, fontWeight: 700 }}>{currentPhase.title}</span>
                </div>
                <p style={{ fontSize: 14, opacity: 0.85, lineHeight: 1.7, margin: '0 0 16px' }}>{currentPhase.desc}</p>
                <div style={{ fontSize: 12, opacity: 0.6 }}>关键词: {currentPhase.keywords}</div>
              </div>

              {/* AI 今日关键词 */}
              <div style={{ marginBottom: 28 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: S.gray }}>AI 今日关键词</span>
                  <span style={{ fontSize: 10, color: S.gray }}>({stats?.today || 0} articles)</span>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {topKeywords.map(([kw, cnt], i) => {
                    const maxCnt = topKeywords[0]?.[1] || 1;
                    const intensity = Math.max(0.15, (cnt as number) / (maxCnt as number));
                    return (
                       <div key={kw} onClick={() => { setActiveKeyword(activeKeyword === kw ? null : kw); setCatFilter(null); }} style={{
                        padding: '6px 12px', borderRadius: 10, cursor: 'pointer',
                        background: i < 3 ? S.coral : `rgba(224,112,58,${intensity})`,
                        color: i < 3 || intensity > 0.4 ? '#fff' : S.navy,
                        fontSize: 12, fontWeight: 600, letterSpacing: '0.02em',
                        transition: 'all 0.15s',
                        outline: activeKeyword === kw ? `2px solid ${S.navy}` : 'none',
                      }}>
                        {kw} {cnt as number}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* TOP STORY */}
              {hero && (
                <div style={{ borderTop: `1px solid ${S.border}`, paddingTop: 28 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                    <span style={{ fontSize: 11, letterSpacing: '0.12em', fontWeight: 700, color: S.gray }}>TOP STORY</span>
                    <span style={{ background: S.accent, color: '#fff', padding: '2px 8px', borderRadius: 10, fontSize: 9, fontWeight: 700 }}>{CAT_EN[hero.category] || hero.category}</span>
                    <span style={{ fontSize: 11, color: S.gray }}>{timeAgo(hero.published_at)}</span>
                    <span style={{ fontSize: 10, color: S.gray, marginLeft: 'auto' }}>{hero.source_id.replace(/^[GC]-/, '').replace(/-/g, ' ')}</span>
                  </div>
                  <h2 style={{ fontFamily: S.serif, fontSize: 32, fontWeight: 700, lineHeight: 1.2, margin: '0 0 20px', minHeight: '2.4em', display: 'flex', alignItems: 'center' }}>{hero.title}</h2>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
                    {hero.tags?.slice(0, 5).map(tag => (
                      <span key={tag} style={{ fontSize: 13, color: S.coral, border: `1px solid ${S.coral}33`, padding: '4px 12px', borderRadius: 10 }}>{tag}</span>
                    ))}
                    <span style={{ fontSize: 13, color: S.gray, marginLeft: 8 }}>Heat: {(hero.importance_score * 10).toFixed(1)}/10</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <a href={hero.url} target="_blank" rel="noopener noreferrer" style={{ padding: '10px 24px', background: S.coral, color: '#fff', borderRadius: 10, fontSize: 14, fontWeight: 700, textDecoration: 'none' }}>阅读原文 →</a>
                    <button onClick={generateSummary} style={{ padding: '10px 18px', border: `1.5px solid ${S.navy}`, borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer', color: S.navy, background: 'transparent' }}>AI 摘要</button>
                    <button onClick={() => { window.location.href = '/workspace'; }} style={{ padding: '10px 18px', border: `1.5px solid ${S.border}`, borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer', color: S.gray, background: 'transparent' }}>+ 工作台</button>
                    <button onClick={() => toggleBookmark(hero.id)} style={{ padding: '10px 18px', border: `1.5px solid ${S.border}`, borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer', color: bookmarkedIds.has(hero.id) ? S.coral : S.gray, background: 'transparent' }}>{bookmarkedIds.has(hero.id) ? '✓ 已收藏' : '收藏'}</button>
                  </div>
                </div>
              )}

              {/* Pager - pushed to bottom via marginTop auto */}
              <div style={{ marginTop: 'auto', paddingTop: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button onClick={() => setHeroIdx(prev => (prev - 1 + topStories.length) % topStories.length)} style={{ width: 28, height: 28, borderRadius: 12, border: `1px solid ${S.border}`, background: 'transparent', cursor: 'pointer', fontSize: 14, color: S.navy, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>&#8249;</button>
                  <span style={{ fontSize: 11, color: S.gray }}>{heroIdx + 1} / {topStories.length}</span>
                  <button onClick={() => setHeroIdx(prev => (prev + 1) % topStories.length)} style={{ width: 28, height: 28, borderRadius: 12, border: `1px solid ${S.border}`, background: 'transparent', cursor: 'pointer', fontSize: 14, color: S.navy, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>&#8250;</button>
                </div>
              </div>
            </div>

            {/* Right Column: Heat Score + Insight - sticky */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* 热度排行 */}
              <div ref={heatSectionRef} style={{ background: S.card, border: `1px solid ${S.border}`, borderRadius: 12, padding: 20, scrollMarginTop: 20 }}>
                <h3 style={{ fontFamily: S.serif, fontStyle: 'italic', fontSize: 16, margin: '0 0 16px', fontWeight: 600 }}>热度排行</h3>
                {topHeat.map((a, i) => (
                  <a key={a.id} href={a.url} target="_blank" rel="noopener noreferrer" style={{ display: 'flex', gap: 10, marginBottom: 14, textDecoration: 'none', color: S.navy, alignItems: 'flex-start' }}>
                    <span style={{ fontFamily: S.serif, fontSize: 20, fontWeight: 700, color: S.coral, lineHeight: 1, minWidth: 24 }}>
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.3, marginBottom: 2 }}>{a.title.length > 50 ? a.title.slice(0, 50) + '...' : a.title}</div>
                      <div style={{ fontSize: 11, color: S.gray }}>热度: {(a.importance_score * 10).toFixed(1)}/10</div>
                    </div>
                  </a>
                ))}
              </div>

              {/* AI 每日洞察 */}
              {insight && (
                <div style={{ background: S.coral, borderRadius: 12, padding: 20, color: '#fff', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: 18, marginBottom: 6 }}>✦</div>
                  <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8, letterSpacing: '0.08em' }}>AI 每日洞察</div>
                  <p style={{ fontFamily: S.serif, fontStyle: 'italic', fontSize: 13, lineHeight: 1.55, margin: '0 0 14px', opacity: 0.95 }}>
                    &ldquo;{insight}&rdquo;
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 10, opacity: 0.7 }}>基于 {stats?.today || 0} 篇文章分析</span>
                    <span onClick={generateSummary} style={{ fontSize: 11, fontWeight: 600, cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.5)', paddingBottom: 1 }}>展开分析 →</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ===== 分类浏览 ===== */}
          <div ref={catSectionRef} style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', scrollMarginTop: 20 }}>
            <h2 style={{ fontFamily: S.serif, fontSize: 24, fontWeight: 700, margin: 0 }}>分类浏览</h2>
            <button onClick={() => setCatFilter(null)} style={{
              padding: '6px 18px', borderRadius: 12, fontSize: 12, fontWeight: 600, cursor: 'pointer', border: '1px solid',
              background: !catFilter ? S.green : 'transparent', color: !catFilter ? '#fff' : S.navy,
              borderColor: !catFilter ? S.green : S.border,
            }}>全部</button>
            {cats.map(([key]) => (
              <button key={key} onClick={() => setCatFilter(catFilter === key ? null : key)} style={{
                padding: '6px 18px', borderRadius: 12, fontSize: 12, fontWeight: 600, cursor: 'pointer', border: '1px solid',
                background: catFilter === key ? S.green : 'transparent', color: catFilter === key ? '#fff' : S.navy,
                borderColor: catFilter === key ? S.green : S.border,
              }}>{CAT[key] || key}</button>
            ))}
          </div>

          <div style={{ fontSize: 12, color: S.gray, marginBottom: 20 }}>
            {searchResults ? `搜索 “${search}” 共 ${searchResults.length} 条结果（按 Esc 清除）` : `${articleCount} 篇文章 · ${tab === 'daily' ? '今日' : tab === 'weekly' ? '本周' : '本月'}`}
          </div>

          {/* Article Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20, marginBottom: 60 }}>
            {gridArticles.map((a, i) => {
              // Every 3rd card = dark featured
              const isDark = i % 5 === 2;
              // Every 5th card = wide
              const isWide = i % 7 === 4;
              return (
                <a key={a.id} href={a.url} target="_blank" rel="noopener noreferrer"
                  onClick={(e) => { e.preventDefault(); setHoveredArticle(a); setDetailLoading(true); setArticleDetail(null);
                    api.getArticle(a.id).then(d => { setArticleDetail(d); setDetailLoading(false); }).catch(() => setDetailLoading(false));
                  }}
                  style={{
                  background: isDark ? S.accent : S.card,
                  border: isDark ? 'none' : `1px solid ${S.border}`,
                  borderRadius: 12, padding: isDark ? 0 : 20, overflow: 'hidden',
                  textDecoration: 'none', color: isDark ? '#fff' : S.navy,
                  gridColumn: isWide ? 'span 2' : 'span 1',
                  display: 'flex', flexDirection: isWide ? 'row' : 'column',
                  transition: 'box-shadow 0.2s', cursor: 'pointer',
                  minHeight: isDark ? 200 : 'auto',
                }}>
                  {isDark ? (
                    // Dark card with gradient bg
                    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', flex: 1,
                      background: 'linear-gradient(135deg, #241a11 0%, #1b130c 55%, #17120e 100%)',
                    }}>
                      <span style={{ fontSize: 10, letterSpacing: '0.1em', opacity: 0.7, marginBottom: 8, textTransform: 'uppercase', fontWeight: 600 }}>
                        {CAT_EN[a.category] || a.category}
                      </span>
                      <div style={{ fontFamily: S.serif, fontSize: 18, fontWeight: 700, lineHeight: 1.3, marginBottom: 12 }}>
                        {a.title.length > 60 ? a.title.slice(0, 60) + '...' : a.title}
                      </div>
                      <span style={{ fontSize: 11, padding: '4px 12px', border: '1px solid rgba(255,255,255,0.4)', borderRadius: 12, alignSelf: 'flex-start' }}>
                        探索 →
                      </span>
                    </div>
                  ) : isWide ? (
                    // Wide horizontal card
                    <>
                      <div style={{ width: 200, flexShrink: 0, background: 'linear-gradient(135deg, #241a11, #33261a)', minHeight: 180 }}/>
                      <div style={{ padding: 20, flex: 1 }}>
                        <span style={{ fontSize: 10, letterSpacing: '0.1em', color: S.gray, fontWeight: 600, textTransform: 'uppercase' }}>
                          {CAT_EN[a.category] || a.category}
                        </span>
                        <div style={{ fontFamily: S.serif, fontSize: 20, fontWeight: 700, lineHeight: 1.3, margin: '8px 0 10px' }}>
                          {a.title.length > 70 ? a.title.slice(0, 70) + '...' : a.title}
                        </div>
                        <p style={{ fontSize: 13, color: S.gray, lineHeight: 1.5, marginBottom: 16 }}>
                          {a.title.slice(0, 80)}...
                        </p>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <span style={{ padding: '6px 14px', background: S.coral, color: '#fff', borderRadius: 12, fontSize: 12, fontWeight: 600 }}>深度分析</span>
                          <span style={{ fontSize: 10, color: S.gray, letterSpacing: '0.1em' }}>精选内容</span>
                        </div>
                      </div>
                    </>
                  ) : (
                    // Standard card
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <span style={{ fontSize: 10, letterSpacing: '0.1em', color: S.gray, fontWeight: 600, textTransform: 'uppercase' }}>
                          {CAT_EN[a.category] || a.category}
                        </span>
                        <span onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleBookmark(a.id); }} title={bookmarkedIds.has(a.id) ? '取消收藏' : '收藏'} style={{ cursor: 'pointer', fontSize: 14, opacity: bookmarkedIds.has(a.id) ? 1 : 0.4, color: bookmarkedIds.has(a.id) ? S.coral : 'inherit' }}>🔖</span>
                      </div>
                      <div style={{ fontFamily: S.serif, fontSize: 17, fontWeight: 700, lineHeight: 1.3, marginBottom: 10, flex: 1 }}>
                        {a.title.length > 55 ? a.title.slice(0, 55) + '...' : a.title}
                      </div>
                      <p style={{ fontSize: 12, color: S.gray, lineHeight: 1.5, marginBottom: 16 }}>
                        {a.tags?.slice(0, 3).join(' · ') || CAT[a.category] || ''}
                      </p>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
                        <span style={{ fontSize: 11, color: S.gray }}>阅读: {Math.max(3, Math.floor(a.importance_score * 15))} 分钟</span>
                        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.05em' }}>深入阅读 →</span>
                      </div>
                    </>
                  )}
                </a>
              );
            })}
          </div>

          {/* ===== FOOTER ===== */}
          <footer style={{ borderTop: `1px solid ${S.border}`, padding: '40px 0 24px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr 1fr', gap: 32, marginBottom: 32 }}>
              <div>
                <h3 style={{ fontFamily: S.serif, fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Ember 智能情报</h3>
                <p style={{ fontSize: 12, color: S.gray, lineHeight: 1.6 }}>
                  利用前沿 AI 技术，从全球信息流中提炼出权威、可读的智能时代编年史。
                </p>
                <div style={{ marginTop: 12, fontSize: 12 }}>
                  <span>已验证数据源: <b>{stats?.total || 0}</b></span>
                  <span style={{ marginLeft: 16, color: S.coral, fontWeight: 700 }}>活跃采集器: 37</span>
                </div>
              </div>
              {[
                { title: '情报中心', items: [{ label: '每日速递', href: '/briefing', heat: false }, { label: '全球热力图', href: '/', heat: true }, { label: '采集日志', href: '/', heat: false }] },
                { title: '编辑精选', items: [{ label: '深度长文', href: '/workspace', heat: false }, { label: '行业访谈', href: '/workspace', heat: false }, { label: '伦理审计', href: '/workspace', heat: false }] },
                { title: '支持', items: [{ label: '隐私政策', href: '/settings', heat: false }, { label: '使用条款', href: '/settings', heat: false }, { label: '联系我们', href: '/settings', heat: false }] },
              ].map(col => (
                <div key={col.title}>
                  <h4 style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: S.navy, marginBottom: 12 }}>{col.title}</h4>
                  {col.items.map(item => (
                    item.heat ? (
                      <span key={item.label} onClick={() => heatSectionRef.current?.scrollIntoView({ behavior: 'smooth' })} style={{ fontSize: 13, color: S.gray, marginBottom: 8, cursor: 'pointer', display: 'block' }}>{item.label}</span>
                    ) : (
                      <Link key={item.label} href={item.href} style={{ fontSize: 13, color: S.gray, marginBottom: 8, display: 'block', textDecoration: 'none' }}>{item.label}</Link>
                    )
                  ))}
                </div>
              ))}
            </div>
            <div style={{ borderTop: `1px solid ${S.border}`, paddingTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: S.gray, letterSpacing: '0.05em' }}>© 2026 Ember 智能情报 版权所有</span>
              <div style={{ display: 'flex', gap: 12, fontSize: 16 }}>
                <span>📡</span>
                <span>✉️</span>
                <span>🎙️</span>
              </div>
            </div>
          </footer>
          {summaryOpen && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setSummaryOpen(false)}>
              <div onClick={e => e.stopPropagation()} style={{ width: 560, maxWidth: '92vw', maxHeight: '80vh', overflow: 'auto', background: S.card, border: `1px solid ${S.border}`, borderRadius: 16, padding: 28 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <span style={{ fontFamily: S.serif, fontSize: 18, fontWeight: 700 }}>分类摘要生成</span>
                  <button onClick={() => setSummaryOpen(false)} style={{ background: 'none', border: 'none', color: S.gray, fontSize: 18, cursor: 'pointer' }}>×</button>
                </div>
                {summaryLoading ? <div style={{ color: S.gray, fontSize: 13 }}>正在生成（需要 LLM API Key）...</div> : (
                  <div style={{ fontSize: 14, lineHeight: 1.9, whiteSpace: 'pre-wrap', color: S.text }}>{summaryText || '暂无内容'}</div>
                )}
              </div>
            </div>
          )}
        </main>
        {/* Right preview panel - editorial style */}
        <div style={{ width: 380, borderLeft: `1px solid ${S.border}`, background: S.bg, flexShrink: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {hoveredArticle ? (
            <div style={{ height: '100%', overflow: 'auto' }}>
              {/* Article header */}
              <div style={{ padding: '24px 24px 0', borderBottom: `1px solid ${S.border}`, paddingBottom: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                  <span style={{ background: S.coral, color: '#fff', padding: '3px 10px', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em' }}>{CAT[hoveredArticle.category] || hoveredArticle.category}</span>
                  <span style={{ fontSize: 10, color: S.gray, letterSpacing: '0.05em' }}>{hoveredArticle.source_id.replace(/^[GC]-/, '').replace(/-/g, ' ')}</span>
                </div>
                <h3 style={{ fontFamily: S.serif, fontSize: 20, fontWeight: 700, lineHeight: 1.35, margin: '0 0 12px', color: S.navy }}>{hoveredArticle.title}</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: S.gray }}>
                  {hoveredArticle.published_at && <span>{new Date(hoveredArticle.published_at).toLocaleString('zh-CN')}</span>}
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ display: 'inline-block', width: 40, height: 4, background: S.border, borderRadius: 10, overflow: 'hidden' }}>
                      <span style={{ display: 'block', height: '100%', width: `${hoveredArticle.importance_score * 100}%`, background: hoveredArticle.importance_score >= 0.7 ? S.coral : S.gray, borderRadius: 10 }} />
                    </span>
                    <span>{(hoveredArticle.importance_score * 10).toFixed(1)}</span>
                  </span>
                </div>
              </div>
              {/* Tags */}
              {hoveredArticle.tags?.length > 0 && (
                <div style={{ padding: '14px 24px', borderBottom: `1px solid ${S.border}`, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {hoveredArticle.tags.slice(0, 6).map(tag => (
                    <span key={tag} style={{ fontSize: 11, color: S.navy, border: `1px solid ${S.border}`, padding: '3px 10px', fontWeight: 500, letterSpacing: '0.02em' }}>{tag}</span>
                  ))}
                </div>
              )}
              {/* Content */}
              <div style={{ padding: '20px 24px 32px' }}>
                {detailLoading ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {[...Array(6)].map((_, i) => (
                      <div key={i} style={{ height: 14, background: S.border, borderRadius: 10, width: i === 5 ? '60%' : '100%', opacity: 0.5 }} />
                    ))}
                  </div>
                ) : articleDetail?.content ? (
                  <div style={{ fontFamily: S.sans, fontSize: 14, color: S.text, lineHeight: 2 }}>
                    {articleDetail.content.split('\n').filter((l: string) => l.trim().length > 0).slice(0, 50).map((p: string, i: number) => (
                      <p key={i} style={{ margin: '0 0 16px', textAlign: 'justify' }}>{p.trim()}</p>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: S.gray, fontSize: 13, fontStyle: 'italic' }}>暂无正文内容</div>
                )}
              </div>
              {/* Bottom action bar */}
              <div style={{ padding: '16px 24px', borderTop: `1px solid ${S.border}`, background: S.card, display: 'flex', gap: 10, position: 'sticky', bottom: 0 }}>
                <a href={hoveredArticle.url} target="_blank" rel="noopener noreferrer" style={{ flex: 1, padding: '10px 0', background: S.coral, color: '#fff', fontSize: 12, fontWeight: 700, textDecoration: 'none', textAlign: 'center', letterSpacing: '0.05em' }}>阅读原文 →</a>
                <button onClick={() => toggleBookmark(hoveredArticle.id)} style={{ padding: '10px 16px', border: `1.5px solid ${S.border}`, background: 'transparent', fontSize: 12, fontWeight: 600, cursor: 'pointer', color: bookmarkedIds.has(hoveredArticle.id) ? S.coral : S.navy }}>{bookmarkedIds.has(hoveredArticle.id) ? '✓ 已收藏' : '+ 收藏'}</button>
              </div>
            </div>
          ) : (
            <div style={{ height: '100%', overflow: 'auto' }}>
              {/* Daily Briefing Header */}
              <div style={{ padding: '20px 24px 16px', borderBottom: `1px solid ${S.border}` }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontFamily: S.serif, fontSize: 18, fontWeight: 700, color: S.navy }}>AI 昨日日报</div>
                    <div style={{ fontSize: 11, color: S.gray, marginTop: 2 }}>{briefing?.date || ''}</div>
                  </div>
                  {briefing?.total_articles && <div style={{ fontSize: 11, color: S.gray }}>共 {briefing.total_articles} 篇</div>}
                </div>
              </div>

              {briefingLoading ? (
                <div style={{ padding: '24px' }}>
                  {[...Array(4)].map((_, i) => (
                    <div key={i} style={{ marginBottom: 20 }}>
                      <div style={{ height: 14, background: S.border, borderRadius: 10, width: '40%', marginBottom: 8, opacity: 0.5 }} />
                      <div style={{ height: 12, background: S.border, borderRadius: 10, width: '100%', marginBottom: 4, opacity: 0.3 }} />
                      <div style={{ height: 12, background: S.border, borderRadius: 10, width: '80%', opacity: 0.3 }} />
                    </div>
                  ))}
                </div>
              ) : briefing?.sections?.length > 0 ? (
                <div style={{ padding: '0 24px 24px' }}>
                  {briefing.summary && (
                    <div style={{ margin: '16px 0', background: S.accent, borderRadius: 10, padding: '16px 20px', color: '#fff' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', marginBottom: 6, opacity: 0.7 }}>综合判断</div>
                      <p style={{ fontFamily: S.serif, fontStyle: 'italic', fontSize: 13, lineHeight: 1.6, margin: 0 }}>&ldquo;{briefing.summary}&rdquo;</p>
                    </div>
                  )}
                  {briefing.sections.map((sec: any, i: number) => (
                    <div key={i} style={{ padding: '16px 0', borderBottom: i < briefing.sections.length - 1 ? `1px solid ${S.border}` : 'none' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <span style={{ fontFamily: S.serif, fontSize: 16, fontWeight: 700, color: i < 3 ? S.coral : S.navy, lineHeight: 1, minWidth: 24 }}>{String(i + 1).padStart(2, '0')}</span>
                        <span style={{ fontSize: 14, fontWeight: 700, color: S.navy }}>{sec.title || sec.category}</span>
                        {sec.article_count && <span style={{ fontSize: 10, color: S.gray }}>{sec.article_count}篇</span>}
                      </div>
                      <p style={{ fontSize: 13, color: S.gray, lineHeight: 1.8, margin: '0 0 0 32px' }}>{sec.content}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ padding: 24, color: S.gray, fontSize: 13 }}>暂无昨日日报数据</div>
              )}
            </div>
          )}
        </div>

        </div>
        )}
      </div>
    </div>
  );
}
