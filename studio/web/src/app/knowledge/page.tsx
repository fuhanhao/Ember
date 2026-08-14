'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

interface Bookmark {
  id: string;
  title: string;
  url: string;
  category?: string;
}

interface Notebook {
  id: string;
  title: string;
  description?: string | null;
  created_at?: string | null;
}

export default function KnowledgePage() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getBookmarks({ limit: '50' }).catch(() => ({ items: [] })),
      api.getNotebooks().catch(() => []),
    ]).then(([bm, nb]) => {
      setBookmarks((bm as any)?.items || []);
      setNotebooks(Array.isArray(nb) ? (nb as Notebook[]) : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="flex h-screen flex-col bg-canvas">
      <header className="flex items-center gap-4 px-8 pb-4 pt-8">
        <Link href="/" className="text-[13px] text-muted hover:text-ink hover:underline">← 返回</Link>
        <div>
          <h1 className="section-title text-[22px]">知识库</h1>
          <p className="text-[13px] text-muted">收藏、整理、检索你的信息资产</p>
        </div>
      </header>

      <main className="flex-1 overflow-auto px-8 pb-10">
        {loading ? (
          <div className="py-16 text-center text-[13px] text-muted">加载中...</div>
        ) : (
          <div className="grid gap-8 lg:grid-cols-2">
            <section>
              <h2 className="mb-3 text-[15px] font-semibold text-ink">收藏文章（{bookmarks.length}）</h2>
              {bookmarks.length === 0 ? (
                <div className="card p-6 text-[13px] text-muted">还没有收藏文章，去信息流里点亮「收藏」吧。</div>
              ) : (
                <div className="space-y-2">
                  {bookmarks.map(b => (
                    <a key={b.id} href={b.url} target="_blank" rel="noopener noreferrer"
                       className="card card-hover block p-4">
                      <div className="line-clamp-2 text-[14px] font-medium text-ink">{b.title}</div>
                      {b.category && <span className="chip mt-2">{b.category}</span>}
                    </a>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="mb-3 text-[15px] font-semibold text-ink">笔记本（{notebooks.length}）</h2>
              {notebooks.length === 0 ? (
                <div className="card p-6 text-[13px] text-muted">还没有笔记本，可在工作台里创建。</div>
              ) : (
                <div className="space-y-2">
                  {notebooks.map(n => (
                    <div key={n.id} className="card p-4">
                      <div className="text-[14px] font-medium text-ink">{n.title}</div>
                      {n.description && <div className="mt-1 text-[12px] text-muted">{n.description}</div>}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
