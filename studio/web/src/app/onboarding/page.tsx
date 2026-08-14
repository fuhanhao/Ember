'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

const ROLES = [
  { value: 'ai_engineer', label: 'AI 工程师' },
  { value: 'developer', label: '开发者' },
  { value: 'product_manager', label: '产品经理' },
  { value: 'founder', label: '创始人' },
  { value: 'investor', label: '投资人' },
  { value: 'content_creator', label: '内容创作者' },
  { value: 'executive', label: '企业高管' },
  { value: 'student', label: '学生/研究者' },
  { value: 'other', label: '其他' },
];

const TAGS = [
  'LLM', 'NLP', 'CV', '多模态', '语音AI', 'AI Agent', 'RAG',
  '具身智能', 'AI安全', 'AI芯片', 'AI Infra', '开源模型',
  'AI编程', 'AI绘画', 'AI视频', '数字人', '企业AI',
  'AI医疗', 'AI教育', 'AI金融', 'AI电商', '融资',
  '政策法规', '独立开发', 'Prompt工程', 'AI变现', 'AI工作流',
];

export default function OnboardingPage() {
  const [step, setStep] = useState(1);
  const [role, setRole] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const router = useRouter();

  const toggleTag = (tag: string) => {
    setTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]);
  };

  const finish = async () => {
    await api.onboarding({ role, interest_tags: tags });
    router.push('/');
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6" style={{ background: 'var(--gradient-soft)' }}>
      <div className="w-full max-w-lg">
        <h1 className="mb-1 text-center text-xl font-bold">
          <span className="text-ember">Ember</span>
        </h1>
        <p className="mb-6 text-center text-sm text-muted">设置你的偏好，获得个性化推荐</p>

        <div className="mb-8 flex gap-2">
          {[1, 2].map(s => (
            <div key={s} className={`h-1 flex-1 rounded-full ${s <= step ? 'bg-ink' : 'bg-edge'}`} />
          ))}
        </div>

        {step === 1 && (
          <div>
            <h2 className="section-title mb-4 text-lg">你的角色</h2>
            <div className="grid grid-cols-3 gap-3">
              {ROLES.map(r => (
                <button key={r.value} onClick={() => setRole(r.value)}
                  className={`card card-hover p-3 text-center text-sm transition-colors ${
                    role === r.value ? '!border-ink !bg-ink !text-white' : 'text-muted'
                  }`}>
                  {r.label}
                </button>
              ))}
            </div>
            <button onClick={() => step === 1 && role && setStep(2)} disabled={!role}
              className="btn btn-primary mt-6 w-full py-2.5">
              下一步
            </button>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 className="section-title mb-1 text-lg">选择兴趣标签</h2>
            <p className="mb-4 text-xs text-muted">至少选择 3 个</p>
            <div className="flex flex-wrap gap-2">
              {TAGS.map(t => (
                <button key={t} onClick={() => toggleTag(t)}
                  className={`chip ${tags.includes(t) ? 'chip-active' : ''}`}>
                  {t}
                </button>
              ))}
            </div>
            <div className="mt-6 flex gap-3">
              <button onClick={() => setStep(1)} className="btn btn-ghost flex-1 py-2.5">
                上一步
              </button>
              <button onClick={finish} disabled={tags.length < 3}
                className="btn btn-primary flex-1 py-2.5">
                完成
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
