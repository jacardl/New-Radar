import { useState, useEffect } from 'react';
import { Save, Settings2, Key, ToggleLeft, ToggleRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

interface ConfigState {
  [key: string]: string;
}

const TOOLS = [
  { id: 'anspire', name: 'Anspire', desc: 'Deep knowledge extraction engine', enableKey: 'ENABLE_ANSPIRE', apiKeyKey: 'ANSPIRE_API_KEY' },
  { id: 'bocha', name: 'Bocha', desc: 'Real-time web retrieval', enableKey: 'ENABLE_BOCHA', apiKeyKey: 'BOCHA_WEB_API_KEY' },
  { id: 'firecrawl', name: 'Firecrawl', desc: 'Advanced markdown web crawling', enableKey: 'ENABLE_FIRECRAWL', apiKeyKey: 'FIRECRAWL_API_KEY' },
  { id: 'tavily', name: 'Tavily', desc: 'Search engine optimized for LLMs', enableKey: 'ENABLE_TAVILY', apiKeyKey: 'TAVILY_API_KEY' },
  { id: 'mediacrawler', name: 'MediaCrawler', desc: 'Multi-platform social media scraper', enableKey: 'ENABLE_MEDIACRAWLER', apiKeyKey: null },
  { id: 'web_access', name: 'Web-Access', desc: 'Fallback web retrieval solution', enableKey: 'ENABLE_WEB_ACCESS', apiKeyKey: null },
];

export default function Settings() {
  const [config, setConfig] = useState<ConfigState>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch('http://localhost:5000/api/config')
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setConfig(data.config);
        } else {
          toast.error('Failed to load configuration');
        }
      })
      .catch(() => toast.error('Network error while loading configuration'))
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = (key: string) => {
    setConfig(prev => ({
      ...prev,
      [key]: prev[key] === 'True' ? 'False' : 'True'
    }));
  };

  const handleInputChange = (key: string, value: string) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch('http://localhost:5000/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      const data = await response.json();
      if (data.success) {
        toast.success('保存成功', {
          description: 'Configuration updated and applied to the system.'
        });
        setConfig(data.config);
      } else {
        toast.error(`Save failed: ${data.message}`);
      }
    } catch (err) {
      toast.error('Network error while saving configuration');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-onSurface-variant">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 w-full max-w-[1000px] mx-auto pb-12">
      <header className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <div className="p-2.5 bg-surface-containerLowest rounded-xl shadow-[0_8px_24px_-8px_rgba(0,92,184,0.12)]">
            <Settings2 className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">Configuration</h1>
            <p className="text-sm font-medium text-onSurface-variant mt-0.5">Manage External Search Tools & API Keys</p>
          </div>
        </div>
        
        <button 
          onClick={handleSave}
          disabled={saving}
          className="bg-gradient-to-br from-primary to-primary-container text-white px-6 py-2.5 rounded-xl font-medium flex items-center gap-2 transition-all active:scale-[0.98] shadow-[0_8px_20px_-8px_rgba(0,92,184,0.5)] hover:shadow-[0_12px_24px_-8px_rgba(0,92,184,0.6)] disabled:opacity-70"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Changes
        </button>
      </header>

      <div className="flex flex-col gap-6">
        {TOOLS.map((tool) => {
          const isEnabled = config[tool.enableKey] === 'True';
          
          return (
            <div key={tool.id} className="bg-surface-containerLowest rounded-2xl p-6 shadow-[0_4px_24px_-12px_rgba(0,0,0,0.04)] relative overflow-hidden transition-all border border-transparent hover:border-surface-dim/30">
              <div className="flex items-start justify-between gap-6">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-bold tracking-tight text-foreground">{tool.name}</h3>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider font-bold ${isEnabled ? 'bg-primary/10 text-primary' : 'bg-surface-containerLow text-onSurface-variant'}`}>
                      {isEnabled ? 'Active' : 'Disabled'}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-onSurface-variant leading-relaxed mb-4">{tool.desc}</p>
                  
                  {tool.apiKeyKey && (
                    <div className={`transition-all duration-300 ${isEnabled ? 'opacity-100 h-auto' : 'opacity-40 h-auto'}`}>
                      <label className="text-xs font-bold uppercase tracking-wider text-onSurface-variant flex items-center gap-1.5 mb-2">
                        <Key className="w-3.5 h-3.5" /> API Key
                      </label>
                      <input 
                        type="password" 
                        value={config[tool.apiKeyKey] || ''}
                        onChange={(e) => handleInputChange(tool.apiKeyKey!, e.target.value)}
                        disabled={!isEnabled}
                        placeholder={isEnabled ? "Enter your API key here..." : "Enable tool to set API key"}
                        className="w-full max-w-md bg-surface-containerLow border-2 border-transparent rounded-xl py-2.5 px-4 text-sm text-foreground shadow-sm placeholder:text-surface-dim focus:outline-none focus:border-primary/40 transition-all disabled:cursor-not-allowed"
                      />
                    </div>
                  )}
                </div>

                <div className="pt-1 cursor-pointer" onClick={() => handleToggle(tool.enableKey)}>
                  {isEnabled ? (
                    <ToggleRight className="w-10 h-10 text-primary transition-colors" />
                  ) : (
                    <ToggleLeft className="w-10 h-10 text-surface-dim transition-colors" />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
