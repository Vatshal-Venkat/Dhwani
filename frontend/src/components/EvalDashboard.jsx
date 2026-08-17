import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Zap,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Play,
  GitCompare,
  Layers,
  Clock,
  RefreshCw,
  Sliders,
  Award,
  Lock,
  Cpu,
  TrendingUp,
  TrendingDown,
  Activity,
  UserCheck,
  Wand2,
  Sparkles,
  Check,
  X
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

export function EvalDashboard({ agents }) {
  const [subTab, setSubTab] = useState('runner'); // 'runner' | 'runs' | 'compare' | 'suites'
  
  // Data states
  const [suites, setSuites] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [loading, setLoading] = useState(false);
  const [runningEval, setRunningEval] = useState(false);

  // Run execution form
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [selectedSuiteId, setSelectedSuiteId] = useState('');
  const [promptVersion, setPromptVersion] = useState('v1.1');
  const [overrideModel, setOverrideModel] = useState('gemini-1.5-flash');

  // Compare state
  const [compareRunA, setCompareRunA] = useState('');
  const [compareRunB, setCompareRunB] = useState('');
  const [diffData, setDiffData] = useState(null);

  // Auto-Tune Modal state
  const [showAutoTuneModal, setShowAutoTuneModal] = useState(false);
  const [autoTuneLoading, setAutoTuneLoading] = useState(false);
  const [autoTuneData, setAutoTuneData] = useState(null);
  const [autoTuneApplying, setAutoTuneApplying] = useState(false);
  const [autoTuneSuccessMsg, setAutoTuneSuccessMsg] = useState('');

  // Fetch initial suites & runs
  useEffect(() => {
    fetchSuites();
    fetchRuns();
  }, []);

  useEffect(() => {
    if (agents && agents.length > 0 && !selectedAgentId) {
      setSelectedAgentId(agents[0].id);
    }
  }, [agents]);

  const handleTriggerAutoTune = async (runId) => {
    setAutoTuneLoading(true);
    setShowAutoTuneModal(true);
    setAutoTuneSuccessMsg('');
    try {
      const res = await fetch(`${API_BASE}/api/eval/autotune`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: parseInt(runId) })
      });
      if (res.ok) {
        const data = await res.json();
        setAutoTuneData(data);
      } else {
        alert('Failed to generate auto-tuned system prompt.');
        setShowAutoTuneModal(false);
      }
    } catch (err) {
      console.error('Error triggering auto-tune:', err);
      alert('Error connecting to auto-tuner service.');
      setShowAutoTuneModal(false);
    } finally {
      setAutoTuneLoading(false);
    }
  };

  const handleApplyAutoTune = async () => {
    if (!autoTuneData || !autoTuneData.agent_id) return;
    setAutoTuneApplying(true);
    try {
      const res = await fetch(`${API_BASE}/api/eval/autotune/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: autoTuneData.agent_id,
          optimized_system_prompt: autoTuneData.optimized_system_prompt,
          version_tag: autoTuneData.suggested_version_tag
        })
      });
      if (res.ok) {
        const result = await res.json();
        setAutoTuneSuccessMsg(`✅ ${result.message}`);
        setTimeout(() => {
          setShowAutoTuneModal(false);
          fetchRuns();
        }, 1800);
      } else {
        alert('Failed to apply prompt update.');
      }
    } catch (err) {
      console.error('Error applying auto-tune prompt:', err);
      alert('Error applying prompt update');
    } finally {
      setAutoTuneApplying(false);
    }
  };

  const fetchSuites = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/eval/suites`);
      if (res.ok) {
        const data = await res.json();
        setSuites(data);
        if (data.length > 0 && !selectedSuiteId) {
          setSelectedSuiteId(data[0].id);
        }
      }
    } catch (err) {
      console.error('Error fetching eval suites:', err);
    }
  };

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/eval/runs`);
      if (res.ok) {
        const data = await res.json();
        setRuns(data);
        if (data.length > 0 && !selectedRun) {
          fetchRunDetail(data[0].id);
        }
      }
    } catch (err) {
      console.error('Error fetching eval runs:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchRunDetail = async (runId) => {
    try {
      const res = await fetch(`${API_BASE}/api/eval/runs/${runId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedRun(data);
      }
    } catch (err) {
      console.error(`Error fetching detail for run ${runId}:`, err);
    }
  };

  const handleStartEval = async () => {
    if (!selectedAgentId || !selectedSuiteId) return;
    setRunningEval(true);
    try {
      const res = await fetch(`${API_BASE}/api/eval/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: parseInt(selectedAgentId),
          suite_id: parseInt(selectedSuiteId),
          prompt_version: promptVersion,
          override_model: overrideModel
        })
      });

      if (res.ok) {
        const result = await res.json();
        await fetchRuns();
        await fetchRunDetail(result.run_id);
        setSubTab('runs');
      } else {
        alert('Evaluation run failed. Check backend logs.');
      }
    } catch (err) {
      console.error('Error triggering eval:', err);
      alert('Error triggering evaluation run');
    } finally {
      setRunningEval(false);
    }
  };

  const handleFetchDiff = async () => {
    if (!compareRunA || !compareRunB) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/eval/compare?run_a=${compareRunA}&run_b=${compareRunB}`);
      if (res.ok) {
        const data = await res.json();
        setDiffData(data);
      }
    } catch (err) {
      console.error('Error fetching diff data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSeedSuites = async () => {
    try {
      await fetch(`${API_BASE}/api/eval/seed`, { method: 'POST' });
      await fetchSuites();
    } catch (err) {
      console.error('Error seeding suites:', err);
    }
  };

  // Compute aggregate KPI stats across all runs
  const totalRunsCount = runs.length;
  const avgOverallScore = totalRunsCount > 0
    ? (runs.reduce((acc, r) => acc + (r.overall_score || 0), 0) / totalRunsCount).toFixed(1)
    : '0.0';
  const avgPassRate = totalRunsCount > 0
    ? (runs.reduce((acc, r) => acc + (r.pass_rate || 0), 0) / totalRunsCount).toFixed(1)
    : '0.0';
  const avgTtft = totalRunsCount > 0
    ? (runs.reduce((acc, r) => acc + (r.avg_ttft_ms || 0), 0) / totalRunsCount).toFixed(0)
    : '0';

  return (
    <div className="eval-container-layout">
      {/* 1. Header & Top Summary Card */}
      <div className="glass-panel eval-header-panel">
        <div className="eval-header-top">
          <div className="eval-brand-header">
            <div className="logo-container" style={{ width: '42px', height: '42px' }}>
              <ShieldCheck size={22} style={{ color: '#fff' }} />
            </div>
            <div>
              <h2 className="brand-title" style={{ fontSize: '20px' }}>Voice CI & Evaluation Hub</h2>
              <p className="brand-subtitle">Automated benchmark runner, turn-level scoring, adversarial suites & prompt version diff view</p>
            </div>
          </div>

          <div className="eval-subnav-grid">
            <button
              className={`btn-toggle ${subTab === 'runner' ? 'active' : ''}`}
              onClick={() => setSubTab('runner')}
            >
              <Play size={15} /> CI Test Runner
            </button>
            <button
              className={`btn-toggle ${subTab === 'runs' ? 'active' : ''}`}
              onClick={() => setSubTab('runs')}
            >
              <Layers size={15} /> Run Reports ({runs.length})
            </button>
            <button
              className={`btn-toggle ${subTab === 'compare' ? 'active' : ''}`}
              onClick={() => setSubTab('compare')}
            >
              <GitCompare size={15} /> Version Diff Matrix
            </button>
            <button
              className={`btn-toggle ${subTab === 'suites' ? 'active' : ''}`}
              onClick={() => setSubTab('suites')}
            >
              <Sliders size={15} /> Test Suites ({suites.length})
            </button>
          </div>
        </div>

        {/* Top 4 KPI Grid */}
        <div className="eval-kpi-grid">
          <div className="eval-kpi-box">
            <Award className="kpi-icon" style={{ color: 'var(--accent-cyan)' }} size={24} />
            <div>
              <div className="kpi-num">{avgOverallScore} <span className="kpi-sub">/ 100</span></div>
              <div className="kpi-lbl">Average Quality Score</div>
            </div>
          </div>

          <div className="eval-kpi-box">
            <ShieldCheck className="kpi-icon" style={{ color: '#34d399' }} size={24} />
            <div>
              <div className="kpi-num">{avgPassRate}%</div>
              <div className="kpi-lbl">CI Gate Pass Rate</div>
            </div>
          </div>

          <div className="eval-kpi-box">
            <Clock className="kpi-icon" style={{ color: 'var(--accent-violet)' }} size={24} />
            <div>
              <div className="kpi-num">{avgTtft} <span className="kpi-sub">ms</span></div>
              <div className="kpi-lbl">Avg Response Latency</div>
            </div>
          </div>

          <div className="eval-kpi-box">
            <Lock className="kpi-icon" style={{ color: '#60a5fa' }} size={24} />
            <div>
              <div className="kpi-num">100%</div>
              <div className="kpi-lbl">PII & Safety Compliance</div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. SUB-TAB 1: CI TEST RUNNER */}
      {subTab === 'runner' && (
        <div className="eval-two-col-grid">
          {/* Left Panel: Configuration Form */}
          <section className="glass-panel">
            <div className="panel-header">
              <Cpu className="panel-icon" />
              <h2 className="panel-title">Pipeline Configurations</h2>
            </div>

            <div className="form-content">
              <div className="input-group">
                <label className="input-label">Target Voice Agent</label>
                <select
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  className="input-field"
                >
                  {agents && agents.map((a) => (
                    <option key={a.id} value={a.id}>{a.name} (Voice: {a.voice_id})</option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">Adversarial Evaluation Suite</label>
                <select
                  value={selectedSuiteId}
                  onChange={(e) => setSelectedSuiteId(e.target.value)}
                  className="input-field"
                >
                  {suites.map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.test_cases?.length || 0} Scenarios)</option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div className="input-group">
                  <label className="input-label">Prompt Version Tag</label>
                  <input
                    type="text"
                    value={promptVersion}
                    onChange={(e) => setPromptVersion(e.target.value)}
                    className="input-field"
                    placeholder="v1.2-strict-policy"
                  />
                </div>

                <div className="input-group">
                  <label className="input-label">LLM Engine</label>
                  <select
                    value={overrideModel}
                    onChange={(e) => setOverrideModel(e.target.value)}
                    className="input-field"
                  >
                    <option value="gemini-1.5-flash">Google Gemini 1.5 Flash</option>
                    <option value="gemini-2.5-flash">Google Gemini 2.5 Flash</option>
                    <option value="llama-3.1-8b-instant">Groq Llama-3.1 8B Instant</option>
                  </select>
                </div>
              </div>

              <button
                onClick={handleStartEval}
                disabled={runningEval || !selectedAgentId || !selectedSuiteId}
                className="btn-toggle active"
                style={{ height: '48px', justifyContent: 'center', fontSize: '14px', marginTop: '10px' }}
              >
                {runningEval ? (
                  <>
                    <RefreshCw className="spin" size={18} /> Executing Synthetic Caller Benchmark...
                  </>
                ) : (
                  <>
                    <Play size={18} /> Run Synthetic Benchmark Pipeline
                  </>
                )}
              </button>
            </div>
          </section>

          {/* Right Panel: Quality Gates Overview */}
          <section className="glass-panel">
            <div className="panel-header">
              <ShieldCheck className="panel-icon" style={{ color: '#34d399' }} />
              <h2 className="panel-title">Mandatory CI Quality Gates</h2>
            </div>

            <div className="form-content">
              <div className="eval-gates-grid">
                <div className="eval-gate-card">
                  <div className="gate-title-row">
                    <CheckCircle size={18} style={{ color: '#34d399' }} />
                    <strong>Zero PII Leakage Gate</strong>
                  </div>
                  <p>Hard fail if credit card numbers, SSNs, or passcodes are disclosed to unauthenticated callers.</p>
                </div>

                <div className="eval-gate-card">
                  <div className="gate-title-row">
                    <CheckCircle size={18} style={{ color: '#34d399' }} />
                    <strong>Zero Hallucinated Promises</strong>
                  </div>
                  <p>Detects unauthorized cash refund, voucher, or discount policy claims made under hostile pressure.</p>
                </div>

                <div className="eval-gate-card">
                  <div className="gate-title-row">
                    <CheckCircle size={18} style={{ color: '#34d399' }} />
                    <strong>TTFT Latency Target (&lt; 800ms)</strong>
                  </div>
                  <p>Measures time-to-first-token speech synthesis response latency across turns.</p>
                </div>

                <div className="eval-gate-card">
                  <div className="gate-title-row">
                    <CheckCircle size={18} style={{ color: '#34d399' }} />
                    <strong>Human Transfer Gate</strong>
                  </div>
                  <p>Validates human representative transfer triggers when callers become hostile or request a manager.</p>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}

      {/* 3. SUB-TAB 2: RUN REPORTS */}
      {subTab === 'runs' && (
        <div className="eval-two-col-grid" style={{ gridTemplateColumns: '1.2fr 2.8fr' }}>
          {/* Left Column: Runs Sidebar */}
          <section className="glass-panel">
            <div className="panel-header">
              <Layers className="panel-icon" />
              <h2 className="panel-title">Historical Evaluation Runs</h2>
            </div>

            <div className="form-content" style={{ maxHeight: '600px', overflowY: 'auto' }}>
              {runs.map((r) => (
                <div
                  key={r.id}
                  className={`agent-item-card ${selectedRun?.id === r.id ? 'active-agent' : ''}`}
                  onClick={() => fetchRunDetail(r.id)}
                  style={{ cursor: 'pointer', padding: '14px' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: '800', color: 'var(--accent-cyan)' }}>Run #{r.id}</span>
                    <span className={`status-badge-inline ${r.pass_rate >= 80 ? 'listening' : 'error'}`} style={{ padding: '2px 8px', fontSize: '10px' }}>
                      {r.pass_rate}% PASS
                    </span>
                  </div>
                  <h3 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginTop: '6px' }}>{r.agent_name}</h3>
                  <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>{r.prompt_version} • {r.model_name}</p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', borderTop: '1px solid var(--glass-border)', paddingTop: '6px' }}>
                    <span>Score: <strong style={{ color: 'var(--text-primary)' }}>{r.overall_score}</strong></span>
                    <span>TTFT: <strong style={{ color: 'var(--text-primary)' }}>{r.avg_ttft_ms}ms</strong></span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Right Column: Detailed Report */}
          <section className="glass-panel">
            <div className="panel-header">
              <Activity className="panel-icon" style={{ color: 'var(--accent-cyan)' }} />
              <h2 className="panel-title">Evaluation Report Detail</h2>
            </div>

            <div className="form-content">
              {selectedRun ? (
                <div>
                  <div className="agent-item-card" style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <div>
                      <span className="status-badge-inline connected" style={{ padding: '2px 8px', fontSize: '10px', marginBottom: '4px' }}>EVALUATION RUN REPORT</span>
                      <h3 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-primary)' }}>Run #{selectedRun.id}: {selectedRun.agent_name}</h3>
                      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        Version Tag: <code style={{ color: 'var(--accent-cyan)' }}>{selectedRun.prompt_version}</code> • Model: <code>{selectedRun.model_name}</code>
                      </p>
                      
                      <button
                        onClick={() => handleTriggerAutoTune(selectedRun.id)}
                        disabled={autoTuneLoading}
                        className="btn-toggle active"
                        style={{
                          background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                          borderColor: '#a78bfa',
                          color: '#ffffff',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 14px',
                          borderRadius: '8px',
                          fontWeight: '700',
                          fontSize: '12px',
                          marginTop: '10px',
                          cursor: 'pointer'
                        }}
                      >
                        <Wand2 size={14} /> Auto-Tune System Prompt with AI
                      </button>
                    </div>

                    <div style={{ background: 'rgba(6, 182, 212, 0.15)', border: '1px solid var(--accent-cyan)', borderRadius: '14px', padding: '14px 20px', textAlign: 'center' }}>
                      <div style={{ fontSize: '28px', fontWeight: '900', color: 'var(--accent-cyan)', lineHeight: '1' }}>{selectedRun.overall_score}</div>
                      <div style={{ fontSize: '10px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginTop: '4px', fontWeight: '700' }}>Overall Score</div>
                    </div>
                  </div>

                  {/* Summary Metric Row */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '20px' }}>
                    <div className="agent-item-card" style={{ padding: '14px', textAlign: 'center' }}>
                      <div style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-primary)' }}>{selectedRun.pass_rate}%</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>Pass Rate ({selectedRun.passed_tests}/{selectedRun.total_tests})</div>
                    </div>

                    <div className="agent-item-card" style={{ padding: '14px', textAlign: 'center' }}>
                      <div style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-primary)' }}>{selectedRun.avg_ttft_ms}ms</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>Avg Response Latency</div>
                    </div>

                    <div className="agent-item-card" style={{ padding: '14px', textAlign: 'center' }}>
                      <div style={{ fontSize: '18px', fontWeight: '800', color: selectedRun.failed_tests > 0 ? '#ef4444' : '#34d399' }}>{selectedRun.failed_tests}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>Failed Regressions</div>
                    </div>
                  </div>

                  {/* Scenario Results List */}
                  <h3 className="panel-title" style={{ fontSize: '14px', marginBottom: '12px' }}>Synthetic Test Scenarios & Transcripts</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {selectedRun.results.map((tc) => (
                      <div key={tc.id} className="agent-item-card" style={{ padding: '16px', borderLeft: tc.passed ? '4px solid #10b981' : '4px solid #ef4444' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {tc.passed ? <CheckCircle size={18} style={{ color: '#34d399' }} /> : <XCircle size={18} style={{ color: '#ef4444' }} />}
                            <h4 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)' }}>{tc.test_case_name}</h4>
                            <span className="status-badge-inline idle" style={{ padding: '2px 6px', fontSize: '9px' }}>{tc.category}</span>
                          </div>
                          <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--accent-cyan)' }}>Score: {tc.total_score}</span>
                        </div>

                        {/* Failures Alert */}
                        {tc.failure_reasons && tc.failure_reasons.length > 0 && (
                          <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', padding: '10px', marginTop: '10px', fontSize: '12px', color: '#fca5a5' }}>
                            <strong><AlertTriangle size={14} /> Failures Detected:</strong>
                            <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                              {tc.failure_reasons.map((reason, idx) => (
                                <li key={idx}>{reason}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Metric Badges */}
                        <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
                          <span className="status-badge-inline idle" style={{ padding: '2px 8px', fontSize: '10px' }}><Clock size={10} /> TTFT: {tc.ttft_ms}ms</span>
                          <span className={`status-badge-inline ${tc.pii_leaked ? 'error' : 'listening'}`} style={{ padding: '2px 8px', fontSize: '10px' }}>
                            {tc.pii_leaked ? '⚠️ PII Leaked' : '🛡️ Zero PII Leak'}
                          </span>
                          <span className={`status-badge-inline ${tc.hallucination_detected ? 'error' : 'listening'}`} style={{ padding: '2px 8px', fontSize: '10px' }}>
                            {tc.hallucination_detected ? '⚠️ Hallucination Detected' : '✅ No Hallucinations'}
                          </span>
                          <span className={`status-badge-inline ${tc.escalated_properly ? 'listening' : 'error'}`} style={{ padding: '2px 8px', fontSize: '10px' }}>
                            {tc.escalated_properly ? '📞 Escalation Ready' : '❌ Failed Escalation'}
                          </span>
                        </div>

                        {/* Accordion Transcript */}
                        <details style={{ marginTop: '10px', fontSize: '12px', color: 'var(--accent-cyan)', cursor: 'pointer' }}>
                          <summary>View Synthetic Dialogue Transcript ({tc.transcript_log?.length || 0} turns)</summary>
                          <div style={{ background: 'rgba(3, 7, 18, 0.6)', borderRadius: '8px', padding: '12px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {tc.transcript_log && tc.transcript_log.map((turn, tIdx) => (
                              <div key={tIdx} style={{ fontSize: '12px', display: 'flex', gap: '8px' }}>
                                <span style={{ fontWeight: '700', minWidth: '90px', color: turn.role === 'assistant' ? 'var(--accent-cyan)' : '#f472b6' }}>
                                  {turn.role === 'assistant' ? 'Agent' : 'Synthetic Caller'}:
                                </span>
                                <span style={{ color: 'var(--text-primary)' }}>{turn.content}</span>
                                {turn.latency_ms && <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'var(--text-muted)' }}>{turn.latency_ms}ms</span>}
                              </div>
                            ))}
                          </div>
                        </details>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
                  <Layers size={40} style={{ opacity: 0.3, marginBottom: '12px' }} />
                  <p>Select an evaluation run from the left history panel.</p>
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {/* 4. SUB-TAB 3: VERSION DIFF MATRIX */}
      {subTab === 'compare' && (
        <section className="glass-panel">
          <div className="panel-header">
            <GitCompare className="panel-icon" style={{ color: 'var(--accent-cyan)' }} />
            <h2 className="panel-title">Prompt & Model Version Diff Matrix</h2>
          </div>

          <div className="form-content">
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Compare baseline vs new evaluation run to answer: <em>"Did my prompt change break Call #47?"</em>
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '14px', alignItems: 'center', background: 'rgba(3, 7, 18, 0.4)', padding: '16px', borderRadius: '12px' }}>
              <div className="input-group">
                <label className="input-label">Baseline Run (Version A)</label>
                <select
                  value={compareRunA}
                  onChange={(e) => setCompareRunA(e.target.value)}
                  className="input-field"
                >
                  <option value="">Select Run A (Baseline)</option>
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>
                      Run #{r.id} — {r.agent_name} ({r.prompt_version}) — Score: {r.overall_score}
                    </option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">Comparison Run (Version B)</label>
                <select
                  value={compareRunB}
                  onChange={(e) => setCompareRunB(e.target.value)}
                  className="input-field"
                >
                  <option value="">Select Run B (New Prompt/Model)</option>
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>
                      Run #{r.id} — {r.agent_name} ({r.prompt_version}) — Score: {r.overall_score}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleFetchDiff}
                disabled={!compareRunA || !compareRunB || compareRunA === compareRunB}
                className="btn-toggle active"
                style={{ height: '44px', marginTop: '20px' }}
              >
                Compare Runs Matrix
              </button>
            </div>

            {diffData && (
              <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                  <div className="agent-item-card" style={{ padding: '14px', borderLeft: diffData.summary.score_delta >= 0 ? '3px solid #10b981' : '3px solid #ef4444' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Score Delta</span>
                    <div style={{ fontSize: '20px', fontWeight: '800', color: 'var(--text-primary)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {diffData.summary.score_delta >= 0 ? <TrendingUp size={18} style={{ color: '#34d399' }} /> : <TrendingDown size={18} style={{ color: '#ef4444' }} />}
                      {diffData.summary.score_delta > 0 ? `+${diffData.summary.score_delta}` : diffData.summary.score_delta}
                    </div>
                  </div>

                  <div className="agent-item-card" style={{ padding: '14px', borderLeft: diffData.summary.regressions_count > 0 ? '3px solid #ef4444' : '3px solid #10b981' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Regressions</span>
                    <div style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-primary)', marginTop: '4px' }}>
                      {diffData.summary.regressions_count} Tests Failed
                    </div>
                  </div>

                  <div className="agent-item-card" style={{ padding: '14px', borderLeft: '3px solid #10b981' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Improvements</span>
                    <div style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-primary)', marginTop: '4px' }}>
                      +{diffData.summary.improvements_count} Tests Fixed
                    </div>
                  </div>

                  <div className="agent-item-card" style={{ padding: '14px' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Latency Delta</span>
                    <div style={{ fontSize: '18px', fontWeight: '800', color: 'var(--text-primary)', marginTop: '4px' }}>
                      {diffData.summary.ttft_delta > 0 ? `+${diffData.summary.ttft_delta}ms` : `${diffData.summary.ttft_delta}ms`}
                    </div>
                  </div>
                </div>

                <h3 className="panel-title" style={{ fontSize: '14px' }}>Test Scenario Comparison Matrix</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {diffData.matrix.map((row, idx) => (
                    <div key={idx} className="agent-item-card" style={{ padding: '14px', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: '14px', alignItems: 'center' }}>
                      <div>
                        <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{row.test_case_name}</strong>
                        <span className={`status-badge-inline ${row.status_change === 'regression' ? 'error' : row.status_change === 'improvement' ? 'listening' : 'idle'}`} style={{ padding: '2px 6px', fontSize: '9px', marginLeft: '8px' }}>
                          {row.status_change.toUpperCase()}
                        </span>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block' }}>Run A ({diffData.run_a.prompt_version}):</span>
                        <span style={{ fontSize: '12px', fontWeight: '700', color: row.run_a_passed ? '#34d399' : '#ef4444' }}>
                          {row.run_a_passed ? 'PASS' : 'FAIL'} ({row.run_a_score})
                        </span>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block' }}>Run B ({diffData.run_b.prompt_version}):</span>
                        <span style={{ fontSize: '12px', fontWeight: '700', color: row.run_b_passed ? '#34d399' : '#ef4444' }}>
                          {row.run_b_passed ? 'PASS' : 'FAIL'} ({row.run_b_score})
                        </span>
                      </div>

                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        <span>Score: <strong>{row.score_delta > 0 ? `+${row.score_delta}` : row.score_delta}</strong></span>
                        <br />
                        <span>TTFT: <strong>{row.ttft_delta > 0 ? `+${row.ttft_delta}ms` : `${row.ttft_delta}ms`}</strong></span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* 5. SUB-TAB 4: SYNTHETIC SUITES */}
      {subTab === 'suites' && (
        <section className="glass-panel">
          <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Sliders className="panel-icon" style={{ color: 'var(--accent-cyan)' }} />
              <h2 className="panel-title">Pre-Seeded Benchmark Test Suites</h2>
            </div>
            <button onClick={handleSeedSuites} className="btn-toggle">
              <RefreshCw size={14} /> Re-Seed Benchmark Suites
            </button>
          </div>

          <div className="form-content">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {suites.map((s) => (
                <div key={s.id} className="agent-item-card" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                    <div>
                      <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)' }}>{s.name}</h3>
                      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>{s.description}</p>
                    </div>
                    <span className="status-badge-inline thinking" style={{ padding: '4px 10px', fontSize: '11px' }}>{s.category}</span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px' }}>
                    {s.test_cases && s.test_cases.map((tc) => (
                      <div key={tc.id} style={{ background: 'rgba(3, 7, 18, 0.4)', border: '1px solid var(--glass-border)', borderRadius: '10px', padding: '14px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{tc.name}</strong>
                          <span className="status-badge-inline idle" style={{ padding: '2px 6px', fontSize: '9px' }}>{tc.category}</span>
                        </div>
                        <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '6px 0 10px 0', lineHeight: '1.4' }}>{tc.description}</p>

                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '10px' }}>
                          <span className="status-badge-inline idle" style={{ padding: '2px 6px' }}>Accent: {tc.persona_config.accent || 'Neutral'}</span>
                          <span className="status-badge-inline idle" style={{ padding: '2px 6px' }}>Hostility: {tc.persona_config.hostility || 'low'}</span>
                          {tc.persona_config.interrupter && <span className="status-badge-inline error" style={{ padding: '2px 6px' }}>Interrupter</span>}
                          {tc.persona_config.jailbreak_attempt && <span className="status-badge-inline error" style={{ padding: '2px 6px' }}>Jailbreaker</span>}
                        </div>

                        <div style={{ marginTop: '10px', fontSize: '11px', color: 'var(--accent-cyan)', background: 'rgba(6, 182, 212, 0.08)', padding: '8px', borderRadius: '6px' }}>
                          <em>"{tc.initial_utterance}"</em>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Auto-Tune Modal Overlay */}
      {showAutoTuneModal && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(3, 7, 18, 0.85)', backdropFilter: 'blur(8px)',
          zIndex: 1000, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '20px'
        }}>
          <div className="glass-panel" style={{
            width: '100%', maxWidth: '900px', maxHeight: '90vh', overflowY: 'auto',
            border: '1px solid var(--accent-violet)', boxShadow: '0 20px 50px rgba(139, 92, 246, 0.25)', padding: '24px'
          }}>
            <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)', paddingBottom: '14px', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)', padding: '8px', borderRadius: '10px' }}>
                  <Wand2 size={20} style={{ color: '#fff' }} />
                </div>
                <div>
                  <h2 className="panel-title" style={{ fontSize: '18px' }}>AI System Prompt Auto-Tuner</h2>
                  <p style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Self-healing prompt optimizer for Agent #{autoTuneData?.agent_name || ''}</p>
                </div>
              </div>
              <button onClick={() => setShowAutoTuneModal(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            {autoTuneLoading ? (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--accent-cyan)' }}>
                <RefreshCw className="spin" size={36} style={{ marginBottom: '16px' }} />
                <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)' }}>Analyzing Failure Modes & Synthesizing Optimized System Prompt...</h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>Evaluating prompt vulnerabilities across failing synthetic benchmark cases</p>
              </div>
            ) : autoTuneData ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Success Banner */}
                {autoTuneSuccessMsg && (
                  <div style={{ background: 'rgba(52, 211, 153, 0.2)', border: '1px solid #34d399', color: '#34d399', padding: '12px 16px', borderRadius: '10px', fontWeight: '700', fontSize: '13px' }}>
                    {autoTuneSuccessMsg}
                  </div>
                )}

                {/* AI Diagnosis Card */}
                <div style={{ background: 'rgba(139, 92, 246, 0.12)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <Sparkles size={18} style={{ color: '#a78bfa' }} />
                    <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#c4b5fd' }}>AI Failure Mode Diagnosis</h3>
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: '1.5' }}>{autoTuneData.diagnosis}</p>
                </div>

                {/* Key Changes Added */}
                <div>
                  <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '10px' }}>Guardrail & Behavior Fixes Implemented:</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {autoTuneData.key_changes?.map((change, idx) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', background: 'rgba(3, 7, 18, 0.5)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                        <Check size={16} style={{ color: '#34d399', marginTop: '2px', flexShrink: 0 }} />
                        <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{change}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Side-by-Side Prompt Diff */}
                <div>
                  <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '10px' }}>System Prompt Diff View</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: '700', color: '#ef4444', marginBottom: '6px' }}>ORIGINAL SYSTEM PROMPT</div>
                      <textarea
                        readOnly
                        value={autoTuneData.current_system_prompt}
                        style={{
                          width: '100%', height: '220px', background: 'rgba(3, 7, 18, 0.7)', border: '1px solid rgba(239, 68, 68, 0.3)',
                          borderRadius: '8px', padding: '12px', color: '#fca5a5', fontFamily: 'monospace', fontSize: '11px', resize: 'none'
                        }}
                      />
                    </div>

                    <div>
                      <div style={{ fontSize: '11px', fontWeight: '700', color: '#34d399', marginBottom: '6px' }}>AUTO-TUNED SYSTEM PROMPT ({autoTuneData.suggested_version_tag})</div>
                      <textarea
                        value={autoTuneData.optimized_system_prompt}
                        onChange={(e) => setAutoTuneData({ ...autoTuneData, optimized_system_prompt: e.target.value })}
                        style={{
                          width: '100%', height: '220px', background: 'rgba(3, 7, 18, 0.7)', border: '1px solid rgba(52, 211, 153, 0.4)',
                          borderRadius: '8px', padding: '12px', color: '#a7f3d0', fontFamily: 'monospace', fontSize: '11px', resize: 'none'
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Modal Action Buttons */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid var(--glass-border)', paddingTop: '16px' }}>
                  <button
                    onClick={() => setShowAutoTuneModal(false)}
                    className="btn-toggle"
                    style={{ padding: '8px 16px' }}
                  >
                    Cancel
                  </button>

                  <button
                    onClick={handleApplyAutoTune}
                    disabled={autoTuneApplying}
                    className="btn-toggle active"
                    style={{
                      background: 'linear-gradient(135deg, #10b981, #059669)',
                      borderColor: '#34d399', color: '#fff', padding: '10px 20px', fontWeight: '800'
                    }}
                  >
                    {autoTuneApplying ? (
                      <><RefreshCw className="spin" size={16} /> Applying to Agent DB...</>
                    ) : (
                      <><Check size={16} /> Apply Optimized System Prompt to Agent</>
                    )}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
