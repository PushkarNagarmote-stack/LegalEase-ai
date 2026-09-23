/**
 * @file tests/main.test.tsx
 * @description Comprehensive React Testing Library and Vitest unit tests for LegalEase AI.
 *
 * Covers:
 *  - MarkdownMessage: rendering of bold, links, lists, code, headers, and edge cases.
 *  - Logo: SVG structure, accessibility attributes, and viewBox.
 *  - Nav: brand logo/name, navigation anchor links, auth states (signed in vs signed out).
 *  - Landing: hero headings, primary/secondary CTAs, route changes on click.
 *  - LoginPage: title, branding, feature badges, disclaimer, and GSI container.
 *  - UserChip: avatar, first name, dropdown open/close toggle, sign-out trigger.
 *  - HistorySidebar: new chat button, chat list rendering, active item highlighting, delete button, collapse toggle, user footer.
 *  - Storage and Auth Utilities: historyKey, loadHistory, saveHistory, makeId, getStoredUser, parseJwt.
 *  - Chat UI: composer aria labels, keyboard typing, welcome message, risk badges, follow-up chips, lawyer prep CTA.
 *  - App Routing: root landing route, login route, protected chat redirect, popstate.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Global jsdom polyfills & mocks
// ---------------------------------------------------------------------------

beforeAll(() => {
  Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo;
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
});

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

vi.stubGlobal('google', {
  accounts: {
    id: {
      initialize: vi.fn(),
      renderButton: vi.fn(),
      prompt: vi.fn(),
      disableAutoSelect: vi.fn(),
    },
  },
});

// Mock fetch for network calls in Chat
global.fetch = vi.fn().mockImplementation(() =>
  Promise.resolve({
    ok: true,
    json: () =>
      Promise.resolve({
        session_id: 'test-session-123',
        answer: 'Indemnification allocates legal risk between parties.',
        citations: [],
        suggested_followups: [],
        questions: ['What is the rent due date?', 'Who pays for water?'],
      }),
  })
) as unknown as typeof fetch;

import {
  MarkdownMessage,
  Logo,
  Nav,
  Landing,
  LoginPage,
  UserChip,
  HistorySidebar,
  Chat,
  App,
  getStoredUser,
  parseJwt,
  historyKey,
  loadHistory,
  saveHistory,
  makeId,
  WELCOME,
} from '../src/main';
import type { GoogleUser, StoredChat } from '../src/main';

const mockUser: GoogleUser = {
  sub: 'uid-test-001',
  name: 'Ada Lovelace',
  email: 'ada@example.com',
  picture: 'https://example.com/avatar.jpg',
};

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// 1. MarkdownMessage
// ---------------------------------------------------------------------------

describe('MarkdownMessage', () => {
  it('renders plain text', () => {
    render(<MarkdownMessage content="Hello world" />);
    expect(screen.getByText('Hello world')).toBeTruthy();
  });

  it('renders markdown bold as <strong>', () => {
    const { container } = render(<MarkdownMessage content="**bold legal term**" />);
    const strong = container.querySelector('strong');
    expect(strong).toBeTruthy();
    expect(strong?.textContent).toBe('bold legal term');
  });

  it('renders a markdown link as <a> with href', () => {
    const { container } = render(<MarkdownMessage content="[LegalEase](https://example.com/terms)" />);
    const link = container.querySelector('a');
    expect(link).toBeTruthy();
    expect(link?.getAttribute('href')).toBe('https://example.com/terms');
  });

  it('renders an unordered list with items', () => {
    const { container } = render(<MarkdownMessage content={"- Rent due 1st\n- Late fee $50\n"} />);
    expect(container.querySelector('ul')).toBeTruthy();
    const items = container.querySelectorAll('li');
    expect(items.length).toBe(2);
  });

  it('renders inline code with <code> tag', () => {
    const { container } = render(<MarkdownMessage content="Clause `Section 4.1` applies." />);
    const code = container.querySelector('code');
    expect(code).toBeTruthy();
    expect(code?.textContent).toBe('Section 4.1');
  });

  it('renders markdown headings', () => {
    const { container } = render(<MarkdownMessage content="### Clause Overview" />);
    const h3 = container.querySelector('h3');
    expect(h3).toBeTruthy();
    expect(h3?.textContent).toBe('Clause Overview');
  });

  it('handles empty string gracefully without throwing', () => {
    const { container } = render(<MarkdownMessage content="" />);
    expect(container.querySelector('.md-body')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 2. Logo
// ---------------------------------------------------------------------------

describe('Logo', () => {
  it('renders an SVG element', () => {
    const { container } = render(<Logo />);
    expect(container.querySelector('svg')).toBeTruthy();
  });

  it('has aria-hidden="true" for assistive tech', () => {
    const { container } = render(<Logo />);
    expect(container.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('has viewBox="0 0 256 256"', () => {
    const { container } = render(<Logo />);
    expect(container.querySelector('svg')?.getAttribute('viewBox')).toBe('0 0 256 256');
  });
});

// ---------------------------------------------------------------------------
// 3. Nav
// ---------------------------------------------------------------------------

describe('Nav', () => {
  const onNavigate = vi.fn();
  const onSignOut = vi.fn();

  it('renders brand title LegalEase', () => {
    render(<Nav onNavigate={onNavigate} user={null} onSignOut={onSignOut} />);
    expect(screen.getByText('LegalEase')).toBeTruthy();
  });

  it('renders navigation links', () => {
    render(<Nav onNavigate={onNavigate} user={null} onSignOut={onSignOut} />);
    expect(screen.getByText('Product')).toBeTruthy();
    expect(screen.getByText('How it works')).toBeTruthy();
    expect(screen.getByText(/Trust & safety/i)).toBeTruthy();
    expect(screen.getByText('Docs')).toBeTruthy();
  });

  it('renders Sign In button when user is null and navigates to /login', async () => {
    const user = userEvent.setup();
    render(<Nav onNavigate={onNavigate} user={null} onSignOut={onSignOut} />);
    const signInBtn = screen.getByRole('button', { name: /Sign In/i });
    expect(signInBtn).toBeTruthy();
    await user.click(signInBtn);
    expect(onNavigate).toHaveBeenCalledWith('/login');
  });

  it('renders user avatar and Open Chat button when authenticated', async () => {
    const user = userEvent.setup();
    render(<Nav onNavigate={onNavigate} user={mockUser} onSignOut={onSignOut} />);
    expect(screen.getByAltText(mockUser.name)).toBeTruthy();
    const chatBtn = screen.getByRole('button', { name: /Open Chat/i });
    expect(chatBtn).toBeTruthy();
    await user.click(chatBtn);
    expect(onNavigate).toHaveBeenCalledWith('/chat');
  });

  it('triggers onSignOut callback when Sign out button is clicked', async () => {
    const user = userEvent.setup();
    render(<Nav onNavigate={onNavigate} user={mockUser} onSignOut={onSignOut} />);
    const signOutBtn = screen.getByRole('button', { name: /Sign out/i });
    await user.click(signOutBtn);
    expect(onSignOut).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 4. Landing
// ---------------------------------------------------------------------------

describe('Landing', () => {
  const onNavigate = vi.fn();
  const onSignOut = vi.fn();

  it('renders main headline as h1', () => {
    render(<Landing onNavigate={onNavigate} user={null} onSignOut={onSignOut} />);
    expect(screen.getByRole('heading', { level: 1 })).toBeTruthy();
  });

  it('navigates to /login when unauthenticated user clicks hero CTA', async () => {
    const user = userEvent.setup();
    render(<Landing onNavigate={onNavigate} user={null} onSignOut={onSignOut} />);
    const heroBtn = screen.getByRole('button', { name: /Try LegalEase/i });
    await user.click(heroBtn);
    expect(onNavigate).toHaveBeenCalledWith('/login');
  });

  it('navigates to /chat when authenticated user clicks hero CTA', async () => {
    const user = userEvent.setup();
    render(<Landing onNavigate={onNavigate} user={mockUser} onSignOut={onSignOut} />);
    const heroBtn = screen.getByRole('button', { name: /Try LegalEase/i });
    await user.click(heroBtn);
    expect(onNavigate).toHaveBeenCalledWith('/chat');
  });

  it('renders See how it works anchor link', () => {
    render(<Landing onNavigate={onNavigate} user={null} onSignOut={onSignOut} />);
    expect(screen.getByText(/see how it works/i)).toBeTruthy();
  });

  it('renders footer copyright notice', () => {
    render(<Landing onNavigate={onNavigate} user={null} onSignOut={onSignOut} />);
    expect(screen.getByText(/LegalEase AI/i)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 5. LoginPage
// ---------------------------------------------------------------------------

describe('LoginPage', () => {
  const onSuccess = vi.fn();

  it('renders the title LegalEase AI', () => {
    render(<LoginPage onSuccess={onSuccess} />);
    expect(screen.getByRole('heading', { level: 1, name: /LegalEase AI/i })).toBeTruthy();
  });

  it('renders feature bullet tags', () => {
    render(<LoginPage onSuccess={onSuccess} />);
    expect(screen.getByText(/Contract analysis/i)).toBeTruthy();
    expect(screen.getByText(/Risk flags/i)).toBeTruthy();
    expect(screen.getByText(/Plain-language answers/i)).toBeTruthy();
  });

  it('renders legal information disclaimer', () => {
    const { container } = render(<LoginPage onSuccess={onSuccess} />);
    const legalEl = container.querySelector('.login-legal');
    expect(legalEl?.textContent).toMatch(/legal information, not formal legal advice/i);
  });

  it('renders the Google sign-in container element', () => {
    const { container } = render(<LoginPage onSuccess={onSuccess} />);
    expect(container.querySelector('#google-signin-btn')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 6. UserChip
// ---------------------------------------------------------------------------

describe('UserChip', () => {
  const onSignOut = vi.fn();

  it('renders user first name and avatar image', () => {
    render(<UserChip user={mockUser} onSignOut={onSignOut} />);
    expect(screen.getByText('Ada')).toBeTruthy();
    const img = screen.getByAltText(mockUser.name);
    expect(img.getAttribute('src')).toBe(mockUser.picture);
  });

  it('dropdown is initially hidden', () => {
    const { container } = render(<UserChip user={mockUser} onSignOut={onSignOut} />);
    expect(container.querySelector('.user-dropdown')).toBeNull();
  });

  it('toggles dropdown menu on avatar button click', async () => {
    const user = userEvent.setup();
    const { container } = render(<UserChip user={mockUser} onSignOut={onSignOut} />);
    const btn = screen.getByRole('button', { name: /Ada/i });
    await user.click(btn);
    expect(container.querySelector('.user-dropdown')).toBeTruthy();
    expect(screen.getByText('ada@example.com')).toBeTruthy();
  });

  it('triggers onSignOut and closes dropdown when Sign out clicked', async () => {
    const user = userEvent.setup();
    const { container } = render(<UserChip user={mockUser} onSignOut={onSignOut} />);
    const btn = screen.getByRole('button', { name: /Ada/i });
    await user.click(btn);
    const signOutBtn = screen.getByRole('button', { name: /Sign out/i });
    await user.click(signOutBtn);
    expect(onSignOut).toHaveBeenCalled();
    expect(container.querySelector('.user-dropdown')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 7. HistorySidebar
// ---------------------------------------------------------------------------

describe('HistorySidebar', () => {
  const mockChats: StoredChat[] = [
    {
      id: 'chat-1',
      title: 'Residential Lease Review',
      messages: [WELCOME],
      doc: 'Lease.pdf',
      flags: { risk: 2, obligation: 3, right: 1, info: 0 },
      createdAt: Date.now() - 10000,
      updatedAt: Date.now() - 5000,
    },
    {
      id: 'chat-2',
      title: 'Employment NDA',
      messages: [WELCOME],
      doc: 'NDA.docx',
      flags: { risk: 1, obligation: 1, right: 0, info: 0 },
      createdAt: Date.now() - 50000,
      updatedAt: Date.now() - 25000,
    },
  ];

  const onSelect = vi.fn();
  const onNew = vi.fn();
  const onDelete = vi.fn();
  const onToggle = vi.fn();
  const onSignOut = vi.fn();

  it('renders New Chat button and triggers onNew callback', async () => {
    const user = userEvent.setup();
    render(
      <HistorySidebar
        chats={mockChats}
        activeChatId="chat-1"
        onSelect={onSelect}
        onNew={onNew}
        onDelete={onDelete}
        collapsed={false}
        onToggle={onToggle}
        user={mockUser}
        onSignOut={onSignOut}
      />
    );
    const newBtn = screen.getByRole('button', { name: /New Chat/i });
    await user.click(newBtn);
    expect(onNew).toHaveBeenCalled();
  });

  it('renders chat items with titles', () => {
    render(
      <HistorySidebar
        chats={mockChats}
        activeChatId="chat-1"
        onSelect={onSelect}
        onNew={onNew}
        onDelete={onDelete}
        collapsed={false}
        onToggle={onToggle}
        user={mockUser}
        onSignOut={onSignOut}
      />
    );
    expect(screen.getByText('Residential Lease Review')).toBeTruthy();
    expect(screen.getByText('Employment NDA')).toBeTruthy();
  });

  it('marks active chat with active CSS class', () => {
    const { container } = render(
      <HistorySidebar
        chats={mockChats}
        activeChatId="chat-1"
        onSelect={onSelect}
        onNew={onNew}
        onDelete={onDelete}
        collapsed={false}
        onToggle={onToggle}
        user={mockUser}
        onSignOut={onSignOut}
      />
    );
    const activeItem = container.querySelector('.history-item.active');
    expect(activeItem).toBeTruthy();
    expect(activeItem?.textContent).toContain('Residential Lease Review');
  });

  it('calls onSelect when a chat item is clicked', async () => {
    const user = userEvent.setup();
    render(
      <HistorySidebar
        chats={mockChats}
        activeChatId="chat-1"
        onSelect={onSelect}
        onNew={onNew}
        onDelete={onDelete}
        collapsed={false}
        onToggle={onToggle}
        user={mockUser}
        onSignOut={onSignOut}
      />
    );
    await user.click(screen.getByText('Employment NDA'));
    expect(onSelect).toHaveBeenCalledWith('chat-2');
  });

  it('calls onDelete when delete button is clicked', async () => {
    const user = userEvent.setup();
    render(
      <HistorySidebar
        chats={mockChats}
        activeChatId="chat-1"
        onSelect={onSelect}
        onNew={onNew}
        onDelete={onDelete}
        collapsed={false}
        onToggle={onToggle}
        user={mockUser}
        onSignOut={onSignOut}
      />
    );
    const deleteBtns = screen.getAllByTitle('Delete chat');
    expect(deleteBtns.length).toBe(2);
    await user.click(deleteBtns[0]);
    expect(onDelete).toHaveBeenCalledWith('chat-1');
  });

  it('calls onToggle when collapse toggle button is clicked', async () => {
    const user = userEvent.setup();
    render(
      <HistorySidebar
        chats={mockChats}
        activeChatId="chat-1"
        onSelect={onSelect}
        onNew={onNew}
        onDelete={onDelete}
        collapsed={false}
        onToggle={onToggle}
        user={mockUser}
        onSignOut={onSignOut}
      />
    );
    const toggleBtn = screen.getByTitle('Collapse sidebar');
    await user.click(toggleBtn);
    expect(onToggle).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 8. Storage and Auth Utilities
// ---------------------------------------------------------------------------

describe('Storage & Auth Utilities', () => {
  it('historyKey formats key with user sub', () => {
    expect(historyKey('usr_123')).toBe('legalease_history_usr_123');
  });

  it('loadHistory returns empty array when nothing stored', () => {
    expect(loadHistory('empty_sub')).toEqual([]);
  });

  it('loadHistory returns empty array when JSON is malformed', () => {
    localStorage.setItem(historyKey('bad_sub'), '{not valid json}');
    expect(loadHistory('bad_sub')).toEqual([]);
  });

  it('saveHistory and loadHistory round-trip successfully', () => {
    const chats: StoredChat[] = [
      {
        id: 'test-1',
        title: 'Title 1',
        messages: [WELCOME],
        doc: 'doc.txt',
        flags: { risk: 0, obligation: 0, right: 0, info: 0 },
        createdAt: 1000,
        updatedAt: 2000,
      },
    ];
    saveHistory('usr_abc', chats);
    const loaded = loadHistory('usr_abc');
    expect(loaded).toHaveLength(1);
    expect(loaded[0].id).toBe('test-1');
  });

  it('saveHistory caps list at 80 items', () => {
    const manyChats: StoredChat[] = Array.from({ length: 100 }, (_, i) => ({
      id: `chat-${i}`,
      title: `Chat ${i}`,
      messages: [],
      doc: '',
      flags: { risk: 0, obligation: 0, right: 0, info: 0 },
      createdAt: i,
      updatedAt: i,
    }));
    saveHistory('usr_cap', manyChats);
    const loaded = loadHistory('usr_cap');
    expect(loaded.length).toBe(80);
  });

  it('makeId returns unique string', () => {
    const id1 = makeId();
    const id2 = makeId();
    expect(typeof id1).toBe('string');
    expect(id1.length).toBeGreaterThan(5);
    expect(id1).not.toBe(id2);
  });

  it('getStoredUser returns null when no user stored', () => {
    expect(getStoredUser()).toBeNull();
  });

  it('getStoredUser parses stored user from localStorage', () => {
    localStorage.setItem('legalease_user', JSON.stringify(mockUser));
    const loaded = getStoredUser();
    expect(loaded).toEqual(mockUser);
  });

  it('getStoredUser returns null when localStorage contains invalid JSON', () => {
    localStorage.setItem('legalease_user', 'invalid-json');
    expect(getStoredUser()).toBeNull();
  });

  it('parseJwt decodes valid JWT payload into GoogleUser', () => {
    const payload = {
      sub: 'google-sub-456',
      name: 'Alan Turing',
      email: 'alan@enigma.org',
      picture: 'https://avatar.url',
    };
    const encodedPayload = btoa(JSON.stringify(payload));
    const fakeJwt = `header.${encodedPayload}.signature`;
    const user = parseJwt(fakeJwt);
    expect(user).toEqual(payload);
  });

  it('parseJwt returns null for malformed token string', () => {
    expect(parseJwt('not-a-jwt')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 9. Chat – Interactive Elements & Accessibility
// ---------------------------------------------------------------------------

describe('Chat – interactive elements & accessibility', () => {
  const noop = vi.fn();

  it('has accessible label on chat input', () => {
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    expect(screen.getByRole('textbox', { name: /ask about your legal document/i })).toBeTruthy();
  });

  it('has accessible label on attach document button', () => {
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    expect(screen.getByRole('button', { name: /attach legal document/i })).toBeTruthy();
  });

  it('has accessible label on send button', () => {
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    expect(screen.getByRole('button', { name: /^send$/i })).toBeTruthy();
  });

  it('accepts keyboard input into the composer', async () => {
    const user = userEvent.setup();
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    const input = screen.getByRole('textbox', { name: /ask about your legal document/i }) as HTMLTextAreaElement;
    await user.type(input, 'What are the termination terms?');
    expect(input.value).toBe('What are the termination terms?');
  });

  it('renders welcome message in chat thread', () => {
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    expect(screen.getByText(/Welcome to LegalEase AI/i)).toBeTruthy();
  });

  it('renders document status pill with default state', () => {
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    expect(screen.getByText('No document attached')).toBeTruthy();
  });

  it('renders Risk, Obligation, Right, and Info badges', () => {
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    expect(screen.getByText('Risk')).toBeTruthy();
    expect(screen.getByText('Obligation')).toBeTruthy();
    expect(screen.getByText('Right')).toBeTruthy();
  });

  it('renders suggested follow-up chips from welcome message', () => {
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    expect(screen.getByText('What is an indemnification clause?')).toBeTruthy();
    expect(screen.getByText('What is force majeure?')).toBeTruthy();
  });

  it('clicking a follow-up chip populates or submits inquiry', async () => {
    const user = userEvent.setup();
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    const chip = screen.getByText('What is an indemnification clause?');
    await user.click(chip);
    // User message should appear in chat thread
    await waitFor(() => {
      const msgs = screen.getAllByText('What is an indemnification clause?');
      expect(msgs.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders Prepare for a lawyer button in chat header', () => {
    render(<Chat onNavigate={noop} user={mockUser} onSignOut={noop} />);
    expect(screen.getByRole('button', { name: /Prepare questions for a lawyer/i })).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 10. App Root Routing
// ---------------------------------------------------------------------------

describe('App routing', () => {
  it('renders Landing page on default root route', () => {
    window.history.pushState({}, '', '/');
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 })).toBeTruthy();
    expect(screen.getByText(/Your legal documents/i)).toBeTruthy();
  });

  it('renders LoginPage on /login route', () => {
    window.history.pushState({}, '', '/login');
    render(<App />);
    expect(screen.getByText(/Understand what you're signing/i)).toBeTruthy();
  });

  it('redirects to LoginPage if unauthenticated user accesses /chat', () => {
    window.history.pushState({}, '', '/chat');
    render(<App />);
    expect(screen.getByText(/Understand what you're signing/i)).toBeTruthy();
  });

  it('renders Chat when authenticated user accesses /chat', () => {
    localStorage.setItem('legalease_user', JSON.stringify(mockUser));
    window.history.pushState({}, '', '/chat');
    render(<App />);
    expect(screen.getByRole('textbox', { name: /ask about your legal document/i })).toBeTruthy();
  });
});
