import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

class DhwaniReportPDF(FPDF):
    def header(self):
        # Draw top accent bar on all pages except the cover page
        if self.page_no() > 1:
            self.set_fill_color(30, 41, 59) # Slate 800
            self.rect(0, 0, 210, 10, "F")
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 8)
            # Offset text down slightly inside the 10mm bar
            self.set_y(2)
            self.cell(0, 6, "DHWANI: OUTBOUND AI VOICE AGENT SIMULATOR - SYSTEM SPECIFICATION DOCUMENT", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            # Reset cursor below the header bar
            self.set_y(15)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184) # Slate 400
        # Left side: Date & Project
        self.cell(120, 10, "Dhwani Project Suite | Comprehensive Reference Architecture Document", align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
        # Right side: Page Number
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
        self.cell(0, 10, "Outbound AI Voice Agent Simulation Suite", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        # Subtitle / Details
        self.set_y(105)
        self.set_text_color(51, 65, 85) # Slate 700
        self.set_font("Helvetica", "B", 18)
        self.cell(0, 10, "SYSTEM ARCHITECTURE & PIPELINE REPORT", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        # Decorative divider line
        self.set_draw_color(226, 232, 240) # Slate 200
        self.set_line_width(0.5)
        self.line(40, 120, 170, 120)
        
        self.set_y(130)
        self.set_font("Helvetica", "", 11)
        
        # Metadata Table
        metadata = [
            ("Project Name:", "Dhwani (AI Voice Agent Simulator)"),
            ("Document Type:", "System Architecture, Design & Data Pipeline Reference"),
            ("Author:", "Antigravity AI Assistant"),
            ("Target Audience:", "Evaluators, Engineers, and Project Reviewers"),
            ("Status:", "Operational Prototype Successfully Deployed"),
            ("Core Services:", "FastAPI, React.js, Web Speech API, Microsoft Edge-TTS"),
            ("Supported LLMs:", "Google Gemini 3.5 Flash, Groq Cloud (Llama 3.1)"),
        ]
        
        for label, val in metadata:
            self.set_x(35)
            self.set_font("Helvetica", "B", 10)
            self.cell(40, 7, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_font("Helvetica", "", 10)
            self.cell(100, 7, val, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
        # Footer notice on Cover Page
        self.set_y(245)
        self.set_text_color(100, 116, 139) # Slate 500
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, "This document contains a comprehensive breakdown of the voice synthesis,", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 5, "large language model integration, browser-native speech recognition, and system design", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 5, "to ensure readiness for project evaluations and technical walkthroughs.", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def write_section_header(self, num, title):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(15, 118, 110) # Teal 700
        self.cell(0, 10, f"{num}. {title.upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Accent line below section header
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
        # Use simple dash '-' instead of Unicode bullet point to avoid encoding issues
        self.cell(4, 5, "-", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(45, 5, title, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 5, description)
        self.ln(1)

def generate_report():
    pdf = DhwaniReportPDF()
    pdf.alias_nb_pages()
    
    # 1. Cover Page
    pdf.create_cover_page()
    
    # ================= PAGE 2 =================
    pdf.add_page()
    pdf.set_y(20)
    
    pdf.write_section_header("1", "Executive Summary & The Sole Purpose of Dhwani")
    pdf.write_paragraph(
        "Dhwani is a real-time, low-latency conversational simulation suite designed for testing, prototyping, "
        "and evaluating outbound AI Voice Agents. By establishing a duplex WebSocket connection between browser-native "
        "APIs and a backend Python service, Dhwani mimics an actual voice call experience directly inside a standard web browser."
    )
    
    pdf.write_subsection_header("The Sole Purpose of the Project:")
    pdf.write_paragraph(
        "The primary purpose of Dhwani is to solve the high barrier of entry, high cost, and slow iteration cycle associated with "
        "developing voice-based LLM agents. Normally, testing an outbound conversational voice agent requires setting up expensive telephony "
        "connections, renting virtual numbers, configuring SIP trunks (via Twilio or Telnyx), and routing audio streams into paid orchestrators "
        "like Retell AI or Vapi. This creates immense friction during early engineering phases.\n\n"
        "Dhwani bridges this gap by acting as a zero-cost local simulator. It bypasses telephony networks entirely, substituting "
        "them with the browser microphone, browser-native Speech-to-Text, and a high-performance backend orchestrator. Developers "
        "can interactively test, debug, and demo their voice scripts, system prompts, latency bottlenecks, and voice accents "
        "instantly and for free."
    )
    
    pdf.write_subsection_header("Key Project Objectives:")
    pdf.write_bullet_point("Interactive Prototyping:", "Allows engineers to tune outbound calling agents (e.g. appointment confirmers, lead qualifiers) interactively prior to production deployment.")
    pdf.write_bullet_point("Accurate Prompt Engineering:", "Test how LLM models adhere to strict instructions (like 'keep responses under two sentences' or 'speak empathetically') under voice-turn conditions.")
    pdf.write_bullet_point("Voice Accent Customization:", "Evaluate multiple synthetic voices and accents (US, UK, French, German) to match target demographics without altering configuration code.")
    pdf.write_bullet_point("Bandwidth & Cost Optimization:", "Utilizes browser-based Speech-to-Text, sending only light text strings to the server, preserving network bandwidth and avoiding expensive audio upload processing costs.")

    # ================= PAGE 3 =================
    pdf.add_page()
    pdf.set_y(20)
    
    pdf.write_section_header("2", "High-Level Architecture & Tech Stack")
    pdf.write_paragraph(
        "Dhwani utilizes a modular, client-server architecture. It operates via stateful WebSocket sessions "
        "to maintain context and minimize audio transmission overhead. Below is the technical breakdown:"
    )
    
    pdf.write_subsection_header("Technology Stack Elements:")
    pdf.write_bullet_point("Frontend UI (React + Vite):", "A highly responsive glassmorphic dashboard built using React. It coordinates state transitions, renders the simulated calling layout, and tracks session timers.")
    pdf.write_bullet_point("Backend Server (FastAPI):", "An asynchronous, high-concurrency Python web framework that handles JSON messages and coordinates streaming logic over WebSocket.")
    pdf.write_bullet_point("Speech-to-Text (STT):", "Browser-native Web Speech API (SpeechRecognition). It performs local transcription directly inside the client's browser, eliminating raw audio upload latency.")
    pdf.write_bullet_point("Text-to-Speech (TTS):", "Edge-TTS package, wrapping Microsoft's Azure Cognitive Speech Synthesis. Generates highly realistic, expressive neural voices without requiring paid API keys.")
    pdf.write_bullet_point("LLM Brain Options:", "Google Gemini API (Gemini 3.5 Flash) and Groq Cloud (Llama 3.1). These providers act as the natural language generation engines.")
    
    pdf.write_subsection_header("Conceptual Pipeline Topology Diagram:")
    
    # Draw ASCII Diagram representing the flow
    diagram_lines = [
        "   +-------------------------------------------------------------+",
        "   |                        BROWSER CLIENT                       |",
        "   |                                                             |",
        "   |  +--------------------+             +--------------------+  |",
        "   |  |   HTML5 Audio      |             |  Web Speech API    |  |",
        "   |  |  (Plays Response)  |             |  (Local Client STT)|  |",
        "   |  +---------^----------+             +---------|----------+  |",
        "   +------------|----------------------------------|-------------+",
        "                |                                  |",
        "         Base64 Audio Bytes                 User Text Transcript",
        "         (Websocket Push)                   (Websocket Send)",
        "                |                                  |",
        "   +------------|----------------------------------|-------------+",
        "   |            |             FASTAPI SERVER       v             |",
        "   |   +--------|-------+                  +------------------+  |",
        "   |   |   TTS Service  |                  |   LLM Service    |  |",
        "   |   |   (Edge TTS)   |                  |  (Gemini / Groq) |  |",
        "   |   +----------------+                  +------------------+  |",
        "   +-------------------------------------------------------------+"
    ]
    
    pdf.set_font("Courier", "", 9)
    pdf.set_text_color(30, 41, 59)
    for line in diagram_lines:
        pdf.cell(0, 4.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)

    # ================= PAGE 4 =================
    pdf.add_page()
    pdf.set_y(20)
    
    pdf.write_section_header("3", "The End-to-End Pipeline Execution Flow")
    pdf.write_paragraph(
        "A conversational session consists of two distinct parts: a setup sequence, followed by an "
        "alternating, state-controlled turn-taking loop between the user and the agent."
    )
    
    pdf.write_subsection_header("Step 1: Session Handshake & Configuration")
    pdf.write_paragraph(
        "The browser opens a stateful connection to the backend via 'ws://localhost:8000/ws/call'. "
        "Upon connection, the frontend sends a 'start_call' JSON payload containing system configurations "
        "(system instructions, agent voice accent selection, LLM provider settings, and opening greeting)."
    )
    
    pdf.write_subsection_header("Step 2: Greeting Synthesizing & Playback")
    pdf.write_paragraph(
        "The FastAPI server initializes the LLM wrapper and invokes the Microsoft Edge-TTS library to convert the "
        "pre-set greeting text into speech. The synthesized audio bytes are returned as a Base64-encoded MP3 stream. "
        "The browser client receives the payload, decodes the audio, programmatically mutes the microphone to avoid "
        "feedback echo, and plays it. Once the audio completes, the mic is unmuted to listen to the user."
    )
    
    pdf.write_subsection_header("Step 3: User Speech Capture & Local Transcription")
    pdf.write_paragraph(
        "The user talks into their microphone. The Web Speech API listens and outputs real-time, interim speech transcripts. "
        "Once the user stops talking, the browser's SpeechRecognition engine fires the final callback, obtaining the final "
        "transcribed text. Doing this locally saves significant network overhead and cloud costs."
    )

    pdf.write_subsection_header("Step 4: AI Reply Generation")
    pdf.write_paragraph(
        "The final transcript is sent to the backend FastAPI server via the active WebSocket. The server updates the "
        "conversational session state to 'thinking' and logs the prompt history. It queries the user's selected LLM provider "
        "(Gemini or Groq) using the updated chat history and custom system instruction parameters."
    )
    
    pdf.write_subsection_header("Step 5: Voice Generation & Playback Loop")
    pdf.write_paragraph(
        "The generated text response is immediately sent to the Edge-TTS engine to synthesize the speech audio. "
        "The server pushes a JSON message containing the AI reply text and the Base64 audio stream. "
        "The browser plays the audio (programmatically muting the microphone during playback), displays the text on the "
        "screen, and reactivates speech recognition when the playback concludes, ready for the next user turn."
    )

    # ================= PAGE 5 =================
    pdf.add_page()
    pdf.set_y(20)
    
    pdf.write_section_header("4", "File-by-File Codebase Walkthrough")
    pdf.write_paragraph(
        "Below is a structural index of the project's files, outlining the role that each script plays in the system:"
    )
    
    pdf.write_subsection_header("Backend Components (backend/app/):")
    
    pdf.write_bullet_point("app/main.py (Application Router & Websocket Controller)", 
                           "This is the entry point. It hosts the FastAPI app instance, provides configuration APIs for frontend setup, "
                           "and handles the websocket endpoint '/ws/call'. It acts as the orchestrator, controlling turn-taking by handling messages like 'start_call', 'user_speech', and 'hang_up'.")
                           
    pdf.write_bullet_point("app/config.py (Settings Loader)", 
                           "Implements a Settings class that inherits from Pydantic's BaseSettings. It loads variables from the local '.env' file, "
                           "providing credentials (GEMINI_API_KEY, GROQ_API_KEY) and defaults (LLM provider, model type, port) across the backend modules.")
                           
    pdf.write_bullet_point("app/llm.py (LLM Provider Interface)", 
                           "Hosts LLMService. Integrates both Google Generative AI (using the new gemini-3.5-flash model) and Groq Client "
                           "libraries. Standardizes input history shapes and queries the requested model. It receives chat histories and applies the custom system prompts dynamically.")
                           
    pdf.write_bullet_point("app/tts.py (Voice Synthesis Engine)", 
                           "Hosts TTSService. Integrates with the 'edge-tts' package. It uses Microsoft's neural voices, streams audio chunk-by-chunk "
                           "locally, and collects raw MP3 bytes. It also defines a static list of curated voices (US, UK, French, German, Spanish).")

    pdf.write_subsection_header("Frontend Components (frontend/src/):")
    
    pdf.write_bullet_point("src/App.jsx (Client Controller & Interface Layout)", 
                           "Contains the entire state and logic of the UI. It instantiates the Web Speech API's SpeechRecognition controller, "
                           "manages websocket open/close connections, plays incoming base64 MP3 files using HTML5 Audio elements, "
                           "and coordinates microphone activation states to prevent speech loopbacks (echo).")
                           
    pdf.write_bullet_point("src/index.css & App.css (Styling & Visual Design)", 
                           "Implements the modern glassmorphic dashboard styling. Features dark backgrounds, glowing circular voice-state visualizers, "
                           "sliding settings drawers, and dynamic CSS animations representing audio waveforms.")

    # ================= PAGE 6 =================
    pdf.add_page()
    pdf.set_y(20)
    
    pdf.write_section_header("5", "Troubleshooting & Viva/Evaluation Reference")
    pdf.write_paragraph(
        "Use this section to prepare for technical reviews. It explains design justifications and core FAQs."
    )
    
    pdf.write_subsection_header("Core Design Trade-offs & Decisions:")
    pdf.write_bullet_point("Client-Side STT vs Server-Side STT:", "Client-side recognition (browser Web Speech API) is free, requires no server compute, and is exceptionally low-latency. However, it requires modern engines (Chrome/Edge) and cannot record raw audio on the backend easily.")
    pdf.write_bullet_point("Edge TTS vs Premium Cloud TTS:", "Edge TTS generates highly realistic natural voices for free. It is ideal for simulation. For a full production system, paid APIs like ElevenLabs offer lower latency tuning and custom voice cloning.")
    pdf.write_bullet_point("WebSocket vs REST HTTP API:", "WebSockets keep a stateful TCP tunnel open. This maintains the LLM chat history in server memory during the call. It removes connection overhead on each turn, bringing average latency down.")

    pdf.write_subsection_header("Frequently Asked Evaluation Questions (Q&A):")
    
    pdf.write_bullet_point("Q1: How does Dhwani prevent the feedback loop (microphone picking up agent speech)?", 
                           "During agent speech, the frontend programmatically stops the SpeechRecognition engine. It listens to the HTML5 Audio 'onended' event, and only reactivates the microphone once the audio playback has completely stopped.")
                           
    pdf.write_bullet_point("Q2: Why does the project use WebSockets instead of HTTP request/response?", 
                           "Outbound voice simulation requires immediate, asynchronous status updates (e.g. telling the frontend when the backend starts 'thinking' or 'speaking'). WebSockets enable full-duplex communication, letting the server push state changes instantly.")
                           
    pdf.write_bullet_point("Q3: How are custom LLM credentials handled in the application?", 
                           "The backend reads default API keys from the '.env' file. However, users can also input custom keys in the frontend settings panel. The frontend passes these custom credentials in the setup message, allowing developers to test with their own quotas.")
                           
    pdf.write_bullet_point("Q4: What happens if the network drops mid-call?", 
                           "The FastAPI server detects a WebSocketDisconnect event and gracefully cleans up resources. The React frontend updates its status to 'disconnected' and resets the call states, preventing stale audio loops.")

    # Save the PDF to the workspace root
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dhwani_system_architecture.pdf"))
    pdf.output(output_path)
    print(f"Report successfully generated at: {output_path}")

if __name__ == "__main__":
    generate_report()
