import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { marked } from 'marked';
import './styles.css';

// Configure marked for safe inline rendering
marked.setOptions({ breaks: true, gfm: true });

/**
 * Renders sanitized markdown content into an HTML body container.
 * @param props Component properties containing the raw markdown string.
 */
export function MarkdownMessage({ content }: { content: string }) {
  const html = marked.parse(content || '') as string;
  return (
    <div
      className="md-body"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/**
 * Citation reference linking a factual claim to an exact clause excerpt.
 */
export type Cite = {
  marker?: string;
  source_text: string;
  clause_ref: string;
};

/**
 * Conversational message structure supporting grounded citations,
 * lawyer checklist items, and follow-up prompts.
 */
export type Msg = {
  id?: string;
  role: 'assistant' | 'user';
  content: string;
  citations?: Cite[];
  followups?: string[];
  lawyer?: string[];
};

/**
 * Authenticated Google user profile metadata.
 */
export type GoogleUser = {
  sub: string;
  name: string;
  email: string;
  picture: string;
};

const api = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001';

const SAMPLE_LEASE = `RESIDENTIAL LEASE AGREEMENT
Section 1. Parties and Premises. Landlord leases to Tenant the premises at 404 Beacon Street, Apt 3B.
Section 2. Term. The lease term shall begin on October 1, 2026 and expire on September 30, 2027.
Section 3. Rent. Tenant shall pay monthly rent of $2,400 due on the first day of each month. A late fee of $120 applies if unpaid after 5 days.
Section 4. Security Deposit. Tenant shall pay a security deposit of $2,400. Landlord may use funds for unpaid rent or damage exceeding ordinary wear and tear. Deposit return is required within 30 days of surrender.
Section 6. Maintenance & Repairs. Tenant must promptly notify Landlord of any conditions requiring repair. Landlord is responsible for structural and plumbing repairs unless damage was caused by Tenant negligence.
Section 8. Termination & Notice to Vacate. Either party may terminate this agreement by giving not less than sixty (60) days' written notice. Failure to provide notice results in forfeiture of deposit.
Section 12. Alterations. Tenant shall make no alterations or painting without Landlord's prior written consent.`;

/**
 * LegalEase AI geometric brand logo SVG icon.
 */
export function Logo() {
  return (
    <svg viewBox="0 0 256 256" aria-hidden="true">
      <path d="M0 128c70 0 128 57 128 128H64c0-35-29-64-64-64v-64Zm256 64c-35 0-64 29-64 64h-64c0-71 57-128 128-128v64ZM128 0c0 71-57 128-128 128V64c35 0 64-29 64-64h64Zm64 0c0 35 29 64 64 64v64c-71 0-128-57-128-128h64Z" />
    </svg>
  );
}

/**
 * Top navigation bar with brand link, documentation links, and user authentication state.
 * @param props Navigation callbacks and authenticated user state.
 */
export function Nav({ onNavigate, user, onSignOut }: { onNavigate: (path: string) => void; user: GoogleUser | null; onSignOut: () => void }) {
  return (
    <nav className="glass">
      <a
        className="brand"
        href="/"
        onClick={(e) => {
          e.preventDefault();
          onNavigate('/');
        }}
      >
        <Logo />
        <span>LegalEase</span>
      </a>
      <div className="navlinks">
        <a href="#product">Product</a>
        <a href="#how">How it works</a>
        <a href="#trust">Trust &amp; safety</a>
        <a href="#docs">Docs</a>
      </div>
      {user ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <img src={user.picture} alt={user.name} style={{ width: '32px', height: '32px', borderRadius: '50%', border: '2px solid rgba(201,168,76,0.6)', objectFit: 'cover' }} referrerPolicy='no-referrer' />
          <button className='primary' onClick={() => onNavigate(user ? '/chat' : '/login')} type='button'>
            Open Chat &rarr;
          </button>
          <button onClick={onSignOut} type='button' style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: 'rgba(255,255,255,0.5)', padding: '8px 14px', cursor: 'pointer', fontSize: '0.82rem', fontFamily: 'inherit' }}>
            Sign out
          </button>
        </div>
      ) : (
        <button
          className='primary'
          onClick={() => onNavigate('/login')}
          type='button'
        >
          Sign In &rarr;
        </button>
      )}
    </nav>
  );
}

