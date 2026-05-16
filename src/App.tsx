import React, { useState, useEffect, useRef } from 'react';
import {
  Play, Pause, SkipBack, SkipForward,
  Mic, Clock, FileText, ExternalLink,
  RefreshCw, ChevronLeft, AlertCircle,
  Sparkles,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API = 'http://localhost:8000';

// --- Types ---

interface EpisodeSummary {
  episodeId: string;
  title: string;
  city: string;
  date: string;
  summary: string;
  audioPath: string;
  createdAt: string;
  segmentsCount: number;
  durationSec: number;
}

interface Segment {
  segmentId: string;
  type: string;
  title: string;
  text: string;
  estimatedDurationSec: number;
  sourceIds: string[];
  riskLevel: string;
}

interface Source {
  sourceId: string;
  title: string;
  url: string;
  type: string;
}

interface EpisodeDetail {
  episodeId: string;
  title: string;
  city: string;
  date: string;
  showName: string;
  hostName: string;
  summary: string;
  segments: Segment[];
  sources: Source[];
  audioPath: string;
  createdAt: string;
  durationSec: number;
}

// --- API helpers ---

async function fetchEpisodes(): Promise<EpisodeSummary[]> {
  const res = await fetch(`${API}/episodes`);
  if (!res.ok) throw new Error('Failed to fetch episodes');
  return res.json();
}

async function fetchEpisode(id: string): Promise<EpisodeDetail> {
  const res = await fetch(`${API}/episodes/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error('Episode not found');
  return res.json();
}

function audioUrl(episodeId: string): string {
  return `${API}/episodes/${encodeURIComponent(episodeId)}/audio`;
}

async function triggerPipeline(): Promise<{ episodeId: string; title: string }> {
  const res = await fetch(`${API}/pipeline/run?mode=news`, { method: 'POST' });
  if (!res.ok) throw new Error('Pipeline failed');
  return res.json();
}

// --- Segment type → Chinese label ---

const SEGMENT_LABELS: Record<string, string> = {
  opening: '开场',
  headline: '要闻',
  line_update: '线路变化',
  commute_tip: '通勤贴士',
  city_story: '城市小事',
  safety: '出行安全',
  ending: '结尾',
};

const SEGMENT_COLORS: Record<string, string> = {
  opening: 'text-emerald-400 bg-emerald-500/10',
  headline: 'text-blue-400 bg-blue-500/10',
  line_update: 'text-amber-400 bg-amber-500/10',
  commute_tip: 'text-violet-400 bg-violet-500/10',
  city_story: 'text-pink-400 bg-pink-500/10',
  safety: 'text-red-400 bg-red-500/10',
  ending: 'text-emerald-400 bg-emerald-500/10',
};

const RISK_BADGES: Record<string, string> = {
  low: 'text-slate-400',
  medium: 'text-amber-400',
  high: 'text-red-400 bg-red-500/10 px-2 py-0.5 rounded',
};

function fmtDuration(sec: number): string {
  if (!sec || sec <= 0) return '--:--';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

// --- Components ---

function EpisodeListPage({
  onSelect,
  onGenerate,
}: {
  onSelect: (id: string) => void;
  onGenerate: () => void;
}) {
  const [episodes, setEpisodes] = useState<EpisodeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchEpisodes();
      setEpisodes(data);
    } catch (e: any) {
      setError(e.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-md mx-auto px-6 pt-10 pb-20"
    >
      <header className="mb-8 text-center">
        <div className="w-14 h-14 bg-gradient-to-br from-emerald-500 to-blue-500 rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-lg">
          <Mic size={28} color="white" />
        </div>
        <h1 className="text-2xl font-bold">小站早班车</h1>
        <p className="text-slate-500 text-sm mt-1">地铁通勤每日播客</p>
      </header>

      <div className="mb-6">
        <button
          onClick={onGenerate}
          className="w-full py-3 bg-gradient-to-r from-emerald-600 to-blue-600 rounded-xl font-bold text-white flex items-center justify-center gap-2 hover:opacity-90 transition-opacity"
        >
          <Sparkles size={18} /> 生成今日节目
        </button>
      </div>

      {loading && (
        <div className="text-center text-slate-500 py-8">加载中...</div>
      )}

      {error && (
        <div className="glass-card p-4 border-red-500/30 text-red-400 text-sm flex items-center gap-2 mb-4">
          <AlertCircle size={16} /> {error}
          <button onClick={load} className="ml-auto text-blue-400 hover:underline">重试</button>
        </div>
      )}

      {!loading && !error && episodes.length === 0 && (
        <div className="text-center text-slate-500 py-12">
          <p className="mb-2">还没有节目</p>
          <p className="text-sm">点击上方按钮生成第一期《小站早班车》</p>
        </div>
      )}

      <div className="space-y-3">
        {episodes.map((ep) => (
          <button
            key={ep.episodeId}
            onClick={() => onSelect(ep.episodeId)}
            className="w-full glass-card p-4 text-left hover:border-blue-500/30 transition-all"
          >
            <div className="flex justify-between items-start mb-1">
              <h3 className="font-bold text-sm line-clamp-1">{ep.title}</h3>
              <span className="text-xs text-slate-500 shrink-0 ml-2">
                {fmtDuration(ep.durationSec)}
              </span>
            </div>
            <p className="text-xs text-slate-500 line-clamp-2 mb-2">{ep.summary}</p>
            <div className="flex items-center gap-3 text-xs text-slate-600">
              <span>{ep.date}</span>
              <span>{ep.city}</span>
              <span>{ep.segmentsCount} 段</span>
            </div>
          </button>
        ))}
      </div>
    </motion.div>
  );
}

function PlayerPage({
  episodeId,
  onBack,
}: {
  episodeId: string;
  onBack: () => void;
}) {
  const [episode, setEpisode] = useState<EpisodeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchEpisode(episodeId);
        setEpisode(data);
      } catch (e: any) {
        setError(e.message || '加载失败');
      } finally {
        setLoading(false);
      }
    })();
  }, [episodeId]);

  const togglePlay = () => {
    const a = audioRef.current;
    if (!a) return;
    if (playing) {
      a.pause();
    } else {
      a.play().catch(() => setError('无法播放音频'));
    }
    setPlaying(!playing);
  };

  const onTimeUpdate = () => {
    if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
  };

  const onEnded = () => setPlaying(false);

  if (loading) {
    return (
      <div className="max-w-md mx-auto px-6 pt-20 text-center text-slate-500">
        加载中...
      </div>
    );
  }

  if (error || !episode) {
    return (
      <div className="max-w-md mx-auto px-6 pt-20 text-center">
        <p className="text-red-400 mb-4">{error || '节目未找到'}</p>
        <button onClick={onBack} className="text-blue-400 hover:underline">返回列表</button>
      </div>
    );
  }

  const duration = episode.durationSec || 0;
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="max-w-md mx-auto px-6 pt-6 pb-20 flex flex-col min-h-screen"
    >
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <button onClick={onBack} className="p-2 hover:bg-white/5 rounded-lg">
          <ChevronLeft size={20} />
        </button>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">
          正在播放
        </div>
        <div className="w-8" />
      </div>

      {/* Cover */}
      <div className="flex-1 flex flex-col items-center">
        <div className="w-56 h-56 glass-card overflow-hidden mb-8 p-2 shadow-xl">
          <div className="w-full h-full rounded-2xl bg-gradient-to-br from-emerald-600 to-blue-600 flex items-center justify-center">
            <Mic size={64} color="white" className={playing ? 'animate-pulse' : ''} />
          </div>
        </div>

        {/* Title */}
        <div className="text-center w-full mb-6">
          <h2 className="text-xl font-bold mb-1">{episode.title}</h2>
          <p className="text-slate-400 text-sm">{episode.showName} · {episode.hostName}</p>
          <p className="text-slate-600 text-xs mt-1">{episode.date} · {episode.city}</p>
        </div>

        {/* Audio element */}
        <audio
          ref={audioRef}
          src={audioUrl(episodeId)}
          onTimeUpdate={onTimeUpdate}
          onEnded={onEnded}
          onError={() => setError('音频加载失败')}
          preload="auto"
        />

        {/* Progress bar */}
        <div className="w-full mb-4">
          <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden mb-2">
            <div
              className="h-full bg-emerald-500 transition-all duration-200"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-slate-500 font-mono">
            <span>{fmtDuration(Math.floor(currentTime))}</span>
            <span>{fmtDuration(duration)}</span>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between w-full px-4 mb-10">
          <button className="text-slate-400"><SkipBack size={28} /></button>
          <button
            onClick={togglePlay}
            className="w-16 h-16 bg-white rounded-full flex items-center justify-center text-black hover:scale-105 transition-transform"
          >
            {playing ? <Pause size={32} fill="black" /> : <Play size={32} fill="black" className="ml-1" />}
          </button>
          <button className="text-slate-400"><SkipForward size={28} /></button>
        </div>

        {/* Summary */}
        <div className="w-full glass-card p-3 mb-4">
          <p className="text-sm text-slate-300">{episode.summary}</p>
        </div>

        {/* Segments */}
        <div className="w-full mb-4">
          <h3 className="text-sm font-bold text-slate-400 mb-2 flex items-center gap-1">
            <FileText size={14} /> 节目段落
          </h3>
          <div className="space-y-2">
            {episode.segments.map((seg) => (
              <details key={seg.segmentId} className="glass-card p-3 cursor-pointer">
                <summary className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${SEGMENT_COLORS[seg.type] || 'text-slate-400'}`}>
                      {SEGMENT_LABELS[seg.type] || seg.type}
                    </span>
                    {seg.title}
                  </span>
                  <span className={`text-xs ${RISK_BADGES[seg.riskLevel] || ''}`}>
                    {seg.riskLevel === 'high' ? '⚠ 高风险' : seg.riskLevel === 'medium' ? '● 中风险' : ''}
                  </span>
                </summary>
                <p className="text-sm text-slate-400 mt-2 leading-relaxed">{seg.text}</p>
                {seg.sourceIds.length > 0 && (
                  <div className="text-xs text-slate-600 mt-1">
                    来源: {seg.sourceIds.join(', ')}
                  </div>
                )}
              </details>
            ))}
          </div>
        </div>

        {/* Sources */}
        {episode.sources.length > 0 && (
          <div className="w-full mb-6">
            <h3 className="text-sm font-bold text-slate-400 mb-2 flex items-center gap-1">
              <ExternalLink size={14} /> 信息来源
            </h3>
            <div className="space-y-1">
              {episode.sources.map((src) => (
                <a
                  key={src.sourceId}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-xs text-blue-400 hover:text-blue-300 truncate"
                >
                  {src.title || src.url}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function GeneratingModal({ onDone }: { onDone: () => void }) {
  const [status, setStatus] = useState<'running' | 'done' | 'error'>('running');
  const [message, setMessage] = useState('正在搜集今日地铁出行信息...');

  useEffect(() => {
    (async () => {
      try {
        setMessage('正在搜集今日地铁出行信息...');
        const result = await triggerPipeline();
        setMessage(`生成完成：${result.title}`);
        setStatus('done');
        setTimeout(onDone, 2000);
      } catch (e: any) {
        setMessage(`生成失败：${e.message || '未知错误'}`);
        setStatus('error');
      }
    })();
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    >
      <div className="glass-card p-8 max-w-sm mx-4 text-center">
        {status === 'running' && (
          <>
            <div className="w-16 h-16 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-300">{message}</p>
            <p className="text-xs text-slate-600 mt-2">这可能需要 1-3 分钟</p>
          </>
        )}
        {status === 'done' && (
          <>
            <div className="text-4xl mb-4">✅</div>
            <p className="text-sm text-emerald-400">{message}</p>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="text-4xl mb-4">❌</div>
            <p className="text-sm text-red-400">{message}</p>
            <button
              onClick={onDone}
              className="mt-4 px-4 py-2 bg-white/10 rounded-lg text-sm"
            >
              返回
            </button>
          </>
        )}
      </div>
    </motion.div>
  );
}

// --- App ---

type View =
  | { name: 'list' }
  | { name: 'player'; episodeId: string }
  | { name: 'generating' };

function App() {
  const [view, setView] = useState<View>({ name: 'list' });

  return (
    <div className="min-h-screen bg-[#0b1120] text-white">
      <AnimatePresence mode="wait">
        {view.name === 'list' && (
          <EpisodeListPage
            key="list"
            onSelect={(id) => setView({ name: 'player', episodeId: id })}
            onGenerate={() => setView({ name: 'generating' })}
          />
        )}
        {view.name === 'player' && (
          <PlayerPage
            key="player"
            episodeId={view.episodeId}
            onBack={() => setView({ name: 'list' })}
          />
        )}
        {view.name === 'generating' && (
          <GeneratingModal
            key="generating"
            onDone={() => setView({ name: 'list' })}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
