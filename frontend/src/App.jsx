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
  Activity,
  Trash2,
  Edit3,
  Plus,
  Calendar,
  Clock
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

  // Navigation and Database Tab States
  const [activeTab, setActiveTab] = useState('simulator'); // 'simulator' | 'agents' | 'history'
  const [agents, setAgents] = useState([]);
  const [selectedAgentId, setSelectedAgentId] = useState('custom');
  
  // Create / Edit Agent Form States
  const [formName, setFormName] = useState('');
  const [formVoice, setFormVoice] = useState('en-US-EmmaMultilingualNeural');
  const [formGreeting, setFormGreeting] = useState('');
  const [formPrompt, setFormPrompt] = useState('');
  const [formTemp, setFormTemp] = useState(0.7);
  const [editingAgentId, setEditingAgentId] = useState(null);

  // Call history states
  const [calls, setCalls] = useState([]);
  const [activeHistoryCall, setActiveHistoryCall] = useState(null);

  // Bookings, Leads, and Guardrail state
  const [bookings, setBookings] = useState([]);
  const [leads, setLeads] = useState([]);
  const [guardrailEvents, setGuardrailEvents] = useState([]);

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
  const micStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const transcriptEndRef = useRef(null);
  const audioQueueRef = useRef([]);

  // Refs for Web Audio API visualizer
  const audioContextRef = useRef(null);
  const micAnalyserRef = useRef(null);
  const agentAnalyserRef = useRef(null);
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);
  const phaseRef = useRef(0);
  const statusRef = useRef(status);

  // Refs to avoid state capture in async event handlers
  const callActiveRef = useRef(false);
  const isSpeakingRef = useRef(false);
  const currentAgentTextRef = useRef('');
  const userSpokeVADRef = useRef(false);

  useEffect(() => {
    callActiveRef.current = callActive;
  }, [callActive]);

  // Keep statusRef updated
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  // Auto-scroll transcript to bottom
  useEffect(() => {
    if (transcriptEndRef.current) {
      transcriptEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [transcripts]);

  // Visualizer Animation Loop
  useEffect(() => {
    const drawVisualizer = () => {
      if (!canvasRef.current) return;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const width = canvas.width;
      const height = canvas.height;

      // Clear canvas
      ctx.clearRect(0, 0, width, height);

      const isActive = callActiveRef.current;
      const currentStatus = statusRef.current;

      // Determine target analyser
      let analyser = null;
      if (isActive) {
        if (currentStatus === 'listening') {
          analyser = micAnalyserRef.current;
        } else if (currentStatus === 'speaking') {
          analyser = agentAnalyserRef.current;
        }
      }

      // Get volume (RMS)
      let volume = 0.015; // default subtle baseline noise
      
      if (isActive) {
        if (currentStatus === 'thinking') {
          // Slow pulsing sine wave for thinking state
          volume = 0.08 + Math.sin(Date.now() / 200) * 0.03;
        } else if (currentStatus === 'dialing') {
          // Pulse wave for dialing
          volume = 0.03 + Math.sin(Date.now() / 150) * 0.01;
        } else if (analyser) {
          const bufferLength = analyser.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);
          analyser.getByteTimeDomainData(dataArray);

          // Calculate RMS (volume)
          let sum = 0;
          for (let i = 0; i < bufferLength; i++) {
            const val = (dataArray[i] - 128) / 128;
            sum += val * val;
          }
          const rms = Math.sqrt(sum / bufferLength);
          // Map rms to volume with a boost for visualization clarity
          volume = Math.max(0.015, rms * 1.8);
        }
      }

      // Increment phase for horizontal movement
      phaseRef.current = (phaseRef.current || 0) + (isActive && currentStatus === 'thinking' ? 0.08 : 0.12);
      const phase = phaseRef.current;

      const centerY = height / 2;
      ctx.lineCap = 'round';

      // Choose colors and waves based on status
      let colors = [];
      if (!isActive) {
        colors = [
          'rgba(148, 163, 184, 0.25)',  // Slate
          'rgba(148, 163, 184, 0.12)',
          'rgba(148, 163, 184, 0.05)',
        ];
      } else {
        switch (currentStatus) {
          case 'dialing':
            colors = [
              'rgba(245, 158, 11, 0.5)',   // Amber
              'rgba(245, 158, 11, 0.25)',
              'rgba(245, 158, 11, 0.1)',
            ];
            break;
          case 'thinking':
            colors = [
              'rgba(6, 182, 212, 0.65)',   // Cyan
              'rgba(99, 102, 241, 0.35)',  // Indigo
              'rgba(168, 85, 247, 0.15)',  // Violet
            ];
            break;
          case 'listening':
            colors = [
              'rgba(16, 185, 129, 0.75)',  // Emerald green
              'rgba(6, 182, 212, 0.4)',   // Cyan
              'rgba(14, 165, 233, 0.15)',  // Sky blue
            ];
            break;
          case 'speaking':
            colors = [
              'rgba(168, 85, 247, 0.75)',  // Violet
              'rgba(139, 92, 246, 0.4)',   // Purple
              'rgba(99, 102, 241, 0.15)',  // Indigo
            ];
            break;
          default:
            colors = [
              'rgba(148, 163, 184, 0.3)',
              'rgba(148, 163, 184, 0.15)',
              'rgba(148, 163, 184, 0.05)',
            ];
        }
      }

      // Draw 3 layers of waves
      for (let l = 0; l < 3; l++) {
        ctx.beginPath();
        ctx.strokeStyle = colors[l];
        ctx.lineWidth = l === 0 ? 2.5 : 1.5;
        
        if (l === 0 && isActive) {
          ctx.shadowBlur = 10;
          ctx.shadowColor = colors[0];
        } else {
          ctx.shadowBlur = 0;
        }

        const frequency = 1.0 + l * 0.4;
        const phaseShift = phase + l * (Math.PI / 2.5);

        for (let x = 0; x <= width; x++) {
          // Envelop to taper off at boundaries
          const normX = (x / width) * 2 - 1;
          const envelope = Math.pow(1 - normX * normX, 2);

          // Siri style wave formula
          const sine = Math.sin(normX * Math.PI * frequency + phaseShift);
          
          let amp = volume * (height * 0.45);
          if (l > 0) amp *= 0.55;

          const y = centerY + sine * amp * envelope;

          if (x === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      }
      ctx.shadowBlur = 0;
    };

    const runLoop = () => {
      drawVisualizer();
      animationFrameRef.current = requestAnimationFrame(runLoop);
    };

    runLoop();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Fetch available voices, configurations, agents, and calls from Backend
  const fetchAgents = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/agents');
      if (response.ok) {
        const data = await response.json();
        setAgents(data);
      }
    } catch (err) {
      console.error("Could not fetch agents", err);
    }
  };

  const fetchCalls = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/calls');
      if (response.ok) {
        const data = await response.json();
        setCalls(data);
      }
    } catch (err) {
      console.error("Could not fetch calls", err);
    }
  };

  const fetchBookingsAndLeads = async () => {
    try {
      const resB = await fetch('http://localhost:8000/api/bookings');
      if (resB.ok) {
        const dataB = await resB.json();
        setBookings(dataB);
      }
      const resL = await fetch('http://localhost:8000/api/leads');
      if (resL.ok) {
        const dataL = await resL.json();
        setLeads(dataL);
      }
    } catch (err) {
      console.error("Could not fetch bookings or leads", err);
    }
  };

  const handleCancelBooking = async (id) => {
    try {
      const res = await fetch(`http://localhost:8000/api/bookings/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchBookingsAndLeads();
      }
    } catch (err) {
      console.error("Failed to cancel booking", err);
    }
  };

  const handleDeleteLead = async (id) => {
    try {
      const res = await fetch(`http://localhost:8000/api/leads/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchBookingsAndLeads();
      }
    } catch (err) {
      console.error("Failed to delete lead", err);
    }
  };

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
    fetchAgents();
    fetchCalls();
  }, []);

  // Save config values to localStorage
  useEffect(() => {
    localStorage.setItem('llm_provider', provider);
    localStorage.setItem('llm_model', model);
    localStorage.setItem('gemini_api_key', geminiKey);
    localStorage.setItem('groq_api_key', groqKey);
  }, [provider, model, geminiKey, groqKey]);

  // Handle Agent selector change
  const handleAgentSelectChange = (agentId) => {
    setSelectedAgentId(agentId);
    if (agentId === 'custom') {
      return;
    }
    const selectedAgent = agents.find(a => a.id === parseInt(agentId));
    if (selectedAgent) {
      setVoice(selectedAgent.voice_id);
      setGreeting(selectedAgent.greeting);
      setSystemPrompt(selectedAgent.system_prompt);
    }
  };

  // Agent CRUD form submit
  const handleSaveAgent = async (e) => {
    e.preventDefault();
    if (!formName.trim() || !formPrompt.trim() || !formGreeting.trim()) {
      alert("Please fill in all fields.");
      return;
    }

    const payload = {
      name: formName,
      voice_id: formVoice,
      temperature: parseFloat(formTemp),
      system_prompt: formPrompt,
      greeting: formGreeting
    };

    try {
      const url = editingAgentId 
        ? `http://localhost:8000/api/agents/${editingAgentId}` 
        : 'http://localhost:8000/api/agents';
      const method = editingAgentId ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        await fetchAgents();
        // Reset form
        setFormName('');
        setFormPrompt('');
        setFormGreeting('');
        setEditingAgentId(null);
      } else {
        console.error("Failed to save agent");
      }
    } catch (err) {
      console.error("Error saving agent:", err);
    }
  };

  const handleDeleteAgent = async (id, event) => {
    event.stopPropagation();
    if (!confirm("Are you sure you want to delete this agent?")) return;

    try {
      const res = await fetch(`http://localhost:8000/api/agents/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await fetchAgents();
        if (selectedAgentId === id.toString()) {
          setSelectedAgentId('custom');
        }
        if (editingAgentId === id) {
          setEditingAgentId(null);
          setFormName('');
          setFormPrompt('');
          setFormGreeting('');
        }
      }
    } catch (err) {
      console.error("Error deleting agent:", err);
    }
  };

  const handleEditAgentClick = (agent, event) => {
    event.stopPropagation();
    setEditingAgentId(agent.id);
    setFormName(agent.name);
    setFormVoice(agent.voice_id);
    setFormPrompt(agent.system_prompt);
    setFormGreeting(agent.greeting);
    setFormTemp(agent.temperature);
  };

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

  // Helper to determine if user speech is semantic
  const isSemanticSpeech = (text) => {
    if (!text) return false;
    const clean = text.trim().toLowerCase().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g,"");
    const words = clean.split(/\s+/).filter(w => w.length > 0);
    if (words.length === 0) return false;
    
    const fillers = new Set([
      "uh", "uhh", "um", "umm", "hmm", "hm", "ah", "ahh", "oh", "eh",
      "yes", "yeah", "ok", "okay", "no", "yep", "nope", "sure", "right"
    ]);
    
    if (words.length === 1 && fillers.has(words[0])) {
      return false;
    }
    return true;
  };

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

      // Check for semantic barge-in
      if (isSpeakingRef.current && userSpokeVADRef.current) {
        const textToCheck = interimTranscript || finalTranscript;
        if (isSemanticSpeech(textToCheck)) {
          handleBargeIn();
        }
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
    if (isSpeakingRef.current) {
      // Queue the incoming audio chunk
      audioQueueRef.current.push({ audioBase64, text });
      return;
    }
    playNextChunk(audioBase64, text);
  };

  const playNextChunk = (audioBase64, text) => {
    isSpeakingRef.current = true;
    currentAgentTextRef.current = text;
    userSpokeVADRef.current = false;
    setStatus('speaking');

    // Create new HTML5 Audio from base64
    const audioUrl = `data:audio/mp3;base64,${audioBase64}`;
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    // Connect agent audio element to agent analyser
    if (audioContextRef.current && agentAnalyserRef.current) {
      try {
        if (audioContextRef.current.state === 'suspended') {
          audioContextRef.current.resume();
        }
        const source = audioContextRef.current.createMediaElementSource(audio);
        source.connect(agentAnalyserRef.current);
        agentAnalyserRef.current.connect(audioContextRef.current.destination);
      } catch (e) {
        console.error("Error connecting agent audio to Web Audio API:", e);
      }
    }

    audio.onplay = () => {
      addTranscript('agent', text);
    };

    audio.onended = () => {
      // Check queue
      if (audioQueueRef.current.length > 0) {
        const next = audioQueueRef.current.shift();
        playNextChunk(next.audioBase64, next.text);
      } else {
        isSpeakingRef.current = false;
        currentAgentTextRef.current = '';

        // Turn back on Speech Recognition UI state
        if (callActiveRef.current) {
          setStatus('listening');
        }
      }
    };

    audio.onerror = (e) => {
      console.error("Audio playback error:", e);
      // Check queue
      if (audioQueueRef.current.length > 0) {
        const next = audioQueueRef.current.shift();
        playNextChunk(next.audioBase64, next.text);
      } else {
        isSpeakingRef.current = false;
        currentAgentTextRef.current = '';
        if (callActiveRef.current) {
          setStatus('listening');
        }
      }
    };

    audio.play().catch(e => {
      console.error("Failed to play audio:", e);
      // Check queue
      if (audioQueueRef.current.length > 0) {
        const next = audioQueueRef.current.shift();
        playNextChunk(next.audioBase64, next.text);
      } else {
        isSpeakingRef.current = false;
        currentAgentTextRef.current = '';
        if (callActiveRef.current) {
          setStatus('listening');
        }
      }
    });
  };

  // Handle Barge-in interruption
  const handleBargeIn = () => {
    if (!callActiveRef.current || !isSpeakingRef.current) return;

    console.log("Barge-in detected: interrupting agent playback...");

    // Clear queue
    audioQueueRef.current = [];

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

    // Initialize Web Audio API for visualizer
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContextClass();
      audioContextRef.current = audioCtx;
      
      const micAnalyser = audioCtx.createAnalyser();
      micAnalyser.fftSize = 512;
      micAnalyserRef.current = micAnalyser;

      const agentAnalyser = audioCtx.createAnalyser();
      agentAnalyser.fftSize = 512;
      agentAnalyserRef.current = agentAnalyser;
    } catch (e) {
      console.error("Failed to initialize Web Audio API:", e);
    }

    // Helper to convert Float32Array to 16-bit PCM WAV
    const float32To16BitPCM = (float32Array) => {
      const buffer = new ArrayBuffer(float32Array.length * 2);
      const view = new DataView(buffer);
      let offset = 0;
      for (let i = 0; i < float32Array.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      }
      return buffer;
    };

    const writeString = (view, offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    const writeWavHeader = (sampleRate, numChannels, numSamples) => {
      const buffer = new ArrayBuffer(44);
      const view = new DataView(buffer);
      
      writeString(view, 0, 'RIFF');
      view.setUint32(4, 36 + numSamples * 2, true);
      writeString(view, 8, 'WAVE');
      writeString(view, 12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, numChannels, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * numChannels * 2, true);
      view.setUint16(32, numChannels * 2, true);
      view.setUint16(34, 16, true);
      writeString(view, 36, 'data');
      view.setUint32(40, numSamples * 2, true);
      
      return buffer;
    };

    const convertToWav = (float32Array, sampleRate = 16000) => {
      const header = writeWavHeader(sampleRate, 1, float32Array.length);
      const pcm = float32To16BitPCM(float32Array);
      const wavBytes = new Uint8Array(header.byteLength + pcm.byteLength);
      wavBytes.set(new Uint8Array(header), 0);
      wavBytes.set(new Uint8Array(pcm), header.byteLength);
      return wavBytes.buffer;
    };

    // Set up microphone capture and VAD for streaming
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        micStreamRef.current = stream;

        // Connect mic stream to mic analyser
        if (audioContextRef.current && micAnalyserRef.current) {
          try {
            if (audioContextRef.current.state === 'suspended') {
              audioContextRef.current.resume();
            }
            const micSource = audioContextRef.current.createMediaStreamSource(stream);
            micSource.connect(micAnalyserRef.current);
          } catch (e) {
            console.error("Error connecting mic stream to analyser:", e);
          }
        }

        // Initialize Silero VAD with local assets, sharing the same stream
        if (window.vad) {
          window.vad.MicVAD.new({
            stream: stream,
            baseAssetPath: "/",
            modelURL: "/silero_vad_v5.onnx",
            ortConfig: (ort) => {
              // Disable WASM threads to bypass secure context (SharedArrayBuffer) requirements on localhost
              ort.env.wasm.numThreads = 1;
              // Point to local WASM files in the public directory
              ort.env.wasm.wasmPaths = "/";
            },
            onSpeechStart: () => {
              console.log("VAD: user speech started. Awaiting semantic validation...");
              userSpokeVADRef.current = true;
              if (callActiveRef.current) {
                // Do NOT call handleBargeIn() immediately for semantic barge-in.
                // It will be triggered by interim SpeechRecognition results instead.
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: 'speech_start' }));
                }
              }
            },
            onSpeechEnd: (audio) => {
              console.log("VAD: user speech ended");
              if (callActiveRef.current && audio && audio.length > 0) {
                try {
                  const wavBuffer = convertToWav(audio, 16000);
                  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send(wavBuffer);
                    console.log(`Sent WAV audio of ${audio.length} samples to backend.`);
                    
                    // Wait a tiny bit (50ms) to ensure any pending audio chunk is fully processed
                    setTimeout(() => {
                      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                        wsRef.current.send(JSON.stringify({ type: 'speech_end' }));
                      }
                    }, 50);
                  }
                } catch (e) {
                  console.error("Error encoding speech WAV:", e);
                }
              }
            }
          })
            .then((myvad) => {
              console.log("VAD initialized successfully");
              vadRef.current = myvad;
              myvad.start();
            })
            .catch((err) => {
              console.error("VAD initialization failed:", err);
              setErrorMessage(`VAD failed to initialize: ${err.message || err}.`);
            });
        } else {
          console.warn("VAD script not found in window context");
          setErrorMessage("VAD script not loaded.");
        }
      })
      .catch((err) => {
        console.error("Microphone access denied or failed for VAD:", err);
      });


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
        agentId: selectedAgentId !== 'custom' ? parseInt(selectedAgentId) : undefined,
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
        }
      } else if (data.type === 'user_speech_transcript') {
        addTranscript('user', data.text);
      } else if (data.type === 'status') {
        if (data.status === 'thinking') {
          setStatus('thinking');
        } else if (data.status === 'listening') {
          setStatus('listening');
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
      fetchCalls();
    };
  };

  // Hang up the call
  const handleHangUp = () => {
    // Send hangup event
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'hang_up' }));
        wsRef.current.close();
      } catch (e) { }
    }

    // Stop MediaRecorder
    if (mediaRecorderRef.current) {
      try {
        if (mediaRecorderRef.current.state !== "inactive") {
          mediaRecorderRef.current.stop();
        }
      } catch (e) { }
      mediaRecorderRef.current = null;
    }

    // Stop mic stream tracks
    if (micStreamRef.current) {
      try {
        micStreamRef.current.getTracks().forEach(track => track.stop());
      } catch (e) { }
      micStreamRef.current = null;
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

    // Clean up Web Audio API context and nodes
    if (audioContextRef.current) {
      try {
        if (audioContextRef.current.state !== 'closed') {
          audioContextRef.current.close();
        }
      } catch (e) {
        console.error("Error closing AudioContext:", e);
      }
      audioContextRef.current = null;
    }
    micAnalyserRef.current = null;
    agentAnalyserRef.current = null;

    // Stop Speech Recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onend = null; // Prevent looping restart
        recognitionRef.current.stop();
      } catch (e) { }
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
        <div className="header-tabs">
          <button 
            className={`tab-btn ${activeTab === 'simulator' ? 'active' : ''}`}
            onClick={() => setActiveTab('simulator')}
            disabled={callActive}
          >
            <Phone className="h-4 w-4" />
            Simulator
          </button>
          <button 
            className={`tab-btn ${activeTab === 'agents' ? 'active' : ''}`}
            onClick={() => setActiveTab('agents')}
            disabled={callActive}
          >
            <Database className="h-4 w-4" />
            Agent Manager
          </button>
          <button 
            className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
            disabled={callActive}
          >
            <MessageSquare className="h-4 w-4" />
            Call History
          </button>
          <button 
            className={`tab-btn ${activeTab === 'bookings' ? 'active' : ''}`}
            onClick={() => { setActiveTab('bookings'); fetchBookingsAndLeads(); }}
            disabled={callActive}
          >
            <Calendar className="h-4 w-4" />
            Bookings & Leads
          </button>
        </div>
      </header>

      {/* Tab-based Main Grid */}
      {activeTab === 'simulator' && (
        <div className="dashboard-grid">
          {/* Left Column: Call Config Panel */}
          <section className="glass-panel">
            <div className="panel-header">
              <SettingsIcon className="panel-icon" />
              <h2 className="panel-title">Call Configurations</h2>
            </div>

            <div className="form-content">
              {/* Agent selector at the top */}
              <div className="agent-select-container">
                <label className="agent-select-label">Select Saved Agent</label>
                <select
                  value={selectedAgentId}
                  onChange={(e) => handleAgentSelectChange(e.target.value)}
                  className="input-field"
                  disabled={callActive}
                >
                  <option value="custom">Custom Configuration</option>
                  {agents.map(a => (
                    <option key={a.id} value={a.id.toString()}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Provider selection */}
              <div className="input-group">
                <label className="input-label">LLM Provider</label>
                <div className="provider-toggle-grid">
                  <button
                    onClick={() => { setProvider('gemini'); setModel('gemini-3.5-flash'); }}
                    className={`btn-toggle ${provider === 'gemini' ? 'active' : ''}`}
                    disabled={callActive || selectedAgentId !== 'custom'}
                  >
                    Google Gemini
                  </button>
                  <button
                    onClick={() => { setProvider('groq'); setModel('llama-3.1-8b-instant'); }}
                    className={`btn-toggle ${provider === 'groq' ? 'active' : ''}`}
                    disabled={callActive || selectedAgentId !== 'custom'}
                  >
                    Groq Cloud
                  </button>
                </div>
              </div>

              {/* Voice Selection */}
              <div className="input-group">
                <label className="input-label">Agent Accent & Voice</label>
                <select
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                  className="input-field"
                  disabled={callActive || selectedAgentId !== 'custom'}
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
                  disabled={callActive || selectedAgentId !== 'custom'}
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
                  disabled={callActive || selectedAgentId !== 'custom'}
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
              <canvas ref={canvasRef} width="350" height="70" className="visualizer-canvas" />
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
                  <>
                    {transcripts.map(log => {
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
                    })}
                    <div ref={transcriptEndRef} />
                  </>
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
      )}

      {/* Agents Manager Tab */}
      {activeTab === 'agents' && (
        <div className="agents-grid">
          {/* Saved Agents List */}
          <section className="glass-panel agents-list-panel">
            <div className="panel-header" style={{ marginBottom: '16px' }}>
              <Database className="panel-icon" style={{ color: 'var(--accent-cyan)' }} />
              <h2 className="panel-title">Saved Agent Personas</h2>
            </div>
            
            {agents.length === 0 ? (
              <div className="transcript-empty">
                <VolumeX className="transcript-empty-icon" />
                <p className="transcript-empty-text">
                  No saved agents found. Use the form to create your first agent persona.
                </p>
              </div>
            ) : (
              agents.map(a => (
                <div 
                  key={a.id} 
                  className={`agent-item-card ${selectedAgentId === a.id.toString() ? 'selected' : ''}`}
                  onClick={() => handleAgentSelectChange(a.id.toString())}
                >
                  <div className="agent-card-info">
                    <h3>{a.name}</h3>
                    <p>{a.system_prompt}</p>
                    <span className="agent-card-voice">{voices.find(v => v.id === a.voice_id)?.name || a.voice_id}</span>
                  </div>
                  <div className="agent-card-actions">
                    <button 
                      className="btn-icon edit" 
                      onClick={(e) => handleEditAgentClick(a, e)}
                      title="Edit Agent"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                    </button>
                    <button 
                      className="btn-icon delete" 
                      onClick={(e) => handleDeleteAgent(a.id, e)}
                      title="Delete Agent"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </section>

          {/* Create / Edit Form */}
          <section className="glass-panel">
            <div className="panel-header">
              <SettingsIcon className="panel-icon" />
              <h2 className="panel-title">{editingAgentId ? `Edit Agent: ${formName}` : 'Create New Agent Persona'}</h2>
            </div>
            
            <form onSubmit={handleSaveAgent} className="form-content" style={{ marginTop: '16px' }}>
              <div className="input-group">
                <label className="input-label">Agent Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="input-field"
                  placeholder="e.g. Alex (Support), Sarah (Billing)..."
                  required
                />
              </div>

              <div className="input-group">
                <label className="input-label">Agent Voice & Accent</label>
                <select
                  value={formVoice}
                  onChange={(e) => setFormVoice(e.target.value)}
                  className="input-field"
                >
                  {voices.map(v => (
                    <option key={v.id} value={v.id} className="bg-slate-900 text-white">
                      {v.name} ({v.gender})
                    </option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">Opening Greeting Line</label>
                <input
                  type="text"
                  value={formGreeting}
                  onChange={(e) => setFormGreeting(e.target.value)}
                  className="input-field"
                  placeholder="e.g. Hi! This is Sarah calling to follow up on your support ticket..."
                  required
                />
              </div>

              <div className="input-group">
                <label className="input-label">Agent Instructions & Prompt</label>
                <textarea
                  rows="5"
                  value={formPrompt}
                  onChange={(e) => setFormPrompt(e.target.value)}
                  className="input-field"
                  placeholder="Define goals, boundaries, and personality of your agent..."
                  required
                />
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                <button type="submit" className="btn-call-action start" style={{ flexGrow: 1, padding: '12px 18px', fontSize: '13px' }}>
                  {editingAgentId ? 'Update Agent Persona' : 'Save Agent Persona'}
                </button>
                {editingAgentId && (
                  <button 
                    type="button" 
                    className="btn-call-action hangup" 
                    style={{ padding: '12px 18px', fontSize: '13px' }}
                    onClick={() => {
                      setEditingAgentId(null);
                      setFormName('');
                      setFormPrompt('');
                      setFormGreeting('');
                    }}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </section>
        </div>
      )}

      {/* Call History Tab */}
      {activeTab === 'history' && (
        <div className="history-grid">
          {/* Left panel: List of Calls */}
          <section className="glass-panel history-list-container">
            <div className="panel-header" style={{ marginBottom: '16px' }}>
              <Activity className="panel-icon" style={{ color: 'var(--accent-cyan)' }} />
              <h2 className="panel-title">Call Logs History</h2>
            </div>
            
            {calls.length === 0 ? (
              <div className="transcript-empty">
                <VolumeX className="transcript-empty-icon" />
                <p className="transcript-empty-text">
                  No logged calls found. Call logs will appear here after calls are completed.
                </p>
              </div>
            ) : (
              calls.map(c => {
                const linkedAgent = agents.find(a => a.id === c.agent_id);
                const agentName = linkedAgent ? linkedAgent.name : "Custom Agent";
                const isSelected = activeHistoryCall && activeHistoryCall.id === c.id;
                
                return (
                  <div 
                    key={c.id} 
                    className={`history-card ${isSelected ? 'active' : ''}`}
                    onClick={() => setActiveHistoryCall(c)}
                  >
                    <div className="history-card-header">
                      <span className="history-agent-name">{agentName}</span>
                      <span className="history-date">
                        {new Date(c.start_time).toLocaleString()}
                      </span>
                    </div>
                    <div className="history-card-body">
                      <div className="history-stat">
                        <Clock className="h-3.5 w-3.5 text-slate-400" />
                        <span>{formatTime(c.duration)}</span>
                      </div>
                      <div className="history-stat">
                        <span className={`status-badge-inline ${c.status === 'completed' ? 'listening' : 'error'}`} style={{ padding: '1px 6px', fontSize: '10px' }}>
                          {c.status.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </section>

          {/* Right panel: Call Details & Transcript */}
          <section className="glass-panel history-detail-panel">
            {activeHistoryCall ? (
              <>
                <div className="history-detail-header">
                  <h2 style={{ fontSize: '20px', color: 'var(--text-primary)' }}>
                    Call Log Detail
                  </h2>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Started: {new Date(activeHistoryCall.start_time).toLocaleString()} • Duration: {formatTime(activeHistoryCall.duration)}
                  </p>
                </div>
                
                <div className="history-transcript-area">
                  {(() => {
                    try {
                      const transcriptLogs = JSON.parse(activeHistoryCall.transcription_log || '[]');
                      if (transcriptLogs.length === 0) {
                        return <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>No conversation transcript recorded.</p>;
                      }
                      return transcriptLogs.map((log, idx) => {
                        if (log.role === 'system') {
                          return (
                            <div key={idx} className="system-pill-wrapper">
                              <span className="system-pill">
                                {log.text || log.content}
                              </span>
                            </div>
                          );
                        }
                        const isAgent = log.role === 'agent' || log.role === 'assistant';
                        return (
                          <div 
                            key={idx} 
                            className={`bubble-wrapper ${isAgent ? 'agent' : 'user'}`}
                            style={{ margin: '8px 0' }}
                          >
                            <div className="bubble-content">
                              <p>{log.text || log.content}</p>
                            </div>
                            <span className="bubble-meta">
                              {isAgent ? 'Agent' : 'User'}
                            </span>
                          </div>
                        );
                      });
                    } catch (e) {
                      return <p style={{ color: 'var(--status-error)' }}>Error parsing transcript log JSON.</p>;
                    }
                  })()}
                </div>
              </>
            ) : (
              <div className="transcript-empty" style={{ margin: 'auto' }}>
                <MessageSquare className="transcript-empty-icon" style={{ opacity: 0.2 }} />
                <p className="transcript-empty-text">
                  Select a call from the history list to view the full details and transcription log.
                </p>
              </div>
            )}
          </section>
      {/* Bookings & Leads Tab */}
      {activeTab === 'bookings' && (
        <div className="history-grid" style={{ gap: '20px' }}>
          {/* Left Column: Appointments */}
          <section className="glass-panel" style={{ padding: '24px' }}>
            <div className="panel-header" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Calendar className="panel-icon" style={{ color: 'var(--accent-cyan)' }} />
                <h2 className="panel-title">Confirmed Appointments ({bookings.length})</h2>
              </div>
              <button onClick={fetchBookingsAndLeads} className="btn-icon" title="Refresh Bookings">
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>

            {bookings.length === 0 ? (
              <div className="transcript-empty" style={{ padding: '40px 0' }}>
                <Calendar className="transcript-empty-icon" style={{ opacity: 0.3 }} />
                <p className="transcript-empty-text">No active bookings yet. Start a call and ask the agent to book an appointment!</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '550px', overflowY: 'auto' }}>
                {bookings.map(b => (
                  <div key={b.id} className="agent-item-card" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <h3 style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)' }}>{b.customer_name}</h3>
                        <span className={`status-badge-inline ${b.status === 'confirmed' ? 'listening' : 'error'}`} style={{ padding: '2px 8px', fontSize: '10px' }}>
                          {b.status.toUpperCase()}
                        </span>
                      </div>
                      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        📞 {b.customer_phone} • 🛠️ {b.service_type}
                      </p>
                      <p style={{ fontSize: '12px', color: 'var(--accent-cyan)', marginTop: '2px', fontWeight: '500' }}>
                        📅 {b.booking_date} at {b.booking_time}
                      </p>
                      {b.notes && (
                        <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', fontStyle: 'italic' }}>
                          "{b.notes}"
                        </p>
                      )}
                    </div>
                    {b.status === 'confirmed' && (
                      <button 
                        onClick={() => handleCancelBooking(b.id)} 
                        className="btn-icon delete" 
                        title="Cancel Appointment"
                        style={{ padding: '8px' }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Right Column: Captured Leads */}
          <section className="glass-panel" style={{ padding: '24px' }}>
            <div className="panel-header" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity className="panel-icon" style={{ color: 'var(--accent-purple)' }} />
                <h2 className="panel-title">Captured Sales Leads ({leads.length})</h2>
              </div>
              <button onClick={fetchBookingsAndLeads} className="btn-icon" title="Refresh Leads">
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>

            {leads.length === 0 ? (
              <div className="transcript-empty" style={{ padding: '40px 0' }}>
                <Activity className="transcript-empty-icon" style={{ opacity: 0.3 }} />
                <p className="transcript-empty-text">No captured leads recorded yet.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '550px', overflowY: 'auto' }}>
                {leads.map(l => (
                  <div key={l.id} className="agent-item-card" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <h3 style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)' }}>{l.name}</h3>
                        <span className="status-badge-inline thinking" style={{ padding: '2px 8px', fontSize: '10px' }}>
                          LEAD
                        </span>
                      </div>
                      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        📞 {l.phone}
                      </p>
                      <p style={{ fontSize: '12px', color: 'var(--text-primary)', marginTop: '4px' }}>
                        <strong>Intent:</strong> {l.intent || 'General Inquiry'}
                      </p>
                      <p style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        Captured: {new Date(l.created_at).toLocaleString()}
                      </p>
                    </div>
                    <button 
                      onClick={() => handleDeleteLead(l.id)} 
                      className="btn-icon delete" 
                      title="Delete Lead"
                      style={{ padding: '8px' }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