/**
 * Marketing landing page highlighting document grounding, trust & safety, and onboarding.
 * @param props Navigation callbacks and user session.
 */
export function Landing({ onNavigate, user, onSignOut }: { onNavigate: (path: string) => void; user: GoogleUser | null; onSignOut: () => void }) {
  return (
    <>
      <div className="backdrop" />
      <div className="guide l" />
      <div className="guide r" />
      <Nav onNavigate={onNavigate} user={user} onSignOut={onSignOut} />

      <main id="top">
        <header className="hero reveal">
          <h1>
            Your legal documents.
            <span className="shiny">Finally understood.</span>
          </h1>
          <p>
            LegalEase reads your contracts and agreements with you &mdash; plain-language answers,
            every claim cited back to the actual clause, no guessing.
          </p>
          <div className="actions">
            <button
              className="primary"
              onClick={() => onNavigate(user ? '/chat' : '/login')}
              type="button"
            >
              Try LegalEase &rarr;
            </button>
            <a className="ghost" href="#how">
              See how it works
            </a>
          </div>
          <small>Not a substitute for professional legal advice.</small>
        </header>

        <section id="product" className="landing-product reveal">
          <div className="preview glass">
            <span className="eyebrow">LEGAL DOCUMENT ASSISTANT</span>
            <h2>Ask the questions the fine print leaves behind.</h2>
            <p>
              Upload contracts, leases, or agreements. Explore every clause through conversational AI,
              and inspect the exact cited source text behind every statement.
            </p>
            <div className="preview-row">
              <span>&#10003; Grounded citations</span>
              <span>&#10003; Risk &amp; obligation flags</span>
              <span>&#10003; Lawyer prep questions</span>
            </div>
            <div style={{ marginTop: '1.5rem' }}>
              <button
                className="primary"
                onClick={() => onNavigate(user ? '/chat' : '/login')}
                type="button"
              >
                Launch Chatbot &rarr;
              </button>
            </div>
          </div>
        </section>

        <section id="trust" className="ground reveal">
          <div>
            <label>GROUNDING &bull; RAG-POWERED</label>
            <h2>Every answer, traced to the source.</h2>
            <p>
              LegalEase retrieves relevant clauses in real-time, maps each claim to its exact section,
              and explicitly notifies you when the document does not contain enough context to answer.
            </p>
            <div className="pills">
              <span>Cited clauses</span>
              <span>Risk severity</span>
              <span>Suggested follow-ups</span>
              <span>Prepare for a lawyer</span>
            </div>
          </div>
          <div className="stats glass">
            <h3>Clause Classification Engine</h3>
            <p>
              <span>
                <i className="risk" /> Risk
              </span>
              <b>Surfaces penalties, damages &amp; liabilities</b>
            </p>
            <p>
              <span>
                <i className="obligation" /> Obligation
              </span>
              <b>Clarifies mandatory deadlines &amp; terms</b>
            </p>
            <p>
              <span>
                <i className="right" /> Right
              </span>
              <b>Highlights legal protections &amp; remedies</b>
            </p>
          </div>
        </section>

        <section id="how" className="how reveal">
          <label>HOW IT WORKS</label>
          <h2>Clarity in three careful steps.</h2>
          <div>
            {[
              ['01', 'Upload', 'Attach a lease, NDA, employment agreement, or any contract (PDF or text).'],
              ['02', 'Ask', 'Ask naturally about hidden fees, notice periods, liabilities, or deadlines.'],
              ['03', 'Understand', 'Read cited answers and receive tailored questions to bring to your attorney.'],
            ].map(([num, title, desc]) => (
              <article className="glass" key={num}>
                <b>{num}</b>
                <h3>{title}</h3>
                <p>{desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="quotes reveal">
          {[
            {
              quote: 'I finally understood which termination clauses required negotiation before I signed my lease.',
              author: 'Renter scenario review',
            },
            {
              quote: 'The direct source citations gave me confidence that the AI wasn’t hallucinating terms.',
              author: 'Freelance contract review',
            },
            {
              quote: 'The "Prepare for my lawyer" list organized my questions and saved me over 30 minutes in legal fees.',
              author: 'Small business founder review',
            },
          ].map((item) => (
            <article className="glass" key={item.author}>
              <q>&ldquo;{item.quote}&rdquo;</q>
              <small>{item.author}</small>
            </article>
          ))}
        </section>

        <section className="cta glass reveal">
          <h2>
            Stop guessing
            <br />
            what you signed.
          </h2>
          <p>
            Bring your document. Ask in plain language. Keep every answer tied to the source.
          </p>
          <div className="actions">
            <button
              className="primary"
              onClick={() => onNavigate(user ? '/chat' : '/login')}
              type="button"
            >
              Start Free Session &rarr;
            </button>
            <a className="ghost" href="#top">
              Back to Top &uarr;
            </a>
          </div>
        </section>
      </main>

      <footer id="docs">
        LegalEase AI &bull; Private, in-memory prototype session &bull; Not legal advice
      </footer>
    </>
  );
}

// ─── Google Auth ──────────────────────────────────────────────────────────────

const GOOGLE_CLIENT_ID = '638136010192-oh6chshnj243ql45hun31864l6mvk39k.apps.googleusercontent.com';

/**
 * Retrieves the stored Google user session from browser localStorage.
 * @returns Decoded GoogleUser object or null if not authenticated.
 */
export function getStoredUser(): GoogleUser | null {
  try {
    const raw = localStorage.getItem('legalease_user');
    return raw ? (JSON.parse(raw) as GoogleUser) : null;
  } catch {
    return null;
  }
}

/**
 * Decodes a Google Sign-In JWT token to extract the user profile.
 * @param token The encoded JWT credential string.
 * @returns Decoded GoogleUser object or null if parsing fails.
 */
export function parseJwt(token: string): GoogleUser | null {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(json) as GoogleUser;
  } catch {
    return null;
  }
}

// ─── Login Page ───────────────────────────────────────────────────────────────

/**
 * Google authentication sign-in page with credential decoding and terms disclaimer.
 * @param props Authentication completion callback.
 */
export function LoginPage({ onSuccess }: { onSuccess: (user: GoogleUser) => void }) {
  const btnRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const tryRender = () => {
      if (!(window as any).google?.accounts?.id || !btnRef.current) return;
      (window as any).google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (resp: { credential: string }) => {
          const user = parseJwt(resp.credential);
          if (user) {
            localStorage.setItem('legalease_user', JSON.stringify(user));
            onSuccess(user);
          }
        },
      });
      (window as any).google.accounts.id.renderButton(btnRef.current, {
        theme: 'filled_black',
        size: 'large',
        shape: 'pill',
        text: 'signin_with',
        width: 280,
      });
    };

    // GSI script may still be loading; retry until ready
    const id = setInterval(() => {
      if ((window as any).google?.accounts?.id) {
        tryRender();
        clearInterval(id);
      }
    }, 100);
    return () => clearInterval(id);
  }, [onSuccess]);

  return (
    <div className="login-page">
      <div className="login-bg-glow" />
      <div className="login-card glass">
        {/* Logo */}
        <div className="login-logo">
          <svg width="44" height="44" viewBox="0 0 256 256" fill="none">
            <circle cx="128" cy="128" r="128" fill="url(#lg)" />
            <path d="M80 176 L128 80 L176 176" stroke="#fff" strokeWidth="18" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            <path d="M95 152 h66" stroke="#fff" strokeWidth="14" strokeLinecap="round" />
            <defs>
              <linearGradient id="lg" x1="0" y1="0" x2="256" y2="256">
                <stop stopColor="#c9a84c" />
                <stop offset="1" stopColor="#7c5f20" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        <h1 className="login-title">LegalEase AI</h1>
        <p className="login-sub">Understand what you're signing — instantly.</p>

        <div className="login-features">
          <span>📄 Contract analysis</span>
          <span>⚖️ Risk flags</span>
          <span>💬 Plain-language answers</span>
        </div>

        <div className="login-divider" />

        {/* Google Sign-In button rendered by GSI SDK */}
        <div ref={btnRef} className="google-btn-wrap" id="google-signin-btn" />

        <p className="login-legal">
          By signing in you agree that LegalEase AI provides legal <em>information</em>, not formal legal advice.
        </p>
      </div>
    </div>
  );
}

