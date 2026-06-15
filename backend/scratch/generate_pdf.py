import os
from fpdf import FPDF

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
            self.cell(0, 6, "DHWANI: OUTBOUND AI VOICE AGENT SIMULATOR", align="C", ln=1)
            # Reset cursor below the header bar
            self.set_y(15)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184) # Slate 400
        # Left side: Date & Project
        self.cell(100, 10, "Dhwani Project Suite • System Reference Document", align="L")
        # Right side: Page Number
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="R")

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
        self.set_font("Helvetica", "B", 32)
        self.cell(0, 15, "D H W A N I", align="C", ln=1)
        
        self.set_font("Helvetica", "", 14)
        self.cell(0, 10, "Outbound AI Voice Agent Simulation Suite", align="C", ln=1)
        
        # Subtitle / Details
        self.set_y(110)
        self.set_text_color(51, 65, 85) # Slate 700
        self.set_font("Helvetica", "B", 18)
        self.cell(0, 10, "SYSTEM ARCHITECTURE & PIPELINE REPORT", align="C", ln=1)
        
        # Decorative divider line
        self.set_draw_color(226, 232, 240) # Slate 200
        self.set_line_width(0.5)
        self.line(40, 125, 170, 125)
        
        self.set_y(135)
        self.set_font("Helvetica", "", 11)
        
        # Metadata Table (Centered manually using offsets)
        metadata = [
            ("Project Name:", "Dhwani (AI Voice Agent Simulator)"),
            ("Document Type:", "System Architecture, Design & Data Pipeline Reference"),
            ("Author:", "Antigravity AI Assistant"),
            ("Target Audience:", "Stakeholders, Engineers, and Project Evaluators"),
            ("Status:", "Working Prototype Operational"),
        ]
        
        for label, val in metadata:
            self.set_x(35)
            self.set_font("Helvetica", "B", 10)
            self.cell(40, 7, label, ln=0)
            self.set_font("Helvetica", "", 10)
            self.cell(100, 7, val, ln=1)
            
        # Footer notice on Cover Page
        self.set_y(250)
        self.set_text_color(100, 116, 139) # Slate 500
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, "This document contains a comprehensive breakdown of the voice synthesis,", align="C", ln=1)
        self.cell(0, 5, "large language model, and browser-native speech recognition pipeline.", align="C", ln=1)

    def write_section_header(self, num, title):
        self.ln(6)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(15, 118, 110) # Teal 700
        self.cell(0, 10, f"{num}. {title.upper()}", ln=1)
        # Accent line below section header
        self.set_draw_color(15, 118, 110)
        self.set_line_width(0.5)
        self.line(self.get_x(), self.get_y(), self.get_x() + 180, self.get_y())
        self.ln(4)

    def write_subsection_header(self, title):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(30, 41, 59) # Slate 800
        self.cell(0, 7, title, ln=1)

    def write_paragraph(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(51, 65, 85) # Slate 700
        self.multi_cell(0, 5, text)
        self.ln(2)

    def write_bullet_point(self, title, description):
        self.set_x(20)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 41, 59)
        self.cell(3, 5, "•", ln=0)
        self.cell(35, 5, title, ln=0)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 5, description)
        self.ln(1)

