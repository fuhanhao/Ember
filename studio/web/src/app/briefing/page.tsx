'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

interface Article {
  id: string; title: string; url: string; source_id: string;
  category: string; tags: string[]; importance_score: number;
  published_at: string | null;
}

interface DigestGroup {
  category: string; label: string; icon: string;
  total: number; top_importance: number; preview: Article[];
}

function timeAgo(iso: string | null) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return Math.floor(diff / 60) + 'm';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h';
  return Math.floor(diff / 86400) + 'd';
}

export default function BriefingPage() {
  const [groups, setGroups] = useState<DigestGroup[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getDigest().then(data => setGroups(data.groups || [])).catch(() => {});
  }, []);

  const expand = async (cat: string) => {
    if (expanded === cat) { setExpanded(null); return; }
    setExpanded(cat);
    setLoading(true);
    try {
      const data = await api.getFeed({ limit: '30', category: cat });
      setArticles(data.items || []);
    } catch {}
    setLoading(false);
  };

  const total = groups.reduce((s, g) => s + g.total, 0);

  return (
    <div className="flex h-screen flex-col bg-canvas">
      <header className="flex items-center gap-4 px-8 pb-4 pt-8">
        <Link href="/" className="text-[13px] text-muted hover:text-ink hover:underline">← 返回</Link>
        <div>
          <h1 className="section-title text-[22px]">每日简报</h1>
          <p className="text-[13px] text-muted">共 {total} 篇文章 · {groups.length} 个分类</p>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-8 pb-8">
        <div className="max-w-[720px] space-y-3">
          {groups.map(g => (
            <div key={g.category} className="card overflow-hidden">
              <button onClick={() => expand(g.category)}
                className={`w-full flex items-center gap-3 px-5 py-4 text-left transition-colors ${
                  expanded === g.category ? 'bg-surface-2' : 'hover:bg-surface-2'
                }`}>
                <span className={`text-[10px] text-faint transition-transform ${expanded === g.category ? 'rotate-90 text-ink' : ''}`}>▶</span>
                <div className="flex-1">
                  <span className="text-[15px] font-medium text-ink">{g.label}</span>
                  <span className="ml-2 text-[12px] text-muted">{g.total} 篇</span>
                </div>
                <div className="h-1.5 w-16 overflow-hidden rounded-full bg-edge">
                  <div className="h-full rounded-full bg-ink" style={{ width: `${Math.min(100, (g.total / Math.max(total, 1)) * 300)}%` }} />
                </div>
              </button>

              {expanded === g.category && (
                <div className="border-t border-edge px-5 py-2">
                  {loading ? (
                    <p className="py-3 text-center text-[12px] text-muted">加载中...</p>
                  ) : articles.map(a => (
                    <div key={a.id} className="flex items-start gap-3 border-b border-edge/60 py-2.5 last:border-0">
                      <div className="min-w-0 flex-1">
                        <p className="line-clamp-2 text-[13px] leading-snug text-ink">{a.title}</p>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="text-[11px] text-muted">{a.source_id}</span>
                          <span className="text-[11px] text-faint">{timeAgo(a.published_at)}</span>
                        </div>
                      </div>
                      <div className="mt-1 flex shrink-0 items-center gap-1">
                        <div className="h-1 w-6 overflow-hidden rounded-full bg-edge">
                          <div className="h-full rounded-full" style={{
                            width: `${a.importance_score * 100}%`,
                            background: a.importance_score >= 0.7 ? 'var(--ok)' : a.importance_score >= 0.4 ? 'var(--warn)' : 'var(--danger)'
                          }} />
                        </div>
                        <span className="text-[9px] text-muted">{a.importance_score.toFixed(1)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