// ─── User Chip (shown in chat header) ─────────────────────────────────────────

/**
 * Interactive user badge displayed in headers with avatar and sign-out controls.
 * @param props Authenticated user metadata and sign-out callback.
 */
export function UserChip({ user, onSignOut }: { user: GoogleUser; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="user-chip" style={{ position: 'relative' }}>
      <button
        className="user-avatar-btn"
        onClick={() => setOpen((v) => !v)}
        title={user.name}
        type="button"
      >
        <img src={user.picture} alt={user.name} className="user-avatar" referrerPolicy="no-referrer" />
        <span className="user-name">{user.name.split(' ')[0]}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="user-dropdown">
          <p className="user-dropdown-name">{user.name}</p>
          <p className="user-dropdown-email">{user.email}</p>
          <hr />
          <button
            type="button"
            onClick={() => { setOpen(false); onSignOut(); }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
// ─── Chat History Storage ─────────────────────────────────────────────────────

/**
 * Serialized conversation state for persistent session storage.
 */
export type StoredChat = {
  id: string;
  title: string;
  messages: Msg[];
  doc: string;
  flags: { risk: number; obligation: number; right: number; info: number };
  createdAt: number;
  updatedAt: number;
};

/**
 * Constructs localStorage key for user conversation history.
 */
export function historyKey(sub: string) { return `legalease_history_${sub}`; }

/**
 * Loads conversation history list for a user from browser localStorage.
 */
export function loadHistory(sub: string): StoredChat[] {
  try { return JSON.parse(localStorage.getItem(historyKey(sub)) || '[]'); }
  catch { return []; }
}

/**
 * Persists updated conversation history list for a user to browser localStorage.
 */
export function saveHistory(sub: string, chats: StoredChat[]) {
  localStorage.setItem(historyKey(sub), JSON.stringify(chats.slice(0, 80)));
}

/**
 * Generates a unique pseudo-random identifier for chat sessions and messages.
 */
export function makeId() { return Date.now().toString(36) + Math.random().toString(36).slice(2); }

export const WELCOME: Msg = {
  id: 'welcome-message-0',
  role: 'assistant',
  content: 'Welcome to LegalEase AI! I can help you:\n\n• Analyze contracts, leases, NDAs — with grounded citations and clause flags\n• Answer general legal questions and explain legal terms\n• Suggest negotiation strategies and attorney prep questions\n\nUpload a document (PDF, DOCX, TXT, MD) to get document-specific answers, or just ask me anything!',
  followups: ['What is an indemnification clause?', 'What is force majeure?', 'How do I negotiate my lease?'],
};

// ─── History Sidebar ──────────────────────────────────────────────────────────

/**
 * Collapsible session history sidebar managing multiple chat threads and date groupings.
 * @param props Conversation state, active selection, and toggle callbacks.
 */
export function HistorySidebar({
  chats,
  activeChatId,
  onSelect,
  onNew,
  onDelete,
  collapsed,
  onToggle,
  user,
  onSignOut,
}: {
  chats: StoredChat[];
  activeChatId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  user: GoogleUser;
  onSignOut: () => void;
}) {
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const grouped = React.useMemo(() => {
    const now = Date.now();
    const DAY = 86400000;
    const groups: { label: string; items: StoredChat[] }[] = [];
    const todayItems = chats.filter(c => now - c.updatedAt < DAY);
    const yesterdayItems = chats.filter(c => now - c.updatedAt >= DAY && now - c.updatedAt < 2 * DAY);
    const olderItems = chats.filter(c => now - c.updatedAt >= 2 * DAY);
    if (todayItems.length) groups.push({ label: 'Today', items: todayItems });
    if (yesterdayItems.length) groups.push({ label: 'Yesterday', items: yesterdayItems });
    if (olderItems.length) groups.push({ label: 'Older', items: olderItems });
    return groups;
  }, [chats]);

  return (
    <div className={`history-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="history-top">
        <button className="history-toggle" onClick={onToggle} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        {!collapsed && (
          <button className="new-chat-btn" onClick={onNew} type="button">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New Chat
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="history-list">
          {chats.length === 0 ? (
            <p className="history-empty">No chats yet. Start a conversation!</p>
          ) : (
            grouped.map(({ label, items }) => (
              <div key={label} className="history-group">
                <span className="history-group-label">{label}</span>
                {items.map(chat => (
                  <div
                    key={chat.id}
                    className={`history-item ${chat.id === activeChatId ? 'active' : ''}`}
                    onClick={() => onSelect(chat.id)}
                    title={chat.title}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                    <span className="history-title">{chat.title}</span>
                    <button
                      className="history-delete"
                      onClick={e => { e.stopPropagation(); onDelete(chat.id); }}
                      title="Delete chat"
                      type="button"
                    >
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      )}

      {collapsed && (
        <div className="history-collapsed-icons">
          <button className="new-chat-icon" onClick={onNew} title="New Chat" type="button">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>
      )}

      {/* Bottom Profile with Pulse & Sign Out */}
      <div className={`history-profile-section ${collapsed ? 'collapsed' : ''}`} ref={profileRef}>
        <button
          className={`history-profile-btn ${collapsed ? 'collapsed' : ''}`}
          onClick={() => setProfileOpen(v => !v)}
          title={`${user.name} (${user.email})`}
          type="button"
          aria-expanded={profileOpen}
        >
          <div className="avatar-pulse-container">
            <img src={user.picture} alt={user.name} className="sidebar-avatar" referrerPolicy="no-referrer" />
            <span className="profile-pulse-ring" />
            <span className="profile-pulse-dot" />
          </div>
          {!collapsed && (
            <div className="history-profile-meta">
              <span className="history-profile-name">{user.name}</span>
              <span className="history-profile-email">{user.email}</span>
            </div>
          )}
          {!collapsed && (
            <svg
              className={`history-profile-arrow ${profileOpen ? 'open' : ''}`}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="18 15 12 9 6 15" />
            </svg>
          )}
        </button>

        {profileOpen && (
          <div className={`history-profile-popover ${collapsed ? 'popover-rail' : 'popover-expanded'}`}>
            <div className="popover-user-info">
              <div className="avatar-pulse-container small">
                <img src={user.picture} alt={user.name} className="sidebar-avatar small" referrerPolicy="no-referrer" />
                <span className="profile-pulse-dot" />
              </div>
              <div className="popover-user-text">
                <p className="popover-name">{user.name}</p>
                <p className="popover-email">{user.email}</p>
              </div>
            </div>
            <div className="popover-divider" />
            <button
              className="popover-signout-btn"
              onClick={() => { setProfileOpen(false); onSignOut(); }}
              type="button"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign out
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Chat Page ────────────────────────────────────────────────────────────────

/**
 * Full-featured chat interface: document upload, grounded Q&A, citation viewer,
 * risk/obligation flags, lawyer-prep questionnaire, and session history sidebar.
 * @param props Navigation and authenticated user callbacks.
 */
export function Chat({ onNavigate, user, onSignOut }: { onNavigate: (path: string) => void; user: GoogleUser; onSignOut: () => void }) {
  // History state
  const [history, setHistory] = useState<StoredChat[]>(() => loadHistory(user.sub));
  const [activeChatId, setActiveChatId] = useState<string>(() => {
    const h = loadHistory(user.sub);
    return h.length > 0 ? h[0].id : makeId();
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

  // Chat state
  const [session, setSession] = useState('demo');
  const [messages, setMessages] = useState<Msg[]>([WELCOME]);
  const [text, setText] = useState('');
  const [doc, setDoc] = useState('No document attached');
  const [typing, setTyping] = useState(false);
  const [open, setOpen] = useState<Cite | null>(null);
  const [flags, setFlags] = useState({ risk: 0, obligation: 0, right: 0, info: 0 });
  const [apiKey, setApiKey] = useState(localStorage.getItem('legalease_api_key') || '');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const isInitialMount = useRef(true);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Create backend session ─────────────────────────────────────────────────
  useEffect(() => {
    fetch(`${api}/api/session`, { method: 'POST' })
      .then(r => r.json())
      .then(x => { if (x.session_id) setSession(x.session_id); })
      .catch(() => {});
  }, [activeChatId]); // new backend session for each chat

  // ── Load the active chat from history ──────────────────────────────────────
  useEffect(() => {
    const found = history.find(c => c.id === activeChatId);
    if (found) {
      setMessages(found.messages);
      setDoc(found.doc);
      setFlags(found.flags);
    } else {
      setMessages([WELCOME]);
      setDoc('No document attached');
      setFlags({ risk: 0, obligation: 0, right: 0, info: 0 });
    }
    setOpen(null);
    isInitialMount.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChatId]);

  // ── Auto-save on message change (debounced 600ms) ──────────────────────────
  useEffect(() => {
    if (isInitialMount.current) { isInitialMount.current = false; return; }
    // Only save if there is at least one user message
    const hasUserMsg = messages.some(m => m.role === 'user');
    if (!hasUserMsg) return;

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      const title = messages.find(m => m.role === 'user')?.content.slice(0, 48) || 'New Chat';
      setHistory(prevHistory => {
        const existing = prevHistory.find(c => c.id === activeChatId);
        const updated: StoredChat = {
          id: activeChatId,
          title,
          messages,
          doc,
          flags,
          createdAt: existing?.createdAt ?? Date.now(),
          updatedAt: Date.now(),
        };
        const next = [updated, ...prevHistory.filter(c => c.id !== activeChatId)];
        saveHistory(user.sub, next);
        return next;
      });
    }, 600);
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
  }, [messages, doc, flags, activeChatId, user.sub]);

  // ── Scroll thread on new messages ─────────────────────────────────────────
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages, typing]);

  // ── New chat ───────────────────────────────────────────────────────────────
  function startNewChat() {
    setActiveChatId(makeId());
  }

  // ── Select chat from history ───────────────────────────────────────────────
  function selectChat(id: string) {
    setActiveChatId(id);
  }

  // ── Delete chat from history ───────────────────────────────────────────────
  function deleteChat(id: string) {
    const next = history.filter(c => c.id !== id);
    setHistory(next);
    saveHistory(user.sub, next);
    if (id === activeChatId) {
      if (next.length > 0) setActiveChatId(next[0].id);
      else setActiveChatId(makeId());
    }
  }

  /** Append a message to the thread, assigning a stable unique id if absent. */
  const push = (m: Msg) => setMessages(prev => [...prev, { id: makeId(), ...m }]);

  async function upload(f: File) {
    if (f.size > 15 * 1024 * 1024) {
      return push({ role: 'assistant', content: 'That file is larger than the 15 MB limit. Please upload a smaller file.' });
    }
    setDoc(f.name);
    setTyping(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await fetch(`${api}/api/session/${session}/document`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      push({
        role: 'assistant',
        content: data.message,
        citations: data.citations,
        followups: data.suggested_followups,
      });
      if (data.flags) setFlags(data.flags);
    } catch (e) {
      push({ role: 'assistant', content: `I could not read that document: ${(e as Error).message}. You can try a text-based PDF or load the sample lease.` });
    } finally { setTyping(false); }
  }

  function loadSampleLease() {
    const sampleBlob = new Blob([SAMPLE_LEASE], { type: 'text/plain' });
    const sampleFile = new File([sampleBlob], 'sample-residential-lease.txt', { type: 'text/plain' });
    upload(sampleFile);
  }

  async function send(value = text) {
    const query = value.trim();
    if (!query) return;
    push({ role: 'user', content: query });
    setText('');
    setTyping(true);
    try {
      const res = await fetch(`${api}/api/session/${session}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query, api_key: apiKey || undefined }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      push({ role: 'assistant', content: data.answer, citations: data.citations, followups: data.suggested_followups });
    } catch (e) {
      push({ role: 'assistant', content: `Could not reach the analysis service: ${(e as Error).message}. Ensure the FastAPI server is running on port 8001.` });
    } finally { setTyping(false); }
  }

  async function lawyer() {
    setTyping(true);
    try {
      const res = await fetch(`${api}/api/session/${session}/prepare-for-lawyer`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not generate lawyer questions');
      push({ role: 'assistant', content: 'Questions to Bring to Your Lawyer:', lawyer: data.questions });
    } catch {
      push({ role: 'assistant', content: 'Please attach or load a document first so I can extract relevant clauses and prepare focused lawyer questions.' });
    } finally { setTyping(false); }
  }

  return (
    <>
      <div className="backdrop" />
      <nav className="glass">
        <a className="brand" href="/" onClick={e => { e.preventDefault(); onNavigate('/'); }}>
          <Logo />
          <span>LegalEase</span>
        </a>
        <button className="primary" onClick={() => onNavigate('/')} type="button">
          &larr; Home
        </button>
      </nav>

      <div className="chat-shell">
        <HistorySidebar
          chats={history}
          activeChatId={activeChatId}
          onSelect={selectChat}
          onNew={startNewChat}
          onDelete={deleteChat}
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(v => !v)}
          user={user}
          onSignOut={onSignOut}
        />

        <main className="chat-page">
          <header className="chat-header">
            <div>
              <span className="eyebrow">PRIVATE SESSION</span>
              <h1>Chat with your document.</h1>
              <p>Grounded answers, source citations, and a clear boundary around legal advice.</p>
            </div>
                      </header>

          <section className="product">
            <div className="window glass">
              <div className="topbar">
                <i /><i /><i />
                <em>LegalEase AI &mdash; {doc}</em>
              </div>

              <div className="workspace">
                <aside>
                  <button className="new" onClick={() => fileInputRef.current?.click()} type="button">
                    &#128196;&nbsp; Upload Document
                  </button>

                  <button
                    className="add"
                    style={{ marginTop: '8px', padding: '6px 10px', background: 'rgba(61,129,227,0.15)', borderRadius: '6px', color: '#a4f4fd', border: '1px solid rgba(61,129,227,0.3)' }}
                    onClick={loadSampleLease}
                    type="button"
                  >
                    &rarr; Load Sample Lease
                  </button>

                  <label>ACTIVE DOCUMENT</label>
                  <p className="doc" title={doc}>{doc}</p>

                  <label>CLAUSE FLAGS</label>
                  {[['risk','Risk',flags.risk],['obligation','Obligation',flags.obligation],['right','Right',flags.right]].map(([c,n,v]) => (
                    <p className="flag" key={String(c)}>
                      <i className={String(c)} />
                      {n}<b>{v}</b>
                    </p>
                  ))}

                  <label style={{ marginTop: '24px' }}>AI ENGINE</label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
                    <input
                      type="password"
                      placeholder="Gemini API key (optional)"
                      value={apiKey}
                      onChange={e => { setApiKey(e.target.value); localStorage.setItem('legalease_api_key', e.target.value); }}
                      style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '6px', color: '#ffffff', padding: '7px 10px', fontSize: '11px', width: '100%', boxSizing: 'border-box', outline: 'none' }}
                      title="Enter your Gemini API key to enable full AI responses via the Gemini model"
                    />
                    <small style={{ color: 'rgba(255,255,255,0.35)', fontSize: '10px', lineHeight: '1.4' }}>
                      {apiKey ? '🔑 Gemini AI enabled' : 'Smart clause QA active'}
                    </small>
                  </div>
                </aside>

                <section className="chat">
                  <div className="thread" ref={threadRef}>
                    {messages.map((m) => (
                      <article className={'message ' + m.role} key={m.id ?? m.content.slice(0, 40) + m.role}>
                        <div className="bubble">
                          {m.lawyer ? (
                            <>
                              <h3>{m.content}</h3>
                              <ol>{m.lawyer.map((q) => <li key={q} style={{ marginTop: '6px' }}>{q}</li>)}</ol>
                              <button
                                type="button"
                                style={{
                                  marginTop: '12px',
                                  padding: '6px 12px',
                                  background: 'rgba(201,168,76,0.15)',
                                  border: '1px solid rgba(201,168,76,0.4)',
                                  borderRadius: '6px',
                                  color: '#f0d38d',
                                  cursor: 'pointer',
                                  fontSize: '0.8rem',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                }}
                                onClick={() => {
                                  const textToCopy = `Questions to Bring to Your Lawyer:\n` + (m.lawyer || []).map((q, i) => `${i + 1}. ${q}`).join('\n');
                                  if (navigator.clipboard?.writeText) {
                                    navigator.clipboard.writeText(textToCopy);
                                  }
                                }}
                                title="Copy all questions to clipboard"
                              >
                                📋 Copy Questions
                              </button>
                            </>
                          ) : m.role === 'assistant' ? (
                            <div className="md-wrap">
                              <MarkdownMessage content={m.content} />
                              {m.citations && m.citations.length > 0 && (
                                <div className="sources-tray">
                                  <div className="sources-tray-label">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                      <polyline points="14 2 14 8 20 8"></polyline>
                                    </svg>
                                    <span>Referenced Clauses:</span>
                                  </div>
                                  <div className="sources-chips">
                                    {m.citations.map((c) => {
                                      const isSelected = open?.clause_ref === c.clause_ref;
                                      return (
                                        <button
                                          className={`source-chip ${isSelected ? 'active' : ''}`}
                                          key={`${m.id ?? 'msg'}-${c.clause_ref}`}
                                          onClick={() => setOpen(isSelected ? null : c)}
                                          title={`View source: ${c.clause_ref}`}
                                          aria-label={`${isSelected ? 'Close' : 'Open'} citation: ${c.clause_ref}`}
                                          aria-expanded={isSelected}
                                          type="button"
                                        >
                                          <span>{c.clause_ref}</span>
                                        </button>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            <p>{m.content}</p>
                          )}

                          {open && m.citations?.some(c => c.clause_ref === open.clause_ref) && (
                            <div className="source-viewer">
                              <div className="source-viewer-header">
                                <b>{open.clause_ref}</b>
                                <button onClick={() => setOpen(null)} className="close-source" type="button" title="Close snippet">&times;</button>
                              </div>
                              <q>&ldquo;{open.source_text}&rdquo;</q>
                            </div>
                          )}
                        </div>

                        {m.followups && m.followups.length > 0 && (
                          <div className="followups">
                            {m.followups.map(q => (
                              <button onClick={() => send(q)} key={q} type="button">{q}</button>
                            ))}
                          </div>
                        )}
                      </article>
                    ))}

                    {typing && (
                      <div className="typing"><i /><i /><i /> LegalEase is writing&hellip;</div>
                    )}
                  </div>

                  <form className="composer" onSubmit={e => { e.preventDefault(); send(); }}>
                    <label htmlFor="file-upload" className="visually-hidden">Upload legal document (PDF, DOCX, TXT, MD)</label>
                    <input
                      id="file-upload"
                      ref={fileInputRef}
                      hidden
                      type="file"
                      accept=".pdf,.docx,.txt,.md"
                      aria-label="Upload legal document (PDF, DOCX, TXT, MD)"
                      onChange={e => e.target.files?.[0] && upload(e.target.files[0])}
                    />
                    <button type="button" onClick={() => fileInputRef.current?.click()} aria-label="Attach legal document" title="Attach PDF, DOCX, TXT or MD document" style={{ fontSize: '18px', padding: '0 8px' }}>
                      &#128206;
                    </button>
                    <label htmlFor="chat-input" className="visually-hidden">Ask about your legal document</label>
                    <input
                      id="chat-input"
                      value={text}
                      onChange={e => setText(e.target.value)}
                      placeholder="Ask about your document (e.g. Can the landlord enter without notice?)..."
                      aria-label="Ask about your legal document"
                    />
                    <button type="button" className="lawyer" onClick={lawyer} title="Generate focused questions for an attorney" aria-label="Prepare questions for a lawyer">Prepare for a lawyer</button>
                    <button className="send" type="submit" aria-label="Send">&uarr;</button>
                  </form>

                  <small className="disclaimer">
                    LegalEase AI provides legal information, not legal advice. Consult a qualified professional for your specific situation.
                  </small>
                </section>
              </div>
            </div>
          </section>
        </main>
      </div>
    </>
  );
}

/**
 * Root application component managing routing, authentication state, and navigation.
 */
export function App() {
  const [user, setUser] = useState<GoogleUser | null>(getStoredUser);
  const [route, setRoute] = useState(() => {
    const path = typeof window !== 'undefined' ? window.location.pathname : '/';
    return path.startsWith('/chat') ? '/chat' : path.startsWith('/login') ? '/login' : '/';
  });

  const navigate = useCallback((to: string) => {
    window.history.pushState({}, '', to);
    setRoute(to);
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' as ScrollBehavior });
  }, []);

  const handleLogin = useCallback((u: GoogleUser) => {
    setUser(u);
    navigate('/chat');
  }, [navigate]);

  const handleSignOut = useCallback(() => {
    localStorage.removeItem('legalease_user');
    setUser(null);
    (window as any).google?.accounts?.id?.disableAutoSelect?.();
    navigate('/');
  }, [navigate]);

  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      setRoute(path.startsWith('/chat') ? '/chat' : path.startsWith('/login') ? '/login' : '/');
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' as ScrollBehavior });
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // /chat is protected — redirect to login if not authenticated
  if (route === '/chat' && !user) return <LoginPage onSuccess={handleLogin} />;
  if (route === '/chat') return <Chat onNavigate={navigate} user={user!} onSignOut={handleSignOut} />;
  if (route === '/login') return <LoginPage onSuccess={handleLogin} />;
  return <Landing onNavigate={navigate} user={user} onSignOut={handleSignOut} />;
}

const rootElement = document.getElementById('root');
if (rootElement) {
  createRoot(rootElement).render(<App />);
}








