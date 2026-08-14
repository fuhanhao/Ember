'use client';
import Link from 'next/link';

interface Article {
  id: string;
  title: string;
  url: string;
  source_id: string;
  category: string;
  tags: string[];
  importance_score: number;
  content_signal?: number;
  published_at: string | null;
  feed_score?: number;
}

function timeAgo(iso: string | null) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
  return Math.floor(diff / 86400) + ' 天前';
}

const catColors: Record<string, { light: string; dark: string }> = {
  paper:          { light: 'bg-blue-500/10 text-blue-600',   dark: 'dark:bg-blue-500/20 dark:text-blue-300' },
  model_release:  { light: 'bg-purple-500/10 text-purple-600', dark: 'dark:bg-purple-500/20 dark:text-purple-300' },
  open_source:    { light: 'bg-green-500/10 text-green-600',  dark: 'dark:bg-green-500/20 dark:text-green-300' },
  funding:        { light: 'bg-yellow-500/10 text-yellow-700', dark: 'dark:bg-yellow-500/20 dark:text-yellow-300' },
  policy:         { light: 'bg-red-500/10 text-red-600',     dark: 'dark:bg-red-500/20 dark:text-red-300' },
  product_launch: { light: 'bg-cyan-500/10 text-cyan-600',   dark: 'dark:bg-cyan-500/20 dark:text-cyan-300' },
  tutorial:       { light: 'bg-teal-500/10 text-teal-600',   dark: 'dark:bg-teal-500/20 dark:text-teal-300' },
  opinion:        { light: 'bg-gray-500/10 text-gray-600',   dark: 'dark:bg-gray-500/20 dark:text-gray-300' },
  industry_report:{ light: 'bg-orange-500/10 text-orange-600', dark: 'dark:bg-orange-500/20 dark:text-orange-300' },
};
const defaultCat = { light: 'bg-gray-500/10 text-gray-600', dark: 'dark:bg-gray-500/20 dark:text-gray-300' };

export default function ArticleCard({ article, onBookmark, onAddToNotebook }: {
  article: Article;
  onBookmark?: (id: string) => void;
  onAddToNotebook?: (id: string) => void;
}) {
  const cat = catColors[article.category] || defaultCat;

  return (
    <div className="card card-hover p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <Link href={`/article/${article.id}`} className="text-[15px] font-medium text-ink hover:text-ink hover:underline leading-snug line-clamp-2">
            {article.title}
          </Link>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <span className={`text-[11px] px-2 py-0.5 rounded ${cat.light} ${cat.dark}`}>{article.category}</span>
            {article.tags?.slice(0, 3).map(t => (
              <span key={t} className="text-[11px] px-1.5 py-0.5 rounded bg-surface-2 text-muted">{t}</span>
            ))}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-xs text-muted">{timeAgo(article.published_at)}</div>
          <div className="text-xs text-faint mt-1">{article.source_id}</div>
        </div>
      </div>
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-edge/70">
        <div className="flex items-center gap-1">
          <div className="w-12 h-1.5 bg-edge rounded-full overflow-hidden">
            <div className="h-full rounded-full" style={{
              width: `${article.importance_score * 100}%`,
              background: article.importance_score >= 0.7 ? 'var(--ok)' : article.importance_score >= 0.4 ? 'var(--warn)' : 'var(--danger)'
            }} />
          </div>
          <span className="text-[11px] text-muted">{article.importance_score.toFixed(2)}</span>
        </div>
        <div className="flex gap-2">
          {onBookmark && (
            <button onClick={() => onBookmark(article.id)} className="text-[11px] text-muted hover:text-ink px-2 py-1 rounded hover:bg-surface-2">
              收藏
            </button>
          )}
          {onAddToNotebook && (
            <button onClick={() => onAddToNotebook(article.id)} className="text-[11px] text-muted hover:text-ok px-2 py-1 rounded hover:bg-surface-2">
              加入笔记本
            </button>
          )}
          <a href={article.url} target="_blank" rel="noopener" className="text-[11px] text-muted hover:text-ink px-2 py-1 rounded hover:bg-surface-2">
            原文
          </a>
        </div>
      </div>
    </div>
  );
}
