'use client';
import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import Nav from '@/components/Nav';

const TAGS = [
  'LLM', 'NLP', 'CV', '多模态', '语音AI', 'AI Agent', 'RAG',
  '具身智能', 'AI安全', 'AI芯片', 'AI Infra', '开源模型',
  'AI编程', 'AI绘画', 'AI视频', '数字人', '企业AI',
  'AI医疗', 'AI教育', 'AI金融', 'AI电商', '融资',
  '政策法规', '独立开发', 'Prompt工程', 'AI变现', 'AI工作流',
];

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user) {
      setDisplayName(user?.display_name);
      setTags(user?.interest_tags || []);
    }
  }, [user]);

  const save = async () => {
    await api.updateMe({ display_name: displayName, interest_tags: tags });
    await refreshUser();
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  // auth guard removed

  return (
    <div className="min-h-screen bg-canvas">
      <Nav />
      <main className="mx-auto max-w-lg p-6">
        <h2 className="section-title mb-4 text-lg">设置</h2>
        <div className="card space-y-4 p-6">
          <div>
            <label className="mb-1 block text-xs text-muted">昵称</label>
            <input value={displayName} onChange={e => setDisplayName(e.target.value)} className="input" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">邮箱</label>
            <input value={user?.email} disabled className="input opacity-60" />
          </div>
          <div>
            <label className="mb-2 block text-xs text-muted">兴趣标签</label>
            <div className="flex flex-wrap gap-2">
              {TAGS.map(t => (
                <button key={t} onClick={() => setTags(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t])}
                  className={`chip ${tags.includes(t) ? 'chip-active' : ''}`}>
                  {t}
                </button>
              ))}
            </div>
          </div>
          <button onClick={save} className="btn btn-primary w-full py-2.5">
            {saved ? '已保存' : '保存'}
          </button>
        </div>
      </main>
    </div>
  );
}
