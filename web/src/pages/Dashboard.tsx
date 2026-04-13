import { useState, useEffect, useRef } from 'react';
import { Activity, Terminal, BrainCircuit, Search, Play, ImageIcon, Globe, Users } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export default function Dashboard() {
  const [query, setQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  
  // Crawler Logs & QR Code
  const [logs, setLogs] = useState<string[]>([]);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  
  // Forum Logs
  const [forumLogs, setForumLogs] = useState<string[]>([]);
  const forumEndRef = useRef<HTMLDivElement>(null);
  
  // Reports
  const [reports, setReports] = useState({
    insight: '',
    media: '',
    query: ''
  });
  const [reportStatus, setReportStatus] = useState<'idle' | 'thinking' | 'streaming' | 'complete'>('idle');
  const [activeEngine, setActiveEngine] = useState<string | null>(null);

  // SSE Crawler Log Connection
  useEffect(() => {
    let eventSource: EventSource | null = null;
    
    if (isProcessing || taskId) {
      eventSource = new EventSource('http://localhost:5000/api/v1/logs/stream');
      
      eventSource.onmessage = (event) => {
        setLogs(prev => [...prev, event.data]);
        setTimeout(() => {
          logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 50);
      };

      eventSource.onerror = (err) => {
        console.error('SSE Error:', err);
      };
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [isProcessing, taskId]);

  // SSE Report Stream Connection
  useEffect(() => {
    let reportSource: EventSource | null = null;

    if (taskId) {
      setReportStatus('thinking');
      reportSource = new EventSource(`http://localhost:5000/api/v1/report/stream/${taskId}`);
      
      reportSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.status === 'thinking') {
          setReportStatus('thinking');
        } else if (data.status === 'complete') {
          setReportStatus('complete');
          setIsProcessing(false);
          setActiveEngine(null);
          setQrCode(null);
          reportSource?.close();
        } else if (data.status === 'qrcode') {
          setQrCode(data.image);
        } else if (data.status === 'forum') {
          setForumLogs(prev => [...prev, data.content]);
          setTimeout(() => {
            forumEndRef.current?.scrollIntoView({ behavior: 'smooth' });
          }, 50);
        } else if (data.engine) {
          if (reportStatus !== 'streaming') setReportStatus('streaming');
          setActiveEngine(data.engine);
          setReports(prev => ({
            ...prev,
            [data.engine]: prev[data.engine as keyof typeof prev] + data.content
          }));
        }
      };

      reportSource.onerror = (err) => {
        console.error('Report SSE Error:', err);
        reportSource?.close();
      };
    }

    return () => {
      if (reportSource) {
        reportSource.close();
      }
    };
  }, [taskId]);

  const handleStartTask = async () => {
    if (!query.trim()) return;
    
    setIsProcessing(true);
    setTaskId(null);
    setReports({ insight: '', media: '', query: '' });
    setForumLogs([]);
    setReportStatus('idle');
    setLogs([`> 初始化系统，准备全网分析: ${query}`]);
    
    try {
      const response = await fetch('http://localhost:5000/api/v1/task/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      
      const data = await response.json();
      if (data.success) {
        setTaskId(data.task_id);
      } else {
        setLogs(prev => [...prev, `> [ERROR] 任务启动失败: ${data.error}`]);
        setIsProcessing(false);
      }
    } catch (err: any) {
      setLogs(prev => [...prev, `> [ERROR] 网络请求失败: ${err.message}`]);
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col gap-8 w-full max-w-[1440px] mx-auto pb-12">
      
      {/* Header */}
      <header className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-4">
          <div className="p-2.5 bg-surface-containerLowest rounded-xl shadow-[0_8px_24px_-8px_rgba(0,92,184,0.12)]">
            <Activity className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">Analysis Matrix</h1>
            <p className="text-sm font-medium text-onSurface-variant mt-0.5">Real-time Task Execution & Telemetry</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2 px-4 py-2 bg-surface-containerLowest rounded-full text-xs font-semibold tracking-wide text-onSurface-variant shadow-sm">
          <div className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-primary animate-pulse' : 'bg-surface-dim'}`} />
          {isProcessing ? 'SYSTEM ACTIVE' : 'SYSTEM IDLE'}
        </div>
      </header>

      {/* Row 1: Command Input */}
      <div className="bg-surface-containerLowest rounded-2xl p-6 shadow-[0_12px_48px_-12px_rgba(0,0,0,0.06)] relative overflow-hidden">
        <h2 className="text-sm font-semibold text-onSurface-variant flex items-center gap-2 mb-4 uppercase tracking-wider">
          <Search className="w-4 h-4" /> Global Search Override
        </h2>
        
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <input 
              type="text" 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. 达巴：水痕之地"
              className="w-full bg-surface-containerLow border-2 border-transparent rounded-xl py-3.5 px-4 text-base font-medium text-foreground shadow-sm placeholder:text-surface-dim focus:outline-none focus:border-primary/40 transition-all"
              disabled={isProcessing}
              onKeyDown={(e) => e.key === 'Enter' && handleStartTask()}
            />
          </div>
          
          <button 
            onClick={handleStartTask}
            disabled={isProcessing || !query}
            className="md:w-auto w-full px-8 bg-gradient-to-br from-primary to-primary-container text-white disabled:opacity-60 disabled:cursor-not-allowed font-medium py-3.5 rounded-xl flex items-center justify-center gap-2 transition-all active:scale-[0.98] shadow-[0_8px_20px_-8px_rgba(0,92,184,0.5)] hover:shadow-[0_12px_24px_-8px_rgba(0,92,184,0.6)]"
          >
            {isProcessing ? (
              <><Activity className="w-4 h-4 animate-spin" /> Processing...</>
            ) : (
              <><Play className="w-4 h-4" fill="currentColor" /> Initialize Sequence</>
            )}
          </button>
        </div>
      </div>

      {/* Row 2: Logs & Forum */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[280px]">
        {/* Crawler Log */}
        <div className="bg-[#1a1c1c] rounded-2xl flex flex-col overflow-hidden shadow-lg relative h-full">
          <div className="bg-[#242727] px-5 py-2.5 flex items-center justify-between border-b border-white/5">
            <div className="flex items-center gap-2 text-xs font-medium text-surface-dim tracking-wide">
              <Terminal className="w-4 h-4" />
              <span>crawler.log — Data Ingestion Pipeline</span>
            </div>
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-rose-500/80"></div>
              <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80"></div>
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></div>
            </div>
          </div>
          
          <div className="p-5 flex-1 overflow-y-auto text-[12px] font-mono leading-relaxed text-emerald-400/90 selection:bg-emerald-500/30">
            {qrCode && (
              <div className="mb-4 flex flex-col items-center justify-center p-4 bg-white/5 rounded-xl border border-white/10">
                <p className="text-white mb-2 font-bold uppercase tracking-wider text-[10px]">⚠️ ACTION REQUIRED: Scan QR Code to Login</p>
                <img src={`data:image/png;base64,${qrCode}`} alt="Login QR Code" className="w-48 h-48 rounded-lg" />
              </div>
            )}
            {logs.length === 0 ? (
              <span className="text-onSurface-variant italic">Awaiting telemetry...</span>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="mb-1 break-words">
                  {log.includes('[ERROR]') || log.includes('❌') ? (
                    <span className="text-secondary">{log}</span>
                  ) : log.includes('[SYSTEM]') || log.includes('✅') ? (
                    <span className="text-primary-container">{log}</span>
                  ) : (
                    log
                  )}
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* Forum Engine Swarm Panel */}
        <div className="bg-surface-containerLowest rounded-2xl flex flex-col overflow-hidden shadow-[0_12px_48px_-12px_rgba(0,0,0,0.06)] border border-surface-containerLow relative h-full">
          <div className="bg-surface-containerLow/50 px-5 py-3 flex items-center justify-between border-b border-surface-containerLow">
            <div className="flex items-center gap-2 text-sm font-bold text-foreground tracking-tight">
              <Users className="w-4 h-4 text-primary" />
              <span>Agent Swarm / Forum</span>
            </div>
            {reportStatus === 'thinking' && (
              <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-primary">
                <Activity className="w-3 h-3 animate-pulse" /> Discussing
              </span>
            )}
          </div>
          
          <div className="p-5 flex-1 overflow-y-auto text-sm leading-relaxed text-onSurface-variant">
            {forumLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-surface-dim space-y-2">
                <Users className="w-8 h-8 opacity-50" />
                <span className="font-medium text-xs uppercase tracking-wider">Agents are quiet</span>
              </div>
            ) : (
              forumLogs.map((log, i) => {
                const isHost = log.includes('主持人') || log.includes('Host');
                return (
                  <div key={i} className={`mb-3 p-3 rounded-xl text-[13px] ${isHost ? 'bg-primary/5 border border-primary/10 text-primary-container font-medium' : 'bg-surface-containerLow text-onSurface-variant'}`}>
                    <div className="prose prose-sm max-w-none prose-p:my-0 prose-p:leading-snug">
                      <ReactMarkdown>{log}</ReactMarkdown>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={forumEndRef} />
          </div>
        </div>
      </div>

      {/* Row 3: 3 Side-by-Side Engine Report Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Insight Engine */}
        <ReportCard 
          title="Insight Engine" 
          icon={<BrainCircuit className="w-5 h-5 text-primary" />} 
          content={reports.insight} 
          status={reportStatus}
          isActive={activeEngine === 'insight'}
        />
        
        {/* Media Engine */}
        <ReportCard 
          title="Media Engine" 
          icon={<ImageIcon className="w-5 h-5 text-primary" />} 
          content={reports.media} 
          status={reportStatus}
          isActive={activeEngine === 'media'}
        />
        
        {/* Query Engine */}
        <ReportCard 
          title="Query Engine" 
          icon={<Globe className="w-5 h-5 text-primary" />} 
          content={reports.query} 
          status={reportStatus}
          isActive={activeEngine === 'query'}
        />

      </div>
    </div>
  );
}

// Sub-component for Report Cards
function ReportCard({ title, icon, content, status, isActive }: { title: string, icon: React.ReactNode, content: string, status: string, isActive: boolean }) {
  return (
    <div className={`bg-surface-containerLowest rounded-2xl flex flex-col h-[500px] shadow-[0_12px_48px_-12px_rgba(0,0,0,0.06)] relative overflow-hidden transition-all duration-300 ${isActive ? 'ring-2 ring-primary/20 shadow-[0_16px_48px_-12px_rgba(0,92,184,0.15)]' : ''}`}>
      
      {/* Header */}
      <div className="p-5 border-b border-surface-containerLow flex items-center justify-between bg-white/50 backdrop-blur-sm z-10 relative">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-surface-containerLow rounded-lg text-primary">
            {icon}
          </div>
          <h3 className="font-bold tracking-tight text-foreground">{title}</h3>
        </div>
        
        {/* Status Indicator */}
        {status === 'thinking' && (
          <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-onSurface-variant bg-surface-containerLow px-2.5 py-1 rounded-full">
            <Activity className="w-3 h-3 animate-pulse text-primary" />
            Thinking...
          </span>
        )}
        {status === 'streaming' && isActive && (
          <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-primary bg-primary/10 px-2.5 py-1 rounded-full">
            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            Generating
          </span>
        )}
        {status === 'complete' && (
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
            Complete
          </span>
        )}
      </div>

      {/* Content Area */}
      <div className="flex-1 p-6 overflow-y-auto relative bg-gradient-to-b from-transparent to-surface-containerLow/30">
        {status === 'idle' && (
          <div className="absolute inset-0 flex items-center justify-center text-sm font-medium text-surface-dim">
            Awaiting task initialization...
          </div>
        )}
        
        {status === 'thinking' && (
          <div className="space-y-4 animate-pulse">
            <div className="h-4 bg-surface-containerHigh rounded w-3/4"></div>
            <div className="space-y-2">
              <div className="h-3 bg-surface-container rounded w-full"></div>
              <div className="h-3 bg-surface-container rounded w-5/6"></div>
              <div className="h-3 bg-surface-container rounded w-full"></div>
            </div>
            <div className="h-4 bg-surface-containerHigh rounded w-1/2 mt-8"></div>
            <div className="space-y-2">
              <div className="h-3 bg-surface-container rounded w-full"></div>
              <div className="h-3 bg-surface-container rounded w-4/5"></div>
            </div>
          </div>
        )}

        {(status === 'streaming' || status === 'complete') && (
          <div className="prose prose-sm max-w-none prose-zinc prose-headings:font-bold prose-headings:tracking-tight prose-p:leading-relaxed prose-p:text-onSurface-variant prose-strong:text-foreground">
            <ReactMarkdown>{content}</ReactMarkdown>
            {isActive && status === 'streaming' && (
              <span className="inline-block w-1.5 h-4 ml-1 bg-primary animate-pulse align-middle" />
            )}
          </div>
        )}
      </div>
      
    </div>
  );
}
