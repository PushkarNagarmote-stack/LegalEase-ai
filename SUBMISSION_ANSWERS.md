# LegalEase AI – Official Submission Answers (Strictly Under 1024 Characters)

## Question 1: Describe the changes/updates made in the deployed version
*(Length: 859 characters / 1024 max)*

1. Production Architecture: Decoupled into React 18 + TypeScript on Vercel (SPA rewrites, asset caching) and FastAPI on Render with dynamic env config (VITE_API_URL, ALLOWED_ORIGINS).
2. Defense-in-Depth Security: Added hardened CSP headers (frame-ancestors 'none', base-uri 'self'), X-Frame-Options: DENY, CSRF origin verification, and sliding-window rate limiting (30 chat/min, 10 uploads/min) with 429 Retry-After. defusedxml blocks XXE attacks, DOMPurify sanitizes client Markdown, and Bandit security scanner reports 0 vulnerabilities.
3. Cold-Start Resilience: Automatic session creation with exponential backoff handles Render free-tier cold starts without dropped requests.
4. Test Coverage & Quality: 211 automated tests (152 Pytest backend + 59 Vitest frontend) with 100% pass rate, zero ESLint/Ruff warnings, and full WCAG accessibility compliance.

---

## Question 2: Mention the Gen AI services utilized in the submission, and where did you utilize it?
*(Length: 882 characters / 1024 max)*

1. Gen AI Service: Google Gemini 2.5 Flash utilized via the official google-genai Python SDK and Gemini REST API, selected for sub-second inference, large context window, and high precision in legal reasoning.
2. Grounded Contract Q&A: In /api/session/{id}/chat, Gemini analyzes user queries against retrieved contract clauses under strict legal-assistant system prompts. Every factual claim is anchored to verbatim clause citations and section titles to eliminate hallucinations.
3. Attorney Prep Questionnaire: In /api/session/{id}/prepare-for-lawyer, Gemini synthesizes high-risk clauses (indemnities, default penalties, deposit forfeitures) into a prioritized, jurisdiction-aware questionnaire for paid legal consultations.
4. Resilient Fallback: Supports environment or user API keys, with automatic fallback to an offline keyword-density retrieval engine if quota is exceeded.
