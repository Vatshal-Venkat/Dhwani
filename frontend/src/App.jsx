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
  const [model, setModel] = useState(() => localStorage.getItem('llm_model') || 'gemini-3.5-flash');
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
  const [interimSpeech, setInterimSpeech] = useState('');
  
  // WebSockets and Audio References
  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const audioRef = useRef(null);
  const callTimerRef = useRef(null);
  const vadRef = useRef(null);
  
  // Refs to avoid state capture in async event handlers
  const callActiveRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const currentAgentTextRef = useRef('');
  const userSpokeVADRef = useRef(false);

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
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      if (callActiveRef.current && !isSpeakingRef.current) {
        setStatus('listening');
      }
      setInterimSpeech('');
    };

    recognition.onresult = (event) => {
      // If the agent is speaking and VAD hasn't detected user speech, ignore the result!
      // This protects against speaker echo when headphones are not used.
      if (isSpeakingRef.current && !userSpokeVADRef.current) {
        console.log("Speech Recognition: Ignored possible agent echo");
        return;
      }

      let interimTranscript = '';
      let finalTranscript = '';
      
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }
      
      if (interimTranscript) {
        setInterimSpeech(interimTranscript);
      }
      
      if (finalTranscript && finalTranscript.trim()) {
        setInterimSpeech('');
        addTranscript('user', finalTranscript);
        
        // Reset the VAD user spoke ref since a turn is completed
        userSpokeVADRef.current = false;
        
        // Send user transcript to WebSocket backend
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          setStatus('thinking');
          wsRef.current.send(JSON.stringify({
            type: 'user_speech',
            text: finalTranscript
          }));
        }
      }
    };

    recognition.onerror = (event) => {
      if (event.error === 'no-speech') {
        // Ignore silent periods
        return;
      }
      
      console.error("Speech Recognition Error:", event.error);
      
      let friendlyMessage = `Speech Recognition Error: ${event.error}`;
      if (event.error === 'not-allowed') {
        friendlyMessage = "Microphone access denied. Please enable microphone permissions in your browser settings.";
      } else if (event.error === 'audio-capture') {
        friendlyMessage = "No microphone detected. Please connect a microphone and try again.";
      }
      
      setErrorMessage(friendlyMessage);
      setStatus('error');
      
      // Clean up connection and stop loop
      handleHangUp();
    };

    recognition.onend = () => {
      // Loop recognition continuously if call is active (even when agent speaks)
      if (callActiveRef.current) {
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
    currentAgentTextRef.current = text;
    userSpokeVADRef.current = false;
    setStatus('speaking');
    
    // Create new HTML5 Audio from base64
    const audioUrl = `data:audio/mp3;base64,${audioBase64}`;
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.onplay = () => {
      addTranscript('agent', text);
    };

    audio.onended = () => {
      isSpeakingRef.current = false;
      currentAgentTextRef.current = '';
      
      // Turn back on Speech Recognition UI state
      if (callActiveRef.current) {
        setStatus('listening');
      }
    };

    audio.onerror = (e) => {
      console.error("Audio playback error:", e);
      isSpeakingRef.current = false;
      currentAgentTextRef.current = '';
      if (callActiveRef.current) {
        setStatus('listening');
      }
    };

    audio.play().catch(e => {
      console.error("Failed to play audio:", e);
      isSpeakingRef.current = false;
      currentAgentTextRef.current = '';
      if (callActiveRef.current) {
        setStatus('listening');
      }
    });
  };

  // Handle Barge-in interruption
  const handleBargeIn = () => {
    if (!callActiveRef.current || !isSpeakingRef.current) return;

    console.log("Barge-in detected: interrupting agent playback...");

    // Estimate text spoken so far based on current playback ratio
    let textSpoken = "";
    if (audioRef.current && currentAgentTextRef.current) {
      const duration = audioRef.current.duration;
      const currentTime = audioRef.current.currentTime;
      if (duration > 0 && currentTime > 0) {
        const ratio = currentTime / duration;
        const words = currentAgentTextRef.current.split(" ");
        const wordsSpokenCount = Math.ceil(words.length * ratio);
        textSpoken = words.slice(0, wordsSpokenCount).join(" ");
      }
    }

    // Stop playback immediately
    if (audioRef.current) {
      try {
        audioRef.current.pause();
      } catch (e) {
        console.error("Error pausing audio on barge-in:", e);
      }
    }
    isSpeakingRef.current = false;
    setStatus('listening');

    // Notify backend of interruption
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'interrupted',
        text_spoken: textSpoken
      }));
    }
  };

  // Start the call
  const handleStartCall = () => {
    setErrorMessage('');
    setTranscripts([]);
    setStatus('dialing');
    setCallActive(true);
    isSpeakingRef.current = false;
    userSpokeVADRef.current = false;

    // Check browser support for Speech API
    const recognition = initializeSpeechRecognition();
    if (!recognition) {
      setErrorMessage("Speech Recognition API not supported in this browser. Please use Google Chrome or Microsoft Edge.");
      setStatus('error');
      setCallActive(false);
      return;
    }
    recognitionRef.current = recognition;

    // Initialize Silero VAD
    if (window.vad) {
      window.vad.MicVAD.new({
        onSpeechStart: () => {
          console.log("VAD: user speech started");
          userSpokeVADRef.current = true;
          if (callActiveRef.current && isSpeakingRef.current) {
            handleBargeIn();
          }
        },
        onSpeechEnd: (audio) => {
          console.log("VAD: user speech ended");
        }
      })
      .then((myvad) => {
        vadRef.current = myvad;
        myvad.start();
      })
      .catch((err) => {
        console.error("VAD initialization failed", err);
      });
    } else {
      console.warn("VAD script not found in window context");
    }

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

    // Destroy VAD instance
    if (vadRef.current) {
      try {
        vadRef.current.destroy();
      } catch (e) {
        console.error("Error destroying VAD:", e);
      }
      vadRef.current = null;
    }
    userSpokeVADRef.current = false;

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
    setInterimSpeech('');
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

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="logo-container">
            <Activity className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="brand-title">Dhwani</h1>
            <p className="brand-subtitle">Outbound AI Voice Agent Simulation Suite</p>
          </div>
        </div>
        <div className="connection-status">
          <span className="connection-status-dot"></span>
          <span>Simulator Connected</span>
        </div>
      </header>

      {/* Main Grid */}
      <div className="dashboard-grid">
        
        {/* Left Column: Call Config Panel */}
        <section className="glass-panel">
          <div className="panel-header">
            <SettingsIcon className="panel-icon" />
            <h2 className="panel-title">Call Configurations</h2>
          </div>

          <div className="form-content">
            {/* Provider selection */}
            <div className="input-group">
              <label className="input-label">LLM Provider</label>
              <div className="provider-toggle-grid">
                <button 
                  onClick={() => { setProvider('gemini'); setModel('gemini-3.5-flash'); }}
                  className={`btn-toggle ${provider === 'gemini' ? 'active' : ''}`}
                  disabled={callActive}
                >
                  Google Gemini
                </button>
                <button 
                  onClick={() => { setProvider('groq'); setModel('llama-3.1-8b-instant'); }}
                  className={`btn-toggle ${provider === 'groq' ? 'active' : ''}`}
                  disabled={callActive}
                >
                  Groq Cloud
                </button>
              </div>
            </div>

            {/* API Credentials */}
            <div className="input-group">
              <label className="input-label">API Credentials</label>
              <div className="input-with-icon">
                <Key className="input-icon" />
                <input 
                  type="password"
                  placeholder={provider === 'gemini' ? "Enter Gemini API Key..." : "Enter Groq API Key..."}
                  value={provider === 'gemini' ? geminiKey : groqKey}
                  onChange={(e) => provider === 'gemini' ? setGeminiKey(e.target.value) : setGroqKey(e.target.value)}
                  className="input-field"
                  disabled={callActive}
                />
              </div>
            </div>

            {/* Voice Selection */}
            <div className="input-group">
              <label className="input-label">Agent Accent & Voice</label>
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
            <div className="input-group">
              <label className="input-label">Opening Greeting Line</label>
              <input 
                type="text"
                value={greeting}
                onChange={(e) => setGreeting(e.target.value)}
                className="input-field"
                disabled={callActive}
              />
            </div>

            {/* Prompt Config */}
            <div className="input-group">
              <label className="input-label">Agent Persona & Prompt</label>
              <textarea 
                rows="4"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="input-field"
                placeholder="Give instructions to the agent..."
                disabled={callActive}
              />
            </div>
          </div>
        </section>

        {/* Center Column: Phone UI Simulation */}
        <section className="glass-panel simulator-panel">
          <div className="simulator-header">
            <span>SIMULATED CELLULAR</span>
            <div className="call-state-indicator">
              <span className={`call-state-dot ${callActive ? 'active' : ''}`}></span>
              <span>{callActive ? 'IN CALL' : 'IDLE'}</span>
            </div>
          </div>

          {/* Glowing Pulse Visualizer */}
          <div className={`visualizer-outer state-${callActive ? status : 'idle'}`}>
            <div className="visualizer-pulse-bg"></div>
            <div className="visualizer-core">
              {callActive ? (
                status === 'speaking' ? (
                  <Volume2 className="visualizer-icon" />
                ) : status === 'thinking' ? (
                  <RefreshCw className="visualizer-icon" />
                ) : (
                  <Mic className="visualizer-icon" />
                )
              ) : (
                <Phone className="visualizer-icon" style={{ opacity: 0.4 }} />
              )}
            </div>
          </div>

          {/* Info Details */}
          <div className="call-info-wrapper">
            {callActive ? (
              <>
                <div className="call-timer">
                  {formatTime(callDuration)}
                </div>
                <div className="call-status-label">
                  STATUS: 
                  <span className={`status-badge-inline ${status}`}>
                    {status}
                  </span>
                </div>
              </>
            ) : (
              <>
                <div className="call-timer" style={{ fontSize: '20px', letterSpacing: 'normal' }}>Start Conversation</div>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '240px', marginLeft: 'auto', marginRight: 'auto' }}>
                  Initiate an outbound voice simulation calling through your web browser.
                </p>
              </>
            )}
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="error-banner">
              {errorMessage}
            </div>
          )}

          {/* Call Control Button */}
          <div className="call-controls">
            {callActive ? (
              <button 
                onClick={handleHangUp}
                className="btn-call-action hangup"
              >
                <PhoneOff className="h-5 w-5" />
                Hang Up Call
              </button>
            ) : (
              <button 
                onClick={handleStartCall}
                className="btn-call-action start"
              >
                <Phone className="h-5 w-5" />
                Initiate Simulator
              </button>
            )}
          </div>

          {/* Wave animation during speak/listen */}
          <div className="wave-container">
            {callActive && (
              <div className={`wave-active`}>
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
        </section>

        {/* Right Column */}
        <div className="right-column">
          {/* Live Transcript Panel */}
          <section className="glass-panel transcript-panel">
            <div className="panel-header" style={{ padding: '0 0 16px 0', borderBottom: '1px solid var(--glass-border)', marginBottom: '20px' }}>
              <MessageSquare className="panel-icon" style={{ color: 'var(--accent-cyan)' }} />
              <h2 className="panel-title">Live Call Logs & Transcript</h2>
            </div>

            {/* Transcript Scroll Area */}
            <div className="transcript-scroll">
              {transcripts.length === 0 ? (
                <div className="transcript-empty">
                  <VolumeX className="transcript-empty-icon" />
                  <p className="transcript-empty-text">
                    No active conversation logs. Transcripts will appear here in real-time when the call is initiated.
                  </p>
                </div>
              ) : (
                transcripts.map(log => {
                  if (log.role === 'system') {
                    return (
                      <div key={log.id} className="system-pill-wrapper">
                        <span className="system-pill">
                          {log.text}
                        </span>
                      </div>
                    );
                  }
                  
                  const isAgent = log.role === 'agent';
                  return (
                    <div 
                      key={log.id} 
                      className={`bubble-wrapper ${isAgent ? 'agent' : 'user'}`}
                    >
                      <div className="bubble-content">
                        <p>{log.text}</p>
                      </div>
                      <span className="bubble-meta">
                        {isAgent ? 'Agent' : 'You'} • {log.timestamp}
                      </span>
                    </div>
                  );
                })
              )}
            </div>

            {/* Helper Tips */}
            {callActive && (
              <div className="turn-helper-footer">
                {status === 'listening' ? (
                  interimSpeech ? `🎤 "${interimSpeech}"` : '🎤 Go ahead and speak now!'
                ) :
                 status === 'speaking' ? '🔊 Agent is currently talking. Please wait.' :
                 status === 'thinking' ? '⚙️ Agent is thinking...' :
                 'Preparing conversation...'}
              </div>
            )}
          </section>


        </div>
        
      </div>
    </div>
  );
}

export default App;