def generate_report():
    pdf = DhwaniReportPDF()
    pdf.alias_nb_pages()
    
    # 1. Cover Page
    pdf.create_cover_page()
    
    # 2. Main Content
    pdf.add_page()
    pdf.set_y(20)
    
    pdf.write_section_header("1", "Executive Summary & Purpose")
    pdf.write_paragraph(
        "Dhwani is a real-time, low-latency conversational simulation suite designed for testing, prototyping, "
        "and evaluating outbound AI Voice Agents. By establishing a bridge between browser-native APIs and backend "
        "large language models, the application achieves a voice call dynamic that runs inside a standard web browser."
    )
    
    pdf.write_subsection_header("Primary Objectives of the System:")
    pdf.write_bullet_point("Interactive Prototyping:", "Evaluate outbound calling scenarios, agent responses, and sales scripts before executing telephony calls on live carriers.")
    pdf.write_bullet_point("Latency Optimization:", "Test and benchmark latency spikes between different LLM backends (such as Google Gemini and Groq Cloud) and speech generators.")
    pdf.write_bullet_point("Voice Persona Design:", "Experiment with diverse system prompts and neural accents to match target user demographics without modifying telephone trunks.")
    pdf.write_bullet_point("Cost Efficiency:", "Avoid paying expensive per-minute VoIP carrier fees during the design and initial QA phases.")

    pdf.write_section_header("2", "High-Level Architecture")
    pdf.write_paragraph(
        "The project is structured under a modern Client-Server topology. Communication is established via a "
        "persistent, stateful WebSocket connection to support fast exchange of text and raw voice data."
    )
    
    pdf.write_bullet_point("Frontend App:", "A React application built on Vite. It utilizes the native browser Web Speech API (SpeechRecognition) for local client-side voice transcription and handles audio element playback.")
    pdf.write_bullet_point("Backend Server:", "A FastAPI Python server that coordinates the conversation flow, hosts REST API config routes, manages LLM integrations (Gemini & Groq), and invokes Text-to-Speech (TTS) engines.")
    pdf.write_bullet_point("LLM Service:", "A wrapper class that structures multi-turn chat records, manages system instructions, and requests generative response completions.")
    pdf.write_bullet_point("TTS Service:", "Uses the edge-tts library to dynamically communicate with Microsoft's neural translation and speech synthesis platform, generating voice responses.")

    # Next page for data pipeline detail
    pdf.add_page()
    pdf.set_y(20)
    
    pdf.write_section_header("3", "The End-to-End Pipeline")
    pdf.write_paragraph(
        "The complete lifecycle of a conversation is split into an initialization sequence and a continuous "
        "turn-taking loop. The communication flow proceeds as follows:"
    )
    
    pdf.write_subsection_header("Step 1: Session Initiation (Dialing)")
    pdf.write_paragraph(
        "The browser opens a WebSocket handshake with the FastAPI server at ws://localhost:8000/ws/call. "
        "Upon connection, the frontend sends a setup payload containing the system instructions, agent accent choice, "
        "preferred LLM provider, and the custom opening greeting."
    )
    
    pdf.write_subsection_header("Step 2: Greeting Playback")
    pdf.write_paragraph(
        "The backend server receives the setup parameters and calls the edge-tts service to synthesize the "
        "initial greeting. The synthesized MP3 bytes are sent back to the frontend, decoded from Base64, "
        "and immediately played by the browser. Once the greeting ends, the microphone is activated."
    )
    
    pdf.write_subsection_header("Step 3: User Speech & Local Transcription (STT)")
    pdf.write_paragraph(
        "The user responds by speaking into the microphone. The browser's Web Speech API transcribes the voice input "
        "locally (Speech-to-Text). By transcribing on the client side, the application avoids transmitting large raw "
        "audio files to the server, dramatically saving bandwidth and reducing total latency."
    )

    pdf.write_subsection_header("Step 4: AI Reply Generation (LLM)")
    pdf.write_paragraph(
        "Once the browser detects a silence pause, it sends the final text transcription to the server via the WebSocket. "
        "The server appends the text to the history, updates the call state to 'thinking', and queries the configured "
        "LLM provider (e.g. Gemini 3.5 Flash) with the complete conversation logs."
    )
    
    pdf.write_subsection_header("Step 5: Voice Synthesis & Turn Release (TTS)")
    pdf.write_paragraph(
        "The LLM returns the textual response. The server forwards this text to the TTS engine to generate the corresponding "
        "audio stream. The backend sends the text and Base64-encoded audio bytes to the browser. The frontend plays the "
        "audio (temporarily muting the mic to prevent echo loopbacks) and reactivates listening once playback completes."
    )

    pdf.write_section_header("4", "Technical Design Trade-offs")
    
    pdf.write_bullet_point("Client-side STT:", "Using Web Speech API is free, fast, and light on the server. However, it relies on the browser's speech recognition engine (e.g., Google's cloud STT on Chrome) and requires Chrome or Edge.")
    pdf.write_bullet_point("Edge TTS:", "Microsoft's neural voice translator produces high-quality, realistic voices without requiring paid api credits, though it demands active internet access for the backend.")
    pdf.write_bullet_point("Stateful WebSockets:", "Maintains the conversation context in the server's RAM during the call, allowing rapid response times. If the network drops, the frontend must handle call recovery.")

    # Save the PDF to the workspace root
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dhwani_system_architecture.pdf"))
    pdf.output(output_path)
    print(f"Report successfully generated at: {output_path}")

if __name__ == "__main__":
    generate_report()
