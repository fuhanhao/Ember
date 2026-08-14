'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { useTheme } from '@/lib/theme';

const links = [
  { href: '/', label: '信息流' },
  { href: '/search', label: '搜索' },
  { href: '/brief', label: '简报' },
  { href: '/bookmarks', label: '收藏' },
  { href: '/notebooks', label: '笔记本' },
  { href: '/history', label: '生成历史' },
];

export default function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <nav className="sticky top-0 z-50 flex items-center justify-between border-b border-edge bg-canvas/85 px-6 py-3 backdrop-blur-xl">
      <div className="flex items-center gap-8">
        <Link href="/" className="group flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-[var(--gradient)] text-white shadow-[0_4px_14px_-4px_var(--accent-glow)] transition-transform group-hover:scale-105">
            <svg width="17" height="17" viewBox="0 0 32 32" fill="none">
              <path d="M16 4c2 5 7 8.4 7 13.8a7 7 0 1 1-14 0c0-2.5 1.2-4.7 2.8-6.6.3 1.6 1 3 2.2 4-.3-4 1-8.8 2-11.2z" fill="#fff"/>
              <circle cx="23.5" cy="9.5" r="1.5" fill="#f0b34a"/>
            </svg>
          </span>
          <span className="text-[17px] font-bold tracking-wide">
            <span className="text-ember">Ember</span>
          </span>
        </Link>
        <div className="flex gap-1">
          {links.map(l => (
            <Link
              key={l.href}
              href={l.href}
              className={`nav-pill ${pathname === l.href ? 'nav-pill-active' : ''}`}
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3 text-sm">
        <button
          onClick={toggleTheme}
          title={theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
          className="flex h-8 w-8 items-center justify-center rounded-[8px] text-muted transition-colors hover:bg-surface-2 hover:text-ink"
        >
          {theme === 'dark' ? (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>
        {user && (
          <>
            <Link href="/settings" className="text-muted transition-colors hover:text-ink">
              {user.display_name}
            </Link>
            <button onClick={logout} className="text-muted transition-colors hover:text-danger">
              退出
            </button>
          </>
        )}
      </div>
    </nav>
  );
}
