import { useState, useEffect } from 'react';
import { FileText, Eye, FileJson, Calendar, Loader2, FileDown } from 'lucide-react';
import { toast } from 'sonner';

interface Report {
  name: string;
  title: string;
  size: number;
  created_at: number;
  html_url: string;
  pdf_url: string;
  md_url: string;
}

export default function History() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/v1/reports');
      const data = await res.json();
      if (data.success) {
        setReports(data.reports);
      } else {
        toast.error('Failed to load reports');
      }
    } catch (err) {
      toast.error('Network error loading reports');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="flex flex-col gap-8 w-full max-w-[1440px] mx-auto pb-12">
      <header className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <div className="p-2.5 bg-surface-containerLowest rounded-xl shadow-[0_8px_24px_-8px_rgba(0,92,184,0.12)]">
            <FileText className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">History Reports</h1>
            <p className="text-sm font-medium text-onSurface-variant mt-0.5">Archive of generated insights and telemetry data</p>
          </div>
        </div>
      </header>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-onSurface-variant">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : reports.length === 0 ? (
        <div className="bg-surface-containerLowest rounded-2xl p-12 text-center shadow-[0_12px_48px_-12px_rgba(0,0,0,0.06)]">
          <div className="mx-auto w-16 h-16 bg-surface-containerLow rounded-full flex items-center justify-center mb-6">
            <FileText className="w-8 h-8 text-surface-dim" />
          </div>
          <h3 className="text-lg font-bold text-foreground mb-2 tracking-tight">No Reports Found</h3>
          <p className="text-sm font-medium text-onSurface-variant leading-relaxed max-w-sm mx-auto">
            Historical reports will appear here once tasks are completed. Try running a new sequence from the Analysis Matrix.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Col: Report List */}
          <div className="lg:col-span-4 flex flex-col gap-4 max-h-[800px] overflow-y-auto pr-2">
            {reports.map((report) => (
              <div 
                key={report.name}
                onClick={() => setPreviewUrl(`http://localhost:5000${report.html_url}`)}
                className={`bg-surface-containerLowest rounded-xl p-5 cursor-pointer transition-all border-2 ${
                  previewUrl?.includes(report.name) 
                    ? 'border-primary/40 shadow-md bg-primary/[0.02]' 
                    : 'border-transparent hover:border-surface-dim/30 shadow-sm'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-1">
                    <FileJson className="w-5 h-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-bold text-foreground mb-1 truncate" title={report.title}>
                      {report.title}
                    </h3>
                    <div className="flex items-center gap-3 text-[11px] text-onSurface-variant font-medium">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {formatDate(report.created_at)}
                      </span>
                      <span>{formatSize(report.size)}</span>
                    </div>
                  </div>
                </div>
                
                <div className="mt-4 pt-3 border-t border-surface-containerLow flex items-center gap-2">
                  <a 
                    href={`http://localhost:5000${report.pdf_url}`}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex-1 bg-surface-containerLow hover:bg-surface-container text-foreground py-1.5 rounded-md flex items-center justify-center gap-1.5 text-xs font-semibold transition-colors"
                  >
                    <FileDown className="w-3.5 h-3.5" /> PDF
                  </a>
                  <a 
                    href={`http://localhost:5000${report.md_url}`}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex-1 bg-surface-containerLow hover:bg-surface-container text-foreground py-1.5 rounded-md flex items-center justify-center gap-1.5 text-xs font-semibold transition-colors"
                  >
                    <FileDown className="w-3.5 h-3.5" /> Markdown
                  </a>
                </div>
              </div>
            ))}
          </div>

          {/* Right Col: Preview Iframe */}
          <div className="lg:col-span-8">
            <div className="bg-surface-containerLowest rounded-2xl border border-surface-containerLow shadow-lg overflow-hidden h-[800px] flex flex-col">
              <div className="bg-surface-containerLow px-4 py-3 border-b border-surface-container flex items-center gap-2">
                <Eye className="w-4 h-4 text-onSurface-variant" />
                <span className="text-xs font-bold uppercase tracking-wider text-onSurface-variant">
                  Interactive Preview
                </span>
              </div>
              
              <div className="flex-1 bg-white relative">
                {previewUrl ? (
                  <iframe 
                    src={previewUrl} 
                    className="w-full h-full border-none"
                    title="Report Preview"
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-sm font-medium text-surface-dim">
                    Select a report from the list to preview
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
