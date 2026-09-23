# LegalEase AI – Official Submission Answers (Under 1024 Characters)

## Question 1: Describe the changes/updates made in the deployed version
*(Length: 840 characters)*

1. Cloud Architecture: Decoupled into a production system with React 18 + TypeScript on Vercel (SPA rewrites, CDN caching) and FastAPI on Render with dynamic env variables (VITE_API_URL, ALLOWED_ORIGINS).
2. Defense-in-Depth Security: Added hardened CSP headers (frame-ancestors none, base-uri self), X-Frame-Options: DENY, CSRF origin verification, and sliding-window rate limiting (30 chat/min, 10 uploads/min) returning 429 Retry-After. Defusedxml parser protects against XXE attacks with 15MB file limits. Clean Bandit audit with 0 issues.
3. Cold-Start Resilience: Implemented automatic session creation with 3-attempt exponential backoff to seamlessly handle Render free-tier wakeups without dropped requests.
4. Quality & 211 Tests: Zero ESLint or Ruff warnings, full JSDoc and PEP-257 docstrings, and 211 automated tests (152 Pytest + 59 Vitest) covering security, WCAG accessibility, and legal parsing.

---

## Question 2: Mention the Gen AI services utilized in the submission, and where did you utilize it?
*(Length: 845 characters)*

1. Gen AI Service: Google Gemini 2.5 Flash utilized via the official google-genai Python SDK and Gemini REST API, selected for sub-second inference speed, high context efficiency, and precision in legal reasoning.
2. Grounded Contract Q&A: In /api/session/{id}/chat, Gemini receives user questions alongside retrieved contract clauses under strict legal-assistant prompts. It generates plain-language answers where every claim is anchored to verbatim clause citations and section titles to eliminate hallucinations.
3. Attorney Prep Questionnaire: In /api/session/{id}/prepare-for-lawyer, Gemini analyzes high-risk clauses (indemnities, default penalties, deposit forfeitures) to draft prioritized, jurisdiction-aware questions for paid legal consultations.
4. Resilient Fallback: Supports user or environment keys, with automatic fallback to an offline keyword-density retrieval engine if quota is exceeded.
