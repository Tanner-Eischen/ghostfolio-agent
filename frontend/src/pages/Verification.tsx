import { useEffect, useState } from 'react';
import { verificationApi } from '../api/client';
import type { VerificationConfig } from '../api/client';

const defaultConfig: VerificationConfig = {
  fact_checking: true,
  hallucination_detection: true,
  confidence_scoring: true,
  hitl_enabled: false,
  confidence_threshold: 70,
};

export function Verification() {
  const [config, setConfig] = useState<VerificationConfig>(defaultConfig);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    async function fetchConfig() {
      try {
        const data = await verificationApi.getConfig();
        setConfig(data);
      } catch (error) {
        console.error('Failed to fetch config:', error);
      }
    }
    fetchConfig();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await verificationApi.saveConfig(config);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save:', error);
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = <K extends keyof VerificationConfig>(key: K, value: VerificationConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  return (
    <main className="flex-1 px-6 md:px-10 py-8 overflow-y-auto">
      <div className="mx-auto max-w-[900px]">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-2 text-sm">
            <span className="text-text-dim hover:text-primary transition-colors cursor-pointer">Home</span>
            <span className="text-surface-border">/</span>
            <span className="text-white font-medium">Verification Layer</span>
          </div>
          <h1 className="text-white text-3xl font-black mb-2">Verification & HITL Configuration</h1>
          <p className="text-text-dim text-lg">
            Configure automated verification checks and human-in-the-loop triggers to ensure response quality.
          </p>
        </div>

        {/* Verification Toggles */}
        <section className="rounded-xl border border-surface-border bg-surface-dark overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-surface-border bg-surface-darker">
            <h3 className="text-white text-lg font-bold flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">verified_user</span>
              Verification Layers
            </h3>
          </div>
          <div className="p-6 space-y-6">
            {/* Fact Checking */}
            <div className="flex items-center justify-between p-4 rounded-lg bg-surface-darker border border-surface-border">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-emerald-500/20 text-emerald-400">
                  <span className="material-symbols-outlined">fact_check</span>
                </div>
                <div>
                  <h4 className="text-white font-semibold">Fact Checking</h4>
                  <p className="text-sm text-text-dim">Verify claims against trusted data sources</p>
                </div>
              </div>
              <label className="relative inline-flex h-6 w-11 items-center rounded-full bg-surface-border cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.fact_checking}
                  onChange={(e) => updateConfig('fact_checking', e.target.checked)}
                  className="peer sr-only"
                />
                <span className={`h-4 w-4 transform rounded-full bg-white transition-transform ${config.fact_checking ? 'translate-x-6 bg-primary' : 'translate-x-1'}`} />
              </label>
            </div>

            {/* Hallucination Detection */}
            <div className="flex items-center justify-between p-4 rounded-lg bg-surface-darker border border-surface-border">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-amber-500/20 text-amber-400">
                  <span className="material-symbols-outlined">psychology_alt</span>
                </div>
                <div>
                  <h4 className="text-white font-semibold">Hallucination Detection</h4>
                  <p className="text-sm text-text-dim">Flag responses with potential fabricated information</p>
                </div>
              </div>
              <label className="relative inline-flex h-6 w-11 items-center rounded-full bg-surface-border cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.hallucination_detection}
                  onChange={(e) => updateConfig('hallucination_detection', e.target.checked)}
                  className="peer sr-only"
                />
                <span className={`h-4 w-4 transform rounded-full bg-white transition-transform ${config.hallucination_detection ? 'translate-x-6 bg-primary' : 'translate-x-1'}`} />
              </label>
            </div>

            {/* Confidence Scoring */}
            <div className="flex items-center justify-between p-4 rounded-lg bg-surface-darker border border-surface-border">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-blue-500/20 text-blue-400">
                  <span className="material-symbols-outlined">speed</span>
                </div>
                <div>
                  <h4 className="text-white font-semibold">Confidence Scoring</h4>
                  <p className="text-sm text-text-dim">Calculate and report confidence levels for each response</p>
                </div>
              </div>
              <label className="relative inline-flex h-6 w-11 items-center rounded-full bg-surface-border cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.confidence_scoring}
                  onChange={(e) => updateConfig('confidence_scoring', e.target.checked)}
                  className="peer sr-only"
                />
                <span className={`h-4 w-4 transform rounded-full bg-white transition-transform ${config.confidence_scoring ? 'translate-x-6 bg-primary' : 'translate-x-1'}`} />
              </label>
            </div>
          </div>
        </section>

        {/* HITL Configuration */}
        <section className="rounded-xl border border-surface-border bg-surface-dark overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-surface-border bg-surface-darker">
            <h3 className="text-white text-lg font-bold flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">support_agent</span>
              Human-in-the-Loop (HITL)
            </h3>
          </div>
          <div className="p-6 space-y-6">
            {/* HITL Toggle */}
            <div className="flex items-center justify-between p-4 rounded-lg bg-surface-darker border border-surface-border">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-purple-500/20 text-purple-400">
                  <span className="material-symbols-outlined">contact_support</span>
                </div>
                <div>
                  <h4 className="text-white font-semibold">Enable HITL Triggers</h4>
                  <p className="text-sm text-text-dim">Route low-confidence responses to human review queue</p>
                </div>
              </div>
              <label className="relative inline-flex h-6 w-11 items-center rounded-full bg-surface-border cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.hitl_enabled}
                  onChange={(e) => updateConfig('hitl_enabled', e.target.checked)}
                  className="peer sr-only"
                />
                <span className={`h-4 w-4 transform rounded-full bg-white transition-transform ${config.hitl_enabled ? 'translate-x-6 bg-primary' : 'translate-x-1'}`} />
              </label>
            </div>

            {/* Confidence Threshold */}
            <div className="p-4 rounded-lg bg-surface-darker border border-surface-border">
              <div className="flex justify-between items-center mb-3">
                <div>
                  <h4 className="text-white font-semibold">Confidence Threshold</h4>
                  <p className="text-sm text-text-dim">Responses below this score trigger HITL review</p>
                </div>
                <span className="text-2xl font-bold text-primary">{config.confidence_threshold}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={config.confidence_threshold}
                onChange={(e) => updateConfig('confidence_threshold', parseInt(e.target.value))}
                className="w-full h-2 bg-surface-border rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between text-xs text-text-dim mt-2">
                <span>Relaxed (0%)</span>
                <span>Balanced (50%)</span>
                <span>Strict (100%)</span>
              </div>
            </div>
          </div>
        </section>

        {/* Save Button */}
        <div className="flex justify-end gap-3">
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-text-dim bg-surface-dark border border-surface-border rounded-lg hover:text-white hover:border-text-dim transition-all">
            <span className="material-symbols-outlined text-lg">restart_alt</span>
            Reset to Defaults
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className={`flex items-center gap-2 px-6 py-2 text-sm font-medium rounded-lg transition-all ${
              saved
                ? 'bg-emerald-500 text-white'
                : 'bg-primary text-background-dark hover:bg-primary-hover'
            }`}
          >
            <span className="material-symbols-outlined text-lg">
              {saved ? 'check_circle' : 'save'}
            </span>
            {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>
    </main>
  );
}
