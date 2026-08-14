'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isLogin) {
        await login(email, password);
        router.push('/');
      } else {
        await register(email, password, displayName);
        router.push('/onboarding');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-6" style={{ background: 'var(--gradient-soft)' }}>
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--gradient)] text-white shadow-[0_10px_28px_-8px_var(--accent-glow)]">
            <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
              <path d="M16 4c2 5 7 8.4 7 13.8a7 7 0 1 1-14 0c0-2.5 1.2-4.7 2.8-6.6.3 1.6 1 3 2.2 4-.3-4 1-8.8 2-11.2z" fill="#fff"/>
              <circle cx="23.5" cy="9.5" r="1.5" fill="#f0b34a"/>
            </svg>
          </span>
          <h1 className="text-2xl font-bold">
            <span className="text-ember">Ember</span>
          </h1>
          <p className="mt-2 text-sm text-muted">AI 智能阅读加工工作台</p>
        </div>

        <div className="card p-6">
          <div className="mb-6 flex rounded-[10px] bg-surface-2 p-1">
            <button onClick={() => setIsLogin(true)}
              className={`flex-1 rounded-[7px] py-2 text-sm font-medium transition-all ${isLogin ? 'bg-surface text-ink shadow-sm' : 'text-muted'}`}>
              登录
            </button>
            <button onClick={() => setIsLogin(false)}
              className={`flex-1 rounded-[7px] py-2 text-sm font-medium transition-all ${!isLogin ? 'bg-surface text-ink shadow-sm' : 'text-muted'}`}>
              注册
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <input type="text" placeholder="昵称" value={displayName} onChange={e => setDisplayName(e.target.value)} className="input" required />
            )}
            <input type="email" placeholder="邮箱" value={email} onChange={e => setEmail(e.target.value)} className="input" required />
            <input type="password" placeholder="密码" value={password} onChange={e => setPassword(e.target.value)} className="input" required />
            {error && <p className="text-xs text-danger">{error}</p>}
            <button type="submit" disabled={loading} className="btn btn-primary w-full py-2.5">
              {loading ? '...' : isLogin ? '登录' : '注册'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
