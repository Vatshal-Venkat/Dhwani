import React, { useState, useEffect, useRef } from 'react';
import { 
  Phone, 
  PhoneOff, 
  Mic, 
  Volume2, 
  Settings as SettingsIcon, 
  VolumeX, 
  RefreshCw, 
  Play, 
  Database, 
  Key, 
  MessageSquare, 
  Activity 
} from 'lucide-react';

function App() {
  // Call configuration state
  const [provider, setProvider] = useState(() => localStorage.getItem('llm_provider') || 'gemini');
  const [model, setModel] = useState(() => localStorage.getItem('llm_model') || 'gemini-1.5-flash');
  const [geminiKey, setGeminiKey] = useState(() => localStorage.getItem('gemini_api_key') || '');
  const [groqKey, setGroqKey] = useState(() => localStorage.getItem('groq_api_key') || '');
  const [voice, setVoice] = useState('en-US-EmmaMultilingualNeural');
  const [voices, setVoices] = useState([]);
  
  const [systemPrompt, setSystemPrompt] = useState(
    "You are Alex, a helpful outbound representative from 'SmartHome Solutions'. " +
    "Your goal is to call the customer to confirm their scheduled installation appointment tomorrow at 10:00 AM. " +
    "Keep your answers short, professional, and friendly. Speak in 1-2 conversational sentences max."
  );
  const [greeting, setGreeting] = useState("Hi there! This is Alex calling from SmartHome Solutions. Am I speaking with the homeowner?");

  // Call runtime state
  const [status, setStatus] = useState('idle'); // idle, dialing, connected, listening, thinking, speaking, disconnected, error
  const [callActive, setCallActive] = useState(false);
  const [callDuration, setCallDuration] = useState(0);
  const [transcripts, setTranscripts] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');
  
  // WebSockets and Audio References
  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const audioRef = useRef(null);
  const callTimerRef = useRef(null);
  
  // Refs to avoid state capture in async event handlers
  const callActiveRef = useRef(false);
  const isSpeakingRef = useRef(false);

  useEffect(() => {
    callActiveRef.current = callActive;
  }, [callActive]);

  // Fetch available voices & default configurations from Backend
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/config');
        if (response.ok) {
          const data = await response.json();
          if (!localStorage.getItem('llm_provider')) setProvider(data.provider);
          if (!localStorage.getItem('llm_model')) setModel(data.model);
          setVoice(data.voice);
        }
      } catch (err) {
        console.error("Could not load backend configurations", err);
      }
    };

    const fetchVoices = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/voices');
        if (response.ok) {
          const data = await response.json();
          setVoices(data);
        }
      } catch (err) {
        console.error("Could not fetch available voices", err);
      }
    };

    fetchConfig();
    fetchVoices();
  }, []);

  // Save config values to localStorage
  useEffect(() => {
    localStorage.setItem('llm_provider', provider);
    localStorage.setItem('llm_model', model);
    localStorage.setItem('gemini_api_key', geminiKey);
    localStorage.setItem('groq_api_key', groqKey);
  }, [provider, model, geminiKey, groqKey]);

  // Handle Call Duration Timer
  useEffect(() => {
    if (callActive) {
      setCallDuration(0);
      callTimerRef.current = setInterval(() => {
        setCallDuration(prev => prev + 1);
      }, 1000);
    } else {
      if (callTimerRef.current) clearInterval(callTimerRef.current);
    }
    return () => {
      if (callTimerRef.current) clearInterval(callTimerRef.current);
    };
  }, [callActive]);

  // Initialize Speech Recognition (Web Speech API)
  const initializeSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.error("Browser does not support Speech Recognition.");
      return null;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      if (callActiveRef.current && !isSpeakingRef.current) {
        setStatus('listening');
      }
    };

    recognition.onresult = (event) => {
      const resultText = event.results[0][0].transcript;
      if (resultText && resultText.trim()) {
        addTranscript('user', resultText);
        
        // Send user transcript to WebSocket backend
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          setStatus('thinking');
          wsRef.current.send(JSON.stringify({
            type: 'user_speech',
            text: resultText
          }));
        }
      }
    };

    recognition.onerror = (event) => {
      // Ignore no-speech errors which occur during pauses
      if (event.error !== 'no-speech') {
        console.error("Speech Recognition Error:", event.error);
      }
    };

    recognition.onend = () => {
      // Loop recognition if call is active and agent is NOT speaking
      if (callActiveRef.current && !isSpeakingRef.current) {
        try {
          recognition.start();
        } catch (e) {
          console.error("Failed to restart Speech Recognition:", e);
        }
      }
    };

    return recognition;
  };

  const addTranscript = (role, text) => {
    setTranscripts(prev => [...prev, {
      id: Date.now() + Math.random().toString(36).substr(2, 9),
      role,
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }]);
  };

  // Play synthetic voice from Base64
  const playAgentAudio = (audioBase64, text) => {
    // If there is an existing audio, stop it
    if (audioRef.current) {
      audioRef.current.pause();
    }

    isSpeakingRef.current = true;
    setStatus('speaking');
    
    // Create new HTML5 Audio from base64
    const audioUrl = `data:audio/mp3;base64,${audioBase64}`;
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    // Turn off recognition during agent speech to avoid feedback
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {
        console.log("Recognition stop error:", e);
      }
    }

    audio.onplay = () => {
      addTranscript('agent', text);
    };

    audio.onended = () => {
      isSpeakingRef.current = false;
      
      // Turn back on Speech Recognition
      if (callActiveRef.current && recognitionRef.current) {
        setStatus('listening');
        try {
          recognitionRef.current.start();
        } catch (e) {
          console.error("Error starting Speech Recognition after playback:", e);
        }
      }
    };

    audio.onerror = (e) => {
      console.error("Audio playback error:", e);
      isSpeakingRef.current = false;
      if (callActiveRef.current && recognitionRef.current) {
        setStatus('listening');
        try {
          recognitionRef.current.start();
        } catch (err) {
          console.error(err);
        }
      }
    };

    audio.play().catch(e => {
      console.error("Failed to play audio:", e);
      isSpeakingRef.current = false;
      // Auto-recover turn
      if (callActiveRef.current && recognitionRef.current) {
        setStatus('listening');
        try { recognitionRef.current.start(); } catch (err) {}
      }
    });
  };

  // Start the call
  const handleStartCall = () => {
    setErrorMessage('');
    setTranscripts([]);
    setStatus('dialing');
    setCallActive(true);
    isSpeakingRef.current = false;

    // Check browser support for Speech API
    const recognition = initializeSpeechRecognition();
    if (!recognition) {
      setErrorMessage("Speech Recognition API not supported in this browser. Please use Google Chrome or Microsoft Edge.");
      setStatus('error');
      setCallActive(false);
      return;
    }
    recognitionRef.current = recognition;

    // Connect to WebSocket Server
    const wsUrl = `ws://localhost:8000/ws/call`;
    const socket = new WebSocket(wsUrl);
    wsRef.current = socket;

    socket.onopen = () => {
      setStatus('connected');
      addTranscript('system', 'Call connected. Agent is initiating greeting...');
      
      // Send configurations
      socket.send(JSON.stringify({
        type: 'start_call',
        systemPrompt,
        voice,
        provider,
        model,
        greeting,
        // Send Keys if custom config used
        geminiKey: provider === 'gemini' ? geminiKey : undefined,
        groqKey: provider === 'groq' ? groqKey : undefined
      }));
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'call_started' || data.type === 'agent_speech') {
        if (data.audio) {
          playAgentAudio(data.audio, data.text);
        } else {
          // Fallback if voice couldn't be generated
          addTranscript('agent', data.text);
          setStatus('listening');
          if (recognitionRef.current) {
            try { recognitionRef.current.start(); } catch (e) {}
          }
        }
      } else if (data.type === 'status') {
        if (data.status === 'thinking') {
          setStatus('thinking');
        } else if (data.status === 'error') {
          setErrorMessage(data.message);
          setStatus('error');
          handleHangUp();
        }
      }
    };

    socket.onerror = (err) => {
      console.error("WebSocket connection error:", err);
      setErrorMessage("Could not connect to voice agent backend server. Ensure backend is running.");
      setStatus('error');
      handleHangUp();
    };

    socket.onclose = () => {
      addTranscript('system', 'Call ended.');
      if (status !== 'error') {
        setStatus('disconnected');
      }
      setCallActive(false);
    };
  };

  // Hang up the call
  const handleHangUp = () => {
    // Send hangup event
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'hang_up' }));
        wsRef.current.close();
      } catch (e) {}
    }

    // Stop audio playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    // Stop Speech Recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onend = null; // Prevent looping restart
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }

    isSpeakingRef.current = false;
    setCallActive(false);
    if (status !== 'error') {
      setStatus('disconnected');
    }
  };

  // Format call duration: mm:ss
  const formatTime = (secs) => {
    const mins = Math.floor(secs / 60);
    const remainingSecs = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remainingSecs.toString().padStart(2, '0')}`;
  };

  const getStatusColor = () => {
    switch (status) {
      case 'dialing': return 'text-amber-400 border-amber-400';
      case 'connected': return 'text-indigo-400 border-indigo-400';
      case 'listening': return 'text-emerald-400 border-emerald-400';
      case 'thinking': return 'text-cyan-400 border-cyan-400';
      case 'speaking': return 'text-purple-400 border-purple-400';
      case 'disconnected': return 'text-slate-400 border-slate-400';
      case 'error': return 'text-rose-500 border-rose-500';
      default: return 'text-slate-400 border-slate-700';
    }
  };

  return (
    <div className="min-h-screen p-6 md:p-12 flex flex-col items-center justify-start max-w-7xl mx-auto">
      {/* Top Header */}
      <header className="w-full flex items-center justify-between mb-8 pb-4 border-b border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Activity className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">Antigravity</h1>
            <p className="text-xs text-[#94a3b8]">Outbound AI Voice Agent Simulation Suite</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-xs font-semibold text-slate-300">Backend Connected</span>
        </div>
      </header>

      {/* Main Grid */}
      <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Column: Call Config Panel (5 cols) */}
        <section className="lg:col-span-4 space-y-6">
          <div className="glass-panel p-6 space-y-6">
            <div className="flex items-center gap-2 border-b border-[rgba(255,255,255,0.06)] pb-3">
              <SettingsIcon className="h-4 w-4 text-indigo-400" />
              <h2 className="text-md font-semibold text-white">Call Configurations</h2>
            </div>

            {/* Provider selection */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">LLM Provider</label>
              <div className="grid grid-cols-2 gap-2">
                <button 
                  onClick={() => { setProvider('gemini'); setModel('gemini-1.5-flash'); }}
                  className={`py-2 px-3 rounded-md text-xs font-semibold border transition-all ${
                    provider === 'gemini' 
                      ? 'bg-indigo-600/20 border-indigo-500 text-white' 
                      : 'bg-slate-900/40 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                  disabled={callActive}
                >
                  Google Gemini
                </button>
                <button 
                  onClick={() => { setProvider('groq'); setModel('llama3-8b-8192'); }}
                  className={`py-2 px-3 rounded-md text-xs font-semibold border transition-all ${
                    provider === 'groq' 
                      ? 'bg-indigo-600/20 border-indigo-500 text-white' 
                      : 'bg-slate-900/40 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                  disabled={callActive}
                >
                  Groq Cloud
                </button>
              </div>
            </div>

            {/* API Keys (Saved locally) */}
            <div className="space-y-3">
              <label className="text-xs font-medium text-slate-300 block">API Credentials</label>
              
              {provider === 'gemini' ? (
                <div className="relative">
                  <Key className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
                  <input 
                    type="password"
                    placeholder="Enter Gemini API Key..."
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    className="input-field pl-10"
                    disabled={callActive}
                  />
                </div>
              ) : (
                <div className="relative">
                  <Key className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
                  <input 
                    type="password"
                    placeholder="Enter Groq API Key..."
                    value={groqKey}
                    onChange={(e) => setGroqKey(e.target.value)}
                    className="input-field pl-10"
                    disabled={callActive}
                  />
                </div>
              )}
              <p className="text-[10px] text-slate-500">API keys are stored strictly in local browser storage.</p>
            </div>

            {/* Voice Selection */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">Agent Accent & Voice</label>
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="input-field"
                disabled={callActive}
              >
                {voices.length > 0 ? (
                  voices.map(v => (
                    <option key={v.id} value={v.id} className="bg-slate-900 text-white">
                      {v.name} ({v.gender})
                    </option>
                  ))
                ) : (
                  <option value="en-US-EmmaMultilingualNeural">Emma (Multilingual, US)</option>
                )}
              </select>
            </div>

            {/* Greeting */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">Opening Greeting Line</label>
              <input 
                type="text"
                value={greeting}
                onChange={(e) => setGreeting(e.target.value)}
                className="input-field"
                disabled={callActive}
              />
            </div>

            {/* Prompt Config */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">Agent Persona & Prompt</label>
              <textarea 
                rows="4"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="input-field resize-none text-xs"
                placeholder="Give instructions to the agent..."
                disabled={callActive}
              />
            </div>
          </div>
        </section>

        {/* Center Column: Phone UI Simulation (4 cols) */}
        <section className="lg:col-span-4 flex flex-col items-center justify-center">
          <div className="glass-panel w-full max-w-sm p-8 flex flex-col items-center justify-between text-center relative min-h-[500px]">
            
            {/* Visualizer Status & Key info */}
            <div className="w-full flex justify-between items-center text-xs text-slate-400 font-semibold border-b border-[rgba(255,255,255,0.06)] pb-4">
              <span>SIMULATED CELLULAR</span>
              <span className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${callActive ? 'bg-indigo-500 animate-ping' : 'bg-slate-600'}`}></span>
                {callActive ? 'IN CALL' : 'IDLE'}
              </span>
            </div>

            {/* Circular Pulse Interaction Center */}
            <div className="my-8 relative flex items-center justify-center">
              {/* Animated outer circles */}
              {callActive && (
                <>
                  <div className="absolute w-44 h-44 rounded-full border border-indigo-500/20 animate-ping" style={{ animationDuration: '3s' }}></div>
                  <div className="absolute w-36 h-36 rounded-full border border-cyan-500/30 animate-pulse"></div>
                </>
              )}

              {/* Main status indicator disc */}
              <div className={`h-28 w-28 rounded-full flex flex-col items-center justify-center relative transition-all duration-500 ${
                callActive 
                  ? 'bg-gradient-to-br from-indigo-900 to-indigo-950 shadow-[0_0_30px_rgba(79,70,229,0.3)] border-2 border-indigo-500' 
                  : 'bg-slate-900/60 border border-slate-800'
              }`}>
                {callActive ? (
                  status === 'speaking' ? (
                    <Volume2 className="h-8 w-8 text-indigo-400 animate-bounce" />
                  ) : status === 'thinking' ? (
                    <RefreshCw className="h-8 w-8 text-cyan-400 animate-spin" />
                  ) : (
                    <Mic className="h-8 w-8 text-emerald-400 animate-pulse" />
                  )
                ) : (
                  <Phone className="h-8 w-8 text-slate-500" />
                )}
              </div>
            </div>

            {/* Info details */}
            <div className="space-y-2 w-full">
              {callActive ? (
                <>
                  <div className="text-2xl font-bold text-white tracking-wider font-heading">
                    {formatTime(callDuration)}
                  </div>
                  <div className="text-xs font-semibold uppercase tracking-widest text-[#94a3b8] flex items-center justify-center gap-1">
                    Status: 
                    <span className={`font-bold capitalize ${
                      status === 'listening' ? 'text-emerald-400' :
                      status === 'thinking' ? 'text-cyan-400' :
                      status === 'speaking' ? 'text-purple-400' :
                      'text-indigo-400'
                    }`}>
                      {status}
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-lg font-bold text-white">Start Conversation</div>
                  <p className="text-xs text-slate-400 max-w-[240px] mx-auto">
                    Initiate an outbound voice simulation calling through your web browser.
                  </p>
                </>
              )}
            </div>

            {/* Error notifications */}
            {errorMessage && (
              <div className="my-2 p-2 bg-rose-900/20 border border-rose-950 text-rose-300 text-xs rounded-md w-full">
                {errorMessage}
              </div>
            )}

            {/* Call Control Button */}
            <div className="w-full pt-6 border-t border-[rgba(255,255,255,0.06)] flex justify-center">
              {callActive ? (
                <button 
                  onClick={handleHangUp}
                  className="w-full flex items-center justify-center gap-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold py-3 px-6 rounded-xl transition-all shadow-lg shadow-rose-900/30"
                >
                  <PhoneOff className="h-5 w-5" />
                  Hang Up Call
                </button>
              ) : (
                <button 
                  onClick={handleStartCall}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-500 to-cyan-500 hover:from-indigo-600 hover:to-cyan-600 text-white font-semibold py-3 px-6 rounded-xl transition-all shadow-lg shadow-indigo-500/20"
                >
                  <Phone className="h-5 w-5 animate-pulse" />
                  Initiate Simulator
                </button>
              )}
            </div>

            {/* Wave animation during speak/listen */}
            <div className="mt-4 flex items-center justify-center h-10 w-full">
              {callActive && (
                <div className={`flex items-end h-8 ${status === 'speaking' || status === 'listening' ? 'wave-active' : ''}`}>
                  <span className="wave-bar"></span>
                  <span className="wave-bar"></span>
                  <span className="wave-bar"></span>
                  <span className="wave-bar"></span>
                  <span className="wave-bar"></span>
                  <span className="wave-bar"></span>
                  <span className="wave-bar"></span>
                </div>
              )}
            </div>

          </div>
        </section>

        {/* Right Column: Live Transcript Panel (5 cols) */}
        <section className="lg:col-span-4 space-y-6">
          <div className="glass-panel p-6 flex flex-col h-[500px]">
            <div className="flex items-center gap-2 border-b border-[rgba(255,255,255,0.06)] pb-3 mb-4 shrink-0">
              <MessageSquare className="h-4 w-4 text-cyan-400" />
              <h2 className="text-md font-semibold text-white">Live Call Logs & Transcript</h2>
            </div>

            {/* Transcript scroll box */}
            <div className="flex-1 overflow-y-auto pr-1 space-y-4 text-sm scroll-smooth">
              {transcripts.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-2">
                  <VolumeX className="h-8 w-8 text-slate-700" />
                  <p className="text-xs">No active conversation logs.</p>
                  <p className="text-[10px] text-slate-600 text-center max-w-[200px]">
                    Transcripts will appear here in real-time when the call is initiated.
                  </p>
                </div>
              ) : (
                transcripts.map(log => {
                  if (log.role === 'system') {
                    return (
                      <div key={log.id} className="text-center">
                        <span className="inline-block py-1 px-3 bg-slate-900/60 border border-slate-950 text-slate-500 rounded-full text-[10px] uppercase font-semibold tracking-wider">
                          {log.text}
                        </span>
                      </div>
                    );
                  }
                  
                  const isAgent = log.role === 'agent';
                  return (
                    <div 
                      key={log.id} 
                      className={`flex flex-col max-w-[85%] ${isAgent ? 'mr-auto items-start' : 'ml-auto items-end'}`}
                    >
                      <div className={`px-4 py-3 rounded-2xl ${
                        isAgent 
                          ? 'bg-slate-800/80 border border-slate-750 text-slate-100 rounded-tl-sm' 
                          : 'bg-indigo-600 text-white rounded-tr-sm shadow-md shadow-indigo-600/10'
                      }`}>
                        <p className="text-xs leading-relaxed">{log.text}</p>
                      </div>
                      <span className="text-[9px] text-slate-500 mt-1 px-1">
                        {isAgent ? 'Agent' : 'You'} • {log.timestamp}
                      </span>
                    </div>
                  );
                })
              )}
            </div>

            {/* Small turn-taking helper tips */}
            {callActive && (
              <div className="border-t border-[rgba(255,255,255,0.06)] pt-3 mt-3 shrink-0 text-center">
                <span className="text-[10px] text-slate-500">
                  {status === 'listening' ? '🎤 Go ahead and speak now!' :
                   status === 'speaking' ? '🔊 Agent is currently talking. Please wait.' :
                   status === 'thinking' ? '⚙️ Agent is thinking...' :
                   'Preparing conversation...'}
                </span>
              </div>
            )}
          </div>
        </section>
        
      </div>
    </div>
  );
}

export default App;
