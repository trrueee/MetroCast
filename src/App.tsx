import React, { useState, useEffect } from 'react';
import { 
  Play, 
  Settings, 
  Clock, 
  Mic, 
  Volume2, 
  ArrowRight, 
  Sparkles, 
  History,
  Pause,
  SkipForward,
  SkipBack,
  Heart,
  Share2,
  ChevronDown,
  Database,
  FileText,
  Music,
  RefreshCw,
  CheckCircle,
  XCircle,
  ExternalLink
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// --- Types ---
type Tone = 'relaxed' | 'professional' | 'humorous' | 'gentle' | 'news';
type Theme = 'tech' | 'career' | 'finance' | 'lifestyle' | 'news' | 'english';

interface PodcastConfig {
  timeOfDay: 'morning' | 'evening';
  duration: number; // minutes
  themes: Theme[];
  tone: Tone;
}

// --- Mock Data ---
const THEMES: { id: Theme; label: string; icon: string }[] = [
  { id: 'tech', label: 'AI 科技', icon: '🤖' },
  { id: 'career', label: '职场成长', icon: '💼' },
  { id: 'finance', label: '财经消费', icon: '📈' },
  { id: 'lifestyle', label: '本地生活', icon: '📍' },
  { id: 'news', label: '热点解读', icon: '🔥' },
  { id: 'english', label: '英语学习', icon: '🗣️' },
];

const TONES: { id: Tone; label: string }[] = [
  { id: 'relaxed', label: '轻松' },
  { id: 'professional', label: '专业' },
  { id: 'humorous', label: '毒舌' },
  { id: 'gentle', label: '温柔' },
  { id: 'news', label: '新闻联播风' },
];

// --- Components ---

const LandingPage = ({ onStart }: { onStart: () => void }) => (
  <motion.div 
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    className="max-w-md mx-auto pt-20 px-6 text-center"
  >
    <div className="mb-8 flex justify-center">
      <div className="w-20 h-20 bg-blue-600 rounded-3xl flex items-center justify-center shadow-lg shadow-blue-500/50 pulse">
        <Mic size={40} color="white" />
      </div>
    </div>
    <h1 className="text-4xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
      听见今天
    </h1>
    <p className="text-slate-400 mb-8 text-lg">
      地铁通勤 10 分钟，<br />为你生成专属的个人信息流。
    </p>

    <div className="glass-card p-4 mb-10 border-blue-500/30 bg-blue-500/5 text-left">
      <div className="flex items-center gap-2 mb-2 text-blue-400 font-bold text-xs uppercase tracking-wider">
        <Sparkles size={14} /> 今日灵感
      </div>
      <p className="text-sm italic text-slate-300">"最好的播客不是听别人在说什么，而是听 AI 如何把你感兴趣的世界连接起来。"</p>
    </div>

    <button onClick={onStart} className="btn-primary w-full py-4 text-xl">
      开启今日通勤 <ArrowRight size={24} />
    </button>
    
    <div className="mt-8 text-center">
      <button 
        onClick={() => window.dispatchEvent(new CustomEvent('changeView', { detail: 'admin' }))}
        className="text-slate-500 text-sm hover:text-blue-400 transition-colors flex items-center justify-center gap-1 mx-auto"
      >
        <Settings size={14} /> 管理后台 (MVP)
      </button>
    </div>

    <div className="mt-12 grid grid-cols-2 gap-4 text-left">
      <div className="glass-card p-4">
        <Sparkles className="text-blue-400 mb-2" size={20} />
        <h3 className="text-sm font-bold">AI 每日生成</h3>
        <p className="text-xs text-slate-500">根据兴趣深度定制内容</p>
      </div>
      <div className="glass-card p-4">
        <Clock className="text-emerald-400 mb-2" size={20} />
        <h3 className="text-sm font-bold">完美适配时长</h3>
        <p className="text-xs text-slate-500">按通勤时间控制进度</p>
      </div>
    </div>
  </motion.div>
);

const GeneratorSettings = ({ onGenerate }: { onGenerate: (config: PodcastConfig) => void }) => {
  const [config, setConfig] = useState<PodcastConfig>({
    timeOfDay: 'morning',
    duration: 10,
    themes: ['tech'],
    tone: 'relaxed',
  });

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="max-w-md mx-auto px-6 pt-10 pb-20"
    >
      <header className="mb-8">
        <h2 className="text-2xl font-bold mb-2">生成今天的播客</h2>
        <p className="text-slate-400">设置你的通勤偏好</p>
      </header>

      <section className="mb-8">
        <label className="text-sm font-semibold text-slate-500 uppercase mb-3 block">时间点</label>
        <div className="grid grid-cols-2 gap-3">
          {(['morning', 'evening'] as const).map(t => (
            <button
              key={t}
              onClick={() => setConfig({ ...config, timeOfDay: t })}
              className={`p-4 rounded-2xl border-2 transition-all ${
                config.timeOfDay === t 
                  ? 'border-blue-500 bg-blue-500/10 text-blue-400' 
                  : 'border-white/5 bg-white/5 text-slate-400'
              }`}
            >
              {t === 'morning' ? '☀️ 早高峰' : '🌙 晚高峰'}
            </button>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <label className="text-sm font-semibold text-slate-500 uppercase mb-3 block">听多久 ({config.duration} 分钟)</label>
        <input 
          type="range" min="5" max="30" step="5"
          value={config.duration}
          onChange={(e) => setConfig({ ...config, duration: parseInt(e.target.value) })}
          className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500"
        />
        <div className="flex justify-between mt-2 text-xs text-slate-500">
          <span>5m</span>
          <span>15m</span>
          <span>30m</span>
        </div>
      </section>

      <section className="mb-8">
        <label className="text-sm font-semibold text-slate-500 uppercase mb-3 block">想听什么</label>
        <div className="grid grid-cols-3 gap-2">
          {THEMES.map(theme => (
            <button
              key={theme.id}
              onClick={() => {
                const themes = config.themes.includes(theme.id)
                  ? config.themes.filter(t => t !== theme.id)
                  : [...config.themes, theme.id];
                setConfig({ ...config, themes });
              }}
              className={`p-3 rounded-xl text-center text-xs transition-all border ${
                config.themes.includes(theme.id)
                  ? 'border-blue-500 bg-blue-500/20'
                  : 'border-transparent bg-white/5'
              }`}
            >
              <div className="text-lg mb-1">{theme.icon}</div>
              {theme.label}
            </button>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <label className="text-sm font-semibold text-slate-500 uppercase mb-3 block">口吻风格</label>
        <div className="flex flex-wrap gap-2">
          {TONES.map(tone => (
            <button
              key={tone.id}
              onClick={() => setConfig({ ...config, tone: tone.id })}
              className={`px-4 py-2 rounded-full text-sm transition-all ${
                config.tone === tone.id
                  ? 'bg-emerald-500 text-white'
                  : 'bg-white/5 text-slate-400'
              }`}
            >
              {tone.label}
            </button>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <label className="text-sm font-semibold text-slate-500 uppercase mb-3 block">或者：转换长文章</label>
        <textarea 
          placeholder="粘贴文章链接或全文，AI 将其转化为对谈式播客..."
          className="w-full h-24 bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:border-blue-500 focus:outline-none transition-colors resize-none"
        />
      </section>

      <button 
        onClick={() => onGenerate(config)}
        className="btn-primary w-full py-4 text-lg"
      >
        生成播客内容
      </button>
    </motion.div>
  );
};

const LoadingState = () => (
  <div className="flex flex-col items-center justify-center h-[80vh] px-10 text-center">
    <motion.div 
      animate={{ 
        scale: [1, 1.2, 1],
        rotate: [0, 180, 360]
      }}
      transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
      className="w-24 h-24 border-4 border-blue-500 border-t-transparent rounded-full mb-8"
    />
    <motion.h2 
      animate={{ opacity: [0.5, 1, 0.5] }}
      transition={{ duration: 2, repeat: Infinity }}
      className="text-xl font-bold mb-2"
    >
      正在为你编写口播稿...
    </motion.h2>
    <p className="text-slate-500 text-sm">搜集今日 {new Date().toLocaleDateString()} 的热点资讯</p>
  </div>
);

const PlayerPage = ({ config }: { config: PodcastConfig }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let interval: any;
    if (isPlaying && progress < 100) {
      interval = setInterval(() => {
        setProgress(p => Math.min(p + 0.1, 100));
      }, 100);
    }
    return () => clearInterval(interval);
  }, [isPlaying, progress]);

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="max-w-md mx-auto px-6 pt-6 pb-20 flex flex-col h-[100vh]"
    >
      <div className="flex justify-between items-center mb-10">
        <button className="p-2 bg-white/5 rounded-full"><ChevronDown /></button>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">正在播放</div>
        <button className="p-2 bg-white/5 rounded-full"><History size={20} /></button>
      </div>

      <div className="flex-1 flex flex-col items-center">
        <motion.div 
          animate={{ scale: isPlaying ? 1.05 : 1 }}
          className="w-64 h-64 glass-card overflow-hidden mb-10 p-2 shadow-2xl"
        >
          <div className="w-full h-full rounded-2xl bg-gradient-to-br from-blue-600 to-emerald-600 flex items-center justify-center">
            <Volume2 size={80} color="white" className={isPlaying ? 'pulse' : ''} />
          </div>
        </motion.div>

        <div className="text-center w-full mb-10">
          <h2 className="text-2xl font-bold mb-2">
            {config.timeOfDay === 'morning' ? '早安，你的 10 分钟科技日报' : '晚安，今日资讯复盘'}
          </h2>
          <p className="text-blue-400 font-medium mb-4">听见今天 • {config.duration} 分钟</p>
          <div className="glass-card p-4 text-left text-sm text-slate-400 line-clamp-3">
            今日摘要：3 条重要 AI 资讯 + 1 个关于大模型效率的深度解释 + 给打工人的 1 个行动建议。
          </div>
        </div>

        <div className="w-full mb-8">
          <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden mb-2">
            <motion.div 
              className="h-full bg-blue-500" 
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between text-[10px] text-slate-500 font-mono">
            <span>00:42</span>
            <span>-{config.duration}:00</span>
          </div>
        </div>

        <div className="flex items-center justify-between w-full px-4 mb-12">
          <button className="text-slate-400 hover:text-white transition-colors"><Heart size={24} /></button>
          <button className="text-white"><SkipBack size={32} fill="white" /></button>
          <button 
            onClick={() => setIsPlaying(!isPlaying)}
            className="w-20 h-20 bg-white rounded-full flex items-center justify-center text-black hover:scale-105 transition-transform"
          >
            {isPlaying ? <Pause size={40} fill="black" /> : <Play size={40} fill="black" className="ml-1" />}
          </button>
          <button className="text-white"><SkipForward size={32} fill="white" /></button>
          <button className="text-slate-400 hover:text-white transition-colors"><Share2 size={24} /></button>
        </div>
      </div>
      
      <div className="glass-card p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white/10 rounded-lg flex items-center justify-center"><Mic size={18} /></div>
          <div>
            <div className="text-xs font-bold">查看字幕稿</div>
            <div className="text-[10px] text-slate-500">已生成全文 1240 字</div>
          </div>
        </div>
        <button className="text-blue-400 text-sm font-bold">继续生成相关内容</button>
      </div>
    </motion.div>
  );
}

const AdminDashboard = () => {
  const [activeTab, setActiveTab] = useState<'material' | 'script' | 'audio'>('material');
  const [isRunning, setIsRunning] = useState(false);

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="min-h-screen p-6 max-w-4xl mx-auto"
    >
      <header className="flex justify-between items-center mb-10">
        <div>
          <h1 className="text-2xl font-bold">MetroCast 控制台</h1>
          <p className="text-slate-500 text-sm">内容抓取、脚本改写与发布管理</p>
        </div>
        <button 
          onClick={() => setIsRunning(true)}
          disabled={isRunning}
          className={`px-6 py-2 rounded-xl flex items-center gap-2 font-bold transition-all ${
            isRunning ? 'bg-slate-800 text-slate-500' : 'bg-blue-600 text-white hover:bg-blue-500'
          }`}
        >
          <RefreshCw size={18} className={isRunning ? 'animate-spin' : ''} />
          {isRunning ? '正在运行流水线...' : '运行每日抓取'}
        </button>
      </header>

      <nav className="flex gap-4 mb-8 border-b border-white/5 pb-4">
        {[
          { id: 'material', label: '素材池', icon: Database },
          { id: 'script', label: '播客稿', icon: FileText },
          { id: 'audio', label: '音频管理', icon: Music },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
              activeTab === tab.id ? 'bg-white/10 text-white' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <tab.icon size={18} />
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="glass-card p-6 min-h-[500px]">
        {activeTab === 'material' && (
          <div>
            <h2 className="text-lg font-bold mb-4">今日抓取素材 (12)</h2>
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="p-4 bg-white/5 rounded-xl border border-white/5 flex justify-between items-center">
                  <div>
                    <div className="font-bold mb-1">AI 领域重大突破：Structured Outputs 发布</div>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded">Hacker News</span>
                      <span>5 分钟前</span>
                      <span className="text-emerald-400">评分: 9.5</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="p-2 hover:bg-white/10 rounded-lg text-slate-400"><ExternalLink size={16} /></button>
                    <button className="p-2 hover:bg-emerald-500/20 rounded-lg text-emerald-400"><CheckCircle size={16} /></button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'script' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold">5月13日 播客稿 (草稿)</h2>
              <div className="flex gap-2">
                <button className="px-3 py-1 bg-white/5 rounded-lg text-xs">重新生成</button>
                <button className="px-3 py-1 bg-emerald-600 rounded-lg text-xs font-bold">确认进入 TTS</button>
              </div>
            </div>
            <textarea 
              className="w-full h-[400px] bg-black/20 border border-white/10 rounded-xl p-4 text-sm font-mono text-slate-300 focus:outline-none focus:border-blue-500/50"
              defaultValue={`# 早上好，欢迎来到每日地铁播客

今天我们来聊聊三件值得你在地铁上听完的 AI 圈大事。

第一件事，是关于 OpenAI 最新推出的 Structured Outputs。简单来说，如果你是一个开发者，你现在可以让 AI 100% 按照你想要的 JSON 格式吐出数据。这意味着，像我这样的自动播客生成器，出错的概率又降低了一大截...

... (省略 800 字)`}
            />
          </div>
        )}

        {activeTab === 'audio' && (
          <div>
            <h2 className="text-lg font-bold mb-4">已生成音频</h2>
            <div className="space-y-4">
              <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-2xl">
                <div className="flex justify-between items-center mb-4">
                  <div>
                    <div className="font-bold">episode_20260513.mp3</div>
                    <div className="text-xs text-slate-500">3分42秒 • 5.2MB • OpenAI Alloy Voice</div>
                  </div>
                  <span className="bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded-full text-xs font-bold">已就绪</span>
                </div>
                <div className="h-1 w-full bg-white/10 rounded-full mb-4">
                  <div className="h-full bg-blue-500 w-1/3 rounded-full" />
                </div>
                <div className="flex gap-3">
                  <button className="px-4 py-2 bg-white text-black rounded-lg text-xs font-bold flex items-center gap-2">
                    <Play size={14} fill="black" /> 预览音频
                  </button>
                  <button className="px-4 py-2 bg-white/10 rounded-lg text-xs font-bold">推送到 RSS</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="mt-10 text-center">
        <button 
          onClick={() => window.dispatchEvent(new CustomEvent('changeView', { detail: 'landing' }))}
          className="text-slate-500 text-sm hover:text-white transition-colors"
        >
          返回首页
        </button>
      </footer>
    </motion.div>
  );
};

function App() {
  const [view, setView] = useState<'landing' | 'settings' | 'loading' | 'player' | 'admin'>('landing');
  const [config, setConfig] = useState<PodcastConfig | null>(null);

  useEffect(() => {
    const handleViewChange = (e: any) => setView(e.detail);
    window.addEventListener('changeView', handleViewChange);
    return () => window.removeEventListener('changeView', handleViewChange);
  }, []);

  const handleGenerate = (newConfig: PodcastConfig) => {
    setConfig(newConfig);
    setView('loading');
    setTimeout(() => {
      setView('player');
    }, 3000); // Simulate generation
  };

  return (
    <div className="min-h-screen">
      <AnimatePresence mode="wait">
        {view === 'landing' && (
          <LandingPage key="landing" onStart={() => setView('settings')} />
        )}
        {view === 'settings' && (
          <GeneratorSettings key="settings" onGenerate={handleGenerate} />
        )}
        {view === 'loading' && (
          <LoadingState key="loading" />
        )}
        {view === 'player' && config && (
          <PlayerPage key="player" config={config} />
        )}
        {view === 'admin' && (
          <AdminDashboard key="admin" />
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
