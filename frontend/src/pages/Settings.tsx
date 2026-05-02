import { useState, useEffect } from 'react';
import { Save, Activity, Eye, EyeOff } from 'lucide-react';
import { API_BASE } from '../config';

export default function Settings() {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [pingStatus, setPingStatus] = useState<{status: 'idle'|'testing'|'success'|'error', latency?: number}>({ status: 'idle' });

  useEffect(() => {
    const key = localStorage.getItem('API_KEY');
    if (key) setApiKey(key);
  }, []);

  const handleSave = () => {
    localStorage.setItem('API_KEY', apiKey);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const testConnection = async () => {
    setPingStatus({ status: 'testing' });
    const start = Date.now();
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        setPingStatus({ status: 'success', latency: Date.now() - start });
      } else {
        setPingStatus({ status: 'error' });
      }
    } catch {
      setPingStatus({ status: 'error' });
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Platform Settings</h2>
        <p className="text-slate-400">Configure your local connection to the Archon orchestration backend.</p>
      </div>
      
      <div className="glass-card rounded-xl border border-white/5 p-8">
        <h3 className="text-lg font-semibold text-[#00ff9f] mb-6 flex items-center gap-2">
          <span className="w-8 h-px bg-[#00ff9f]/30"></span>
          Authentication
        </h3>
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-mono tracking-widest text-slate-400 uppercase mb-2">
              API Key (X-Api-Key)
            </label>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-lg pl-4 pr-12 py-3 text-white font-mono placeholder-slate-600 focus:outline-none focus:border-[#7c3aed] focus:shadow-[0_0_15px_rgba(124,58,237,0.2)] transition-all"
                placeholder="Enter 32-byte secret key"
              />
              <button 
                onClick={() => setShowKey(!showKey)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
              >
                {showKey ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500 font-mono">
              Stored locally in browser localStorage.
            </p>
          </div>
          
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-6 py-3 bg-[#7c3aed] text-white rounded-lg hover:bg-[#6d28d9] transition-colors font-medium shadow-[0_0_20px_rgba(124,58,237,0.3)]"
          >
            <Save size={18} />
            {saved ? 'Configuration Saved' : 'Save Configuration'}
          </button>
        </div>
      </div>

      <div className="glass-card rounded-xl border border-white/5 p-8">
        <h3 className="text-lg font-semibold text-[#7c3aed] mb-6 flex items-center gap-2">
          <span className="w-8 h-px bg-[#7c3aed]/30"></span>
          Diagnostics
        </h3>
        
        <div className="space-y-6">
          <div className="flex items-center justify-between p-4 bg-black/40 border border-white/5 rounded-lg">
            <div>
              <p className="text-sm font-medium text-slate-300">Backend API</p>
              <p className="text-xs text-slate-500 font-mono mt-1">{API_BASE}</p>
            </div>
            <div className="flex items-center gap-4">
              {pingStatus.status === 'success' && <span className="text-[#00ff9f] text-sm font-mono">{pingStatus.latency}ms</span>}
              {pingStatus.status === 'error' && <span className="text-red-400 text-sm font-mono">Offline</span>}
              <button 
                onClick={testConnection}
                disabled={pingStatus.status === 'testing'}
                className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 text-white rounded-lg transition-colors text-sm border border-white/10"
              >
                <Activity size={16} className={pingStatus.status === 'testing' ? 'animate-pulse text-[#00ff9f]' : ''} />
                Ping
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
