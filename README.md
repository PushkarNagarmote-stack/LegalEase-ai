# LegalEase AI

LegalEase AI is a conversational GenAI legal-document assistant built with React 18, TypeScript, and FastAPI. It provides document-grounded answers, clickable clause citations, risk/obligation/right flags, suggested follow-ups, and an attorney-prep questionnaire.

## Architecture

- **Landing Page (`/`)**: Dark liquid-glass product introduction with features, grounding overview, how-it-works workflow, and client-side instant navigation to the chatbot.
- **AI Chatbot (`/chat`)**: Dedicated macOS-style window for uploading agreements (PDF or TXT), viewing clause flag tallies, clicking citation cards to read exact source excerpts, and preparing attorney question lists.
- **In-Memory Grounded Backend**: FastAPI server with automatic document chunking, keyword-density retrieval, clause type classification, and question generation.

## How to Run Locally

Open two separate PowerShell terminal windows:

### Terminal 1 — Backend (FastAPI on Port 8001):
```powershell
cd "C:\Users\pushkar\Documents\Codex\2026-09-23\hey-good-to-tell-you-that"
python -m uvicorn backend.main:app --reload --port 8001
```
*(Port 8001 is used to prevent Windows `WinError 10013` restricted socket conflicts).*

### Terminal 2 — Frontend (Vite):
```powershell
cd "C:\Users\pushkar\Documents\Codex\2026-09-23\hey-good-to-tell-you-that"
npm run dev
```

Open the address Vite prints in your browser (typically `http://localhost:5173`).

- Visit `http://localhost:5173/` for the **Landing Page**.
- Click any **"Try LegalEase"** or **"Launch Chatbot"** button (or navigate to `http://localhost:5173/chat`) for the **Dedicated Chatbot**.
- Use the **"Load Sample Lease"** button in the sidebar or upload your own `.pdf` or `.txt` document to test.
