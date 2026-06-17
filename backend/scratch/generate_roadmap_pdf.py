import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

class DhwaniRoadmapPDF(FPDF):
    def header(self):
        # Draw top accent bar on all pages except the cover page
        if self.page_no() > 1:
            self.set_fill_color(30, 41, 59) # Slate 800
            self.rect(0, 0, 210, 10, "F")
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 8)
            self.set_y(2)
            self.cell(0, 6, "DHWANI: TECHNICAL SPECIFICATION, SYSTEM WORKING & FUTURE ROADMAP", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_y(15)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184) # Slate 400
        self.cell(120, 10, "Dhwani Project Suite | Guide to Working & Next Steps Roadmap", align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def create_cover_page(self):
        self.add_page()
        # Top decorative band
        self.set_fill_color(30, 41, 59) # Slate 800
        self.rect(0, 0, 210, 80, "F")
        
        # Bottom decorative band accent
        self.set_fill_color(15, 118, 110) # Teal 700
        self.rect(0, 80, 210, 5, "F")
        
        # Cover Title
        self.set_y(30)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 36)
        self.cell(0, 15, "D H W A N I", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        self.set_font("Helvetica", "", 14)
        self.cell(0, 10, "Working Principles, Technical Specs & What To Do Next", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        # Subtitle / Details
        self.set_y(105)
        self.set_text_color(51, 65, 85) # Slate 700
        self.set_font("Helvetica", "B", 18)
        self.cell(0, 10, "COMPLETE GUIDE & ENGINEERING ROADMAP", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        # Decorative divider line
        self.set_draw_color(226, 232, 240) # Slate 200
        self.set_line_width(0.5)
        self.line(40, 120, 170, 120)
        
        self.set_y(130)
        self.set_font("Helvetica", "", 11)
        
        # Metadata Table
        metadata = [
            ("Project Name:", "Dhwani (AI Voice Agent Suite)"),
            ("Document Type:", "Architecture Walkthrough & Development Backlog"),
            ("Prepared By:", "Antigravity AI Assistant"),
            ("Target Audience:", "Vatshal, Engineering Teams, Reviewers"),
            ("Status:", "Version 1.0 (WebSocket Core Operational)"),
            ("Next Milestones:", "VAD barge-in, Server STT, Telephony Trunks"),
        ]
        
        for label, val in metadata:
            self.set_x(35)
            self.set_font("Helvetica", "B", 10)
            self.cell(40, 7, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_font("Helvetica", "", 10)
            self.cell(100, 7, val, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
        # Footer notice on Cover Page
        self.set_y(240)
        self.set_text_color(100, 116, 139) # Slate 500
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, "This document walks you through the active codebase, details the real-time pipeline,", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 5, "and lists actionable future features (with system changes) to build a production-grade", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 5, "voice AI agent that matches market leaders like Vapi, Retell AI, and Bland AI.", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def write_section_header(self, num, title):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(15, 118, 110) # Teal 700
        self.cell(0, 10, f"{num}. {title.upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(15, 118, 110)
        self.set_line_width(0.5)
        self.line(self.get_x(), self.get_y(), self.get_x() + 180, self.get_y())
        self.ln(4)

    def write_subsection_header(self, title):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(30, 41, 59) # Slate 800
        self.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def write_paragraph(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(51, 65, 85) # Slate 700
        self.multi_cell(0, 5, text)
        self.ln(2)

    def write_bullet_point(self, title, description):
        self.set_x(20)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 41, 59)
        self.cell(4, 5, "-", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(45, 5, title, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 5, description)
        self.ln(1)

def generate_roadmap_report():
    pdf = DhwaniRoadmapPDF()
    pdf.alias_nb_pages()
    
    # Page 1: Cover
    pdf.create_cover_page()
    
    # Page 2: How It Works Today
    pdf.add_page()
    pdf.set_y(20)
    pdf.write_section_header("1", "Under-the-Hood: How Dhwani Works Today")
    
    pdf.write_paragraph(
        "Dhwani is currently built as a light, high-performance duplex voice pipeline that utilizes WebSockets "
        "to coordinate real-time audio playback and user transcription turns. This architecture consists of:"
    )
    
    pdf.write_subsection_header("1.1 Frontend Client-Side (Browser Context)")
    pdf.write_paragraph(
        "Built in React, the UI handles state changes (dialing, connected, listening, thinking, speaking) and manages browser hardware APIs. "
        "It uses the browser's native Web Speech API (window.SpeechRecognition) to capture user speech. When the user speaks, the browser "
        "transcribes the audio locally to plain text and sends the final string to the backend. This saves server CPU and bandwidth. "
        "To play the agent's voice, the frontend decodes base64-encoded MP3 chunks received from the WebSocket into a dynamic HTML5 Audio element."
    )
    
    pdf.write_subsection_header("1.2 Backend Server-Side (FastAPI Context)")
    pdf.write_paragraph(
        "Built as an asynchronous FastAPI python backend, the server exposes a WebSocket endpoint /ws/call. It maintains session configurations "
        "(system prompts, provider choices, voices) and holds the ongoing conversation history list in memory. "
        "When it receives text from the frontend, it queries the configured LLM (Google Gemini or Groq Cloud) and feeds the text response "
        "into edge-tts. edge-tts generates an MP3 byte stream using Microsoft's realistic neural voices. The backend base64-encodes this audio "
        "and pushes it back to the client."
    )
    
    pdf.write_subsection_header("1.3 Echo Prevention Mechanism")
    pdf.write_paragraph(
        "A critical engineering challenge in browser-based voice systems is acoustic loopback (the microphone picking up the agent's voice "
        "and transcribing it). Dhwani solves this by programmatically pausing the SpeechRecognition listener on the frontend immediately "
        "before the HTML5 Audio element starts playing. The frontend hooks into the audio's 'onended' callback. Once the agent is done speaking, "
        "the listener is resumed, opening the mic for the user."
    )

    # Page 3: What to Do Next - Core Enhancements (Roadmap Part 1)
    pdf.add_page()
    pdf.set_y(20)
    pdf.write_section_header("2", "What to Do Next: Core Feature Enhancements")
    
    pdf.write_paragraph(
        "To take Dhwani from a local testing simulator to a production-grade commercial platform like Retell AI, Vapi, or Bland AI, "
        "the following modules need to be implemented next. These are ordered by engineering priority:"
    )
    
    pdf.write_subsection_header("Priority 1: Voice Activity Detection (VAD) & Barge-in Handling")
    pdf.write_bullet_point("The Problem:", "Currently, if the agent is speaking and the user starts talking, the agent cannot be interrupted. The user must wait until the agent finishes playing, which ruins conversational flow.")
    pdf.write_bullet_point("The Solution:", "Implement Client-Side or Server-Side VAD (e.g., using silero-vad or WebRTC VAD). If the user starts speaking, the frontend must immediately fire a 'mute/interrupt' event, stop the active HTML5 Audio playback, clear the audio queue on both ends, and switch back to listening state.")
    
    pdf.write_subsection_header("Priority 2: Transition to Binary Audio Streaming (WebRTC / Raw Audio)")
    pdf.write_bullet_point("The Problem:", "Relying on browser-native SpeechRecognition is inconsistent because text finalization has latency, and it requires specific browsers. It does not work well in silent or noisy backgrounds.")
    pdf.write_bullet_point("The Solution:", "Capture raw mic audio chunks via MediaRecorder API or Web Audio API, encode them into low-latency format (like PCM or Opus), and stream them as binary chunks over the WebSocket. On the backend, process these streams using a fast STT engine like Whisper (via Groq/OpenAI) or Deepgram.")

    pdf.write_subsection_header("Priority 3: Ultra-Low-Latency Voice Engines")
    pdf.write_bullet_point("The Problem:", "edge-tts is free, but it takes 800ms-1200ms to synthesize speech because it is a wrapper that waits for the full text before streaming the bytes.")
    pdf.write_bullet_point("The Solution:", "Integrate Cartesia (Sonic-beta) or ElevenLabs (Turbo v2) streaming APIs. By sending LLM output chunks to these providers as they generate, we can get audio bytes back in under 150ms, resulting in realistic conversation.")

    # Page 4: Advanced Features & Database Architecture (Roadmap Part 2)
    pdf.add_page()
    pdf.set_y(20)
    pdf.write_section_header("3", "Advanced Enhancements: Production Architecture")
    
    pdf.write_paragraph(
        "Beyond core voice loops, production deployment requires background storage, telemetry, and external systems integration:"
    )
    
    pdf.write_subsection_header("3.1 Telephony Integrations (Real Phone Calls)")
    pdf.write_paragraph(
        "Currently, calls are browser-simulated. To make and receive real phone calls, you should configure "
        "Twilio Media Streams or Telnyx SIP trunks. In this design, Twilio makes/receives the PSTN call, opens a WebSocket "
        "directly to your FastAPI server, and streams bidirectional u-law (PCMU) 8kHz audio. The FastAPI server processes "
        "this binary steam, routes it to Whisper/Deepgram STT, queries the LLM, and streams PCMU back to Twilio."
    )
    
    pdf.write_subsection_header("3.2 RAG (Retrieval-Augmented Generation) & Knowledge Bases")
    pdf.write_paragraph(
        "For agents to talk about specific businesses (e.g., dentist schedules, e-commerce orders, product manuals), they need "
        "access to external documents. You should integrate a Vector Database (like Qdrant, Pinecone, or pgvector) and build a RAG pipeline. "
        "When the user asks a question, the backend performs a semantic search on the vector DB, retrieves the relevant context, and appends "
        "it to the LLM system prompt so the model responds with accurate information."
    )
    
    pdf.write_subsection_header("3.3 Persistent Database Schema (SQLite/PostgreSQL)")
    pdf.write_paragraph(
        "Currently, configuration, keys, and transcripts exist only in memory and localStorage. You should add database tables to persist:"
    )
    pdf.write_bullet_point("Agents Table:", "Stores agent profiles (id, name, voice_id, temperature, system_prompt, greeting, creator_id).")
    pdf.write_bullet_point("Calls Table:", "Logs call details (call_id, agent_id, start_time, duration, status, transcription_log_json, cost).")
    pdf.write_bullet_point("API Keys Table:", "Saves user credentials securely using encryption at rest.")
    
    pdf.write_subsection_header("3.4 Visual Architecture Design of Production System")
    
    diagram = [
        "  [User Phone] <--(PSTN / Twilio SIP)--> [Twilio Media Stream / WebSockets]",
        "                                                    |",
        "                                         (PCM/u-Law Audio Streams)",
        "                                                    v",
        "  +-------------------------------------------------------------------------+",
        "  |                          FASTAPI ORCHESTRATOR                           |",
        "  |                                                                         |",
        "  |  +------------------+    +-----------------+    +--------------------+  |",
        "  |  | Deepgram STT     |    | LLM Handler     |    | Cartesia TTS       |  |",
        "  |  | (Streaming Audio |--> | (Retrieves RAG  |--> | (Streams response  |  |",
        "  |  |  to text text)   |    |  from Qdrant DB)|    |  back dynamically) |  |",
        "  |  +------------------+    +-----------------+    +--------------------+  |",
        "  +-------------------------------------------------------------------------+"
    ]
    
    pdf.set_font("Courier", "", 9)
    pdf.set_text_color(30, 41, 59)
    for line in diagram:
        pdf.cell(0, 4.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)

    # Page 5: Actionable Developer Checklist
    pdf.add_page()
    pdf.set_y(20)
    pdf.write_section_header("4", "Actionable Step-by-Step Developer Checklist")
    
    pdf.write_paragraph(
        "Here is the exact task list to start building out the next phases. Use this checklist as your roadmap:"
    )
    
    pdf.write_subsection_header("Phase 1: Environment & Tool Setup (Immediate)")
    pdf.write_bullet_point("Step 1.1:", "Create a new git branch 'feature/vad-and-audio-stream' to isolate changes.")
    pdf.write_bullet_point("Step 1.2:", "Add database requirements to requirements.txt (SQLAlchemy, alembic, greenlet).")
    pdf.write_bullet_point("Step 1.3:", "Configure a local SQLite database and write database initialization models.")
    
    pdf.write_subsection_header("Phase 2: Code Refactoring - WebSocket Upgrades")
    pdf.write_bullet_point("Step 2.1:", "In app/main.py, change WebSocket receiver from handle_text to accept binary packets.")
    pdf.write_bullet_point("Step 2.2:", "Integrate PyAudio or sounddevice on a local debug test script to verify raw recordings.")
    pdf.write_bullet_point("Step 2.3:", "Implement a client-side audio capture loop in App.jsx using MediaRecorder API.")
    
    pdf.write_subsection_header("Phase 3: Interruption (Barge-In) Logic")
    pdf.write_bullet_point("Step 3.1:", "Add 'interrupt' packet type in the WebSocket communication protocol.")
    pdf.write_bullet_point("Step 3.2:", "In App.jsx, add an listener that monitors when input volume crosses a noise threshold.")
    pdf.write_bullet_point("Step 3.3:", "On noise threshold trigger, call audioRef.current.pause() and emit 'interrupt' over WS.")
    
    pdf.write_subsection_header("Phase 4: Deepgram & Cartesia Integration")
    pdf.write_bullet_point("Step 4.1:", "Sign up for Deepgram and Cartesia APIs, and add credentials in your backend .env file.")
    pdf.write_bullet_point("Step 4.2:", "Replace browser STT with Deepgram Streaming STT inside backend app/main.py WebSocket loop.")
    pdf.write_bullet_point("Step 4.3:", "Replace edge-tts with Cartesia streaming inside app/tts.py to achieve sub-200ms latency.")
    
    pdf.write_subsection_header("Summary Note:")
    pdf.write_paragraph(
        "By following this guide, you will transition Dhwani from a simple sequential text/voice exchange prototype "
        "into a state-of-the-art, low-latency, conversational voice agent capable of handling interruptions, real phone lines, "
        "and production-level scale."
    )

    # Save the PDF to the workspace root
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dhwani_system_architecture.pdf"))
    pdf.output(output_path)
    print(f"Roadmap report successfully generated at: {output_path}")

if __name__ == "__main__":
    generate_roadmap_report()
