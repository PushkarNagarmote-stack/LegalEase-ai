from collections import Counter
import os
import re
import sys
from typing import Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="LegalEase AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, dict[str, Any]] = {}

STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'aren\'t', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'can\'t', 'cannot', 'could',
    'couldn\'t', 'did', 'didn\'t', 'do', 'does', 'doesn\'t', 'doing', 'don\'t', 'down', 'during', 'each', 'few', 'for',
    'from', 'further', 'had', 'hadn\'t', 'has', 'hasn\'t', 'have', 'haven\'t', 'having', 'he', 'her', 'here', 'hers',
    'herself', 'him', 'himself', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'itself', 'me', 'more',
    'most', 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our',
    'ours', 'ourselves', 'out', 'over', 'own', 'same', 'she', 'should', 'so', 'some', 'such', 'than', 'that', 'the',
    'their', 'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they', 'this', 'those', 'through', 'to', 'too',
    'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when', 'where', 'which', 'while', 'who', 'whom',
    'why', 'with', 'would', 'you', 'your', 'yours', 'tell', 'give', 'show', 'please'
}

SYNONYMS = {
    'rent': ['rent', 'monthly', 'payment', 'due', 'amount', 'dollars', 'pay', 'cost'],
    'deposit': ['deposit', 'security', 'wear', 'tear', 'returned', 'refund', 'escrow', 'held'],
    'terminate': ['terminate', 'termination', 'leave', 'vacate', 'end', 'notice', 'move', 'cancel', 'break', 'departure'],
    'notice': ['notice', 'written', 'days', 'sixty', 'thirty', 'notify', 'advance', 'formal'],
    'late': ['late', 'fee', 'grace', 'penalty', '5th', 'assessed', 'charge'],
    'repair': ['repair', 'repairs', 'maintenance', 'plumbing', 'electrical', 'structural', 'fix', 'damage', 'condition'],
    'term': ['term', 'months', 'duration', 'commence', 'expire', 'period', 'year', 'length'],
    'pet': ['pet', 'pets', 'dog', 'cat', 'animal', 'breed'],
    'guest': ['guest', 'guests', 'visitor', 'visitors', 'stay', 'overnight'],
    'entry': ['entry', 'enter', 'inspection', 'access', 'hours', 'emergency'],
    'alteration': ['alteration', 'paint', 'modify', 'decorat', 'renovat', 'lock'],
    'utility': ['utility', 'utilities', 'water', 'gas', 'electric', 'trash', 'sewer', 'heat'],
}

LEGAL_KNOWLEDGE_BASE = {
    'indemn': {
        'topic': 'Indemnification Clauses',
        'content': 'An **indemnification clause** is a risk-shifting provision where one party agrees to compensate (or "hold harmless") the other for certain damages, legal liabilities, or lawsuits arising from the contract.\n\n- **In Leases**: Landlords frequently include this so tenants cover claims if a guest slips or property is damaged due to tenant negligence.\n- **Negotiation Tip**: Ensure indemnification is **mutual** and explicitly excludes the other party\'s gross negligence or willful misconduct.',
        'followups': ['What is the difference between indemnify and hold harmless?', 'How can I limit my liability in a contract?']
    },
    'force majeure': {
        'topic': 'Force Majeure ("Act of God")',
        'content': 'A **force majeure clause** excuses contractual obligations when extraordinary, unforeseeable events beyond the parties\' control occurâ€”such as natural disasters, wars, or government lockdowns.\n\n- **Key Rule**: Courts interpret force majeure strictly. If an event is not specifically listed in the clause, it may not be excused.\n- **Important**: In residential leases, force majeure rarely excuses rent payment unless the premises become completely uninhabitable.',
        'followups': ['Does force majeure excuse rent during emergencies?', 'What makes a valid force majeure event?']
    },
    'severab': {
        'topic': 'Severability Provisions',
        'content': 'A **severability clause** states that if any single term or clause in the contract is found unlawful or unenforceable by a court, the remainder of the agreement stays legally binding and in effect.\n\n- **Purpose**: It prevents the entire contract from collapsing just because one aggressive term violated local statutory law.',
        'followups': ['What happens if a contract doesn\'t have severability?', 'Can an illegal clause void a whole contract?']
    },
    'arbitrat': {
        'topic': 'Arbitration & Dispute Resolution',
        'content': 'An **arbitration clause** requires parties to resolve legal disputes outside of court before a neutral private arbitrator rather than through a public judge and jury.\n\n- **Pros**: Faster, private, and confidential.\n- **Cons**: Often limits discovery rights, eliminates jury trials, and generally cannot be appealed.\n- **Look For**: Whether arbitration is mandatory or optional, and whether you retain the right to resolve issues in small claims court.',
        'followups': ['Can I opt out of an arbitration clause?', 'Is arbitration better or worse for tenants?']
    },
    'liquidat': {
        'topic': 'Liquidated Damages',
        'content': 'A **liquidated damages clause** specifies a pre-agreed financial penalty that one party must pay if they breach the contract (e.g. breaking a lease early or late performance).\n\n- **Legal Standard**: To be enforceable, the amount must be a reasonable estimate of anticipated damages at the time of signing, not a punitive penalty.\n- **If Unreasonable**: Courts will strike down excessive liquidated damages as unenforceable penalties.',
        'followups': ['How can I challenge an excessive fee or penalty?', 'What makes liquidated damages enforceable?']
    },
    'quiet enjoy': {
        'topic': 'Covenant of Quiet Enjoyment',
        'content': 'The **implied covenant of quiet enjoyment** guarantees that a tenant can live in the property peacefully without substantial interference, harassment, or unlawful entry from the landlord.\n\n- **Examples of Breach**: Unannounced landlord entries, chronic unaddressed noise or harassment, or failing to fix uninhabitable conditions.',
        'followups': ['Can a landlord enter my apartment without notice?', 'What should I do if a landlord violates quiet enjoyment?']
    },
    'habitab': {
        'topic': 'Warranty of Habitability',
        'content': 'The **implied warranty of habitability** requires residential landlords to provide living conditions that are safe, clean, and fit for human habitation, regardless of what the lease says.\n\n- **Standard Requirements**: Working plumbing, hot/cold running water, effective heating/weatherproofing, sanitary conditions, and smoke/CO alarms.\n- **Legal Protections**: Leases cannot waive or contract away habitability protections in most jurisdictions.',
        'followups': ['Can I withhold rent for broken heat or hot water?', 'What is repair and deduct?']
    },
}

def split_document_into_clauses(text: str, filename: str) -> list[dict[str, Any]]:
    clean_fname = os.path.basename(filename)
    section_pattern = r'\n(?=(?:[0-9]{1,2}\.|\bSection\b|\bArticle\b|\bClause\b)\s+[A-Za-z0-9])'
    parts = re.split(section_pattern, text)
    if len(parts) <= 1:
        parts = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]

    clauses = []
    for i, p in enumerate(parts, 1):
        clean = p.strip()
        if len(clean) < 15:
            continue
        first_line = clean.split('\n')[0].strip()
        m_head = re.match(r'^((?:Section|Article|Clause|[0-9]{1,2}\.)\s*[^.\n:;]+(?:[:.][^.\n:;]+)?)', first_line, re.IGNORECASE)
        if m_head:
            heading = m_head.group(1).strip()
        else:
            heading = re.sub(r'^[#*\s]+', '', first_line)[:45].strip()
        ref = f"{heading}" if heading else f"Section {i}"
        clauses.append({
            'ref': ref,
            'text': clean,
            'heading': heading.lower(),
            'type': classify_clause(clean)
        })
    return clauses or [{'ref': f'{clean_fname} - Section 1', 'text': text, 'heading': 'agreement', 'type': 'info'}]

def classify_clause(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ('terminate', 'penalty', 'fee', 'forfeit', 'liable', 'default', 'breach', 'damages', 'indemnify', 'late fee')):
        return 'risk'
    if any(x in t for x in ('must', 'shall', 'required', 'notice', 'responsible', 'obligation', 'covenant', 'pay', 'notify')):
        return 'obligation'
    if any(x in t for x in ('right', 'may request', 'entitled', 'landlord shall', 'tenant may', 'permitted', 'option', 'refund')):
        return 'right'
    return 'info'

def retrieve_clauses(session: dict[str, Any], question: str) -> list[dict[str, Any]]:
    clauses = session.get('chunks', [])
    if not clauses:
        return []

    q_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', question) if w.lower() not in STOP_WORDS]
    expanded_q = set(q_words)
    for w in q_words:
        for root, syns in SYNONYMS.items():
            if w in syns or w == root:
                expanded_q.update(syns)

    scored = []
    for c in clauses:
        c_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', c['text'])]
        c_counts = Counter(c_words)

        score = 0.0
        for qw in expanded_q:
            if qw in c['heading']:
                score += 8.0
            if qw in c_counts:
                score += min(c_counts[qw], 4) * 2.0

        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_matches = [x[1] for x in scored if x[0] > 0]
    return top_matches[:3]

def try_gemini_llm(message: str, session: dict[str, Any], api_key: str | None) -> dict[str, Any] | None:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        doc_context = ""
        chunks = session.get('chunks', [])
        if chunks:
            doc_context = "UPLOADED DOCUMENT EXCERPTS:\n" + "\n\n".join(
                f"- {c['ref']}:\n{c['text'][:800]}" for c in chunks[:6]
            )

        system_instruction = (
            "You are LegalEase AI, an expert conversational legal-literacy assistant. "
            "You help users understand agreements and legal concepts in clear, plain language. "
            "Do NOT include raw citation brackets like [1] or [2] in your response text. Refer naturally to clauses by name if referencing the document. "
            "Format your answers with clean markdown: clear headings, bullet points, bold key terms. "
            "When answering questions about the uploaded document, ground your answers in the provided excerpts. "
            "When answering general legal questions, definitions, negotiation tactics, or conversational queries, answer helpfully, thoroughly, and naturally. "
            "Always maintain a clear distinction between legal information and formal attorney representation."
        )

        user_content = f"{doc_context}\n\nUSER QUESTION: {message}" if doc_context else message

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3
            )
        )
        if response and response.text:
            clean_answer = re.sub(r'\[\d+\]', '', response.text).strip()
            return {
                'answer': clean_answer,
                'citations': [{'clause_ref': c['ref'], 'source_text': c['text'][:700]} for c in chunks[:3]],
                'suggested_followups': ['What are my biggest legal risks?', 'What should I negotiate?', 'What questions should I ask an attorney?']
            }
    except Exception as e:
        print(f"Gemini call fallback: {e}")
        return None
    return None

def generate_conversational_response(question: str, session: dict[str, Any]) -> dict[str, Any]:
    q_lower = question.lower().strip()

    # 1. Greetings
    if any(q_lower.startswith(g) for g in ('hi', 'hello', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening')):
        has_doc = bool(session.get('chunks'))
        doc_note = f"I see you have **{session.get('file_names', ['your document'])[-1]}** loaded." if has_doc else "You can upload a contract or lease anytime using the **Upload Document** button on the left."
        return {
            'answer': (
                "Hello! I am **LegalEase AI**, your conversational legal document and literacy assistant.\n\n"
                "I can help you:\n"
                "- **Read & Analyze Agreements**: Understand leases, employment agreements, NDAs, and service contracts in plain language.\n"
                "- **Identify Specific Terms**: Pinpoint exact rent amounts, notice periods, deadlines, and deposit conditions.\n"
                "- **Flag Hidden Risks**: Highlight aggressive indemnification, unilateral penalties, and missing protections.\n"
                "- **Prepare for Legal Counsel**: Organize high-priority questions to review with an attorney.\n\n"
                f"{doc_note}\n\n"
                "How can I help you today?"
            ),
            'citations': [],
            'suggested_followups': [
                'What are common traps in residential leases?',
                'How do I negotiate my contract terms?',
                'What is an indemnification clause?'
            ]
        }

    # 2. How it works / Self-introduction
    if any(k in q_lower for k in ('how you work', 'how do you work', 'how does this work', 'how does it work', 'what do you do', 'what can you do', 'who are you', 'tell me about yourself', 'how it works', 'explain yourself')):
        has_doc = bool(session.get('chunks'))
        doc_status = f"You currently have **{session.get('file_names', ['your document'])[-1]}** active." if has_doc else "You haven't uploaded a document yet."
        return {
            'answer': (
                "### How LegalEase AI Works\n\n"
                "LegalEase AI is built to give everyday individuals and small business owners the clarity they need when facing complex legal contracts.\n\n"
                "**1. Document Ingestion & Clause Detection**\n"
                "When you upload a document (PDF, DOCX, TXT), I parse the document into individual sections and categorize them into **Risks** (penalties, liabilities), **Obligations** (duties, payments), and **Rights** (tenant/client entitlements).\n\n"
                "**2. Plain-Language Q&A**\n"
                "You can ask natural questions like *'When is rent considered late?'*, *'Can the landlord enter without notice?'*, or *'What happens if I terminate early?'* without using legal jargon.\n\n"
                "**3. Direct Source Grounding**\n"
                "Instead of guessing, every answer links back to the exact contract clause so you can verify the original legal wording yourself.\n\n"
                "**4. Attorney Preparation**\n"
                "Click the **'Prepare for a lawyer'** button to produce an organized list of high-risk flags and tailored questions to maximize your time with legal counsel.\n\n"
                f"*{doc_status} Feel free to ask any question or test with the sample lease!*"
            ),
            'citations': [],
            'suggested_followups': [
                'What should I look for before signing a lease?',
                'How do I negotiate contract terms?',
                'What makes a contract legally binding?'
            ]
        }

    # 3. Document Summary / Overview
    if any(k in q_lower for k in ('summarize', 'summary', 'overview', 'what is this document', 'explain this document', 'what is in this document')):
        chunks = session.get('chunks', [])
        if not chunks:
            return {
                'answer': (
                    "No document is currently loaded. To get a comprehensive summary and breakdown, "
                    "please upload a file (PDF, DOCX, or TXT) using the **Upload Document** button, "
                    "or click **Load Sample Lease** to try an example agreement."
                ),
                'citations': [],
                'suggested_followups': ['Load Sample Lease', 'What is an indemnification clause?']
            }
        file_name = session.get('file_names', ['Uploaded Document'])[-1]
        headings = [c['heading'].title() for c in chunks[:6] if c.get('heading')]
        return {
            'answer': (
                f"### Document Summary: **{file_name}**\n\n"
                f"I have parsed **{len(chunks)} sections** in this document.\n\n"
                "**Key Clauses Identified**:\n"
                + "\n".join(f"- **{h}**" for h in headings)
                + "\n\n"
                "You can ask me specific questions about rent amounts, termination rules, notice periods, repair obligations, or liability limits!"
            ),
            'citations': [{'clause_ref': c['ref'], 'source_text': c['text'][:700]} for c in chunks[:3]],
            'suggested_followups': [
                'What are my main financial obligations?',
                'What are the notice requirements to terminate?',
                'Are there any high-risk clauses or penalties?'
            ]
        }

    # 4. Pre-signing checklist / Red flags
    if any(k in q_lower for k in ('before signing', 'checklist', 'what to look for', 'red flags', 'signing an agreement', 'common traps')):
        return {
            'answer': (
                "### Checklist: What to Look For Before Signing\n\n"
                "Before signing any contract or lease, verify these critical items:\n\n"
                "- **Financial Terms & Hidden Charges**: Confirm the base fee/rent, due dates, grace periods, and late penalty formulas.\n"
                "- **Duration & Renewal**: Check automatic renewal triggers and the exact advance notice required to terminate (e.g. 30 vs 60 days).\n"
                "- **Termination & Early Exit**: Look for early cancellation fees, liquidated damages, or subletting restrictions.\n"
                "- **Maintenance & Repairs**: Ensure the other party is explicitly responsible for major structural and essential utility repairs.\n"
                "- **Dispute Resolution**: Watch out for mandatory arbitration clauses or waivers of jury trial rights.\n\n"
                "*Golden Rule: Never rely on verbal assurances. If something was promised verbally, insist it is written into the agreement.*"
            ),
            'citations': [],
            'suggested_followups': [
                'How can I negotiate terms before signing?',
                'What makes a contract legally binding?',
                'What is a liquidated damages clause?'
            ]
        }

    # 5. Contract Negotiation Strategies
    if any(k in q_lower for k in ('negotiat', 'how to negotiate', 'bargain')):
        return {
            'answer': (
                "### Practical Contract Negotiation Strategies\n\n"
                "Most agreements and residential leases are negotiable before signing. Here are effective strategies:\n\n"
                "1. **Identify Unbalanced Clauses**: Look for one-sided indemnification, aggressive penalties, or vague repair timelines.\n"
                "2. **Propose Mutual Wording**: If a clause states you must indemnify the other party, request that the indemnification be **mutual**.\n"
                "3. **Replace Ambiguity with Specifics**: If a clause says *'reasonable notice'*, ask for an explicit timeframe like *'at least 24 hours written notice'*.\n"
                "4. **Leverage Your Strengths**: Strong credit, timely payments, or agreeing to a longer term can be traded for concessions like lower deposits or waived fees.\n"
                "5. **Use Written Addenda**: If changes are agreed upon, initial the edits directly on the contract or attach a signed addendum."
            ),
            'citations': [],
            'suggested_followups': [
                'What is an indemnification clause?',
                'Can I opt out of an arbitration clause?',
                'What should I look for before signing?'
            ]
        }

    # 6. Contract Validity
    if any(k in q_lower for k in ('binding', 'valid contract', 'enforceab', 'legally binding')):
        return {
            'answer': (
                "### What Makes a Contract Legally Binding?\n\n"
                "For an agreement to be legally enforceable in court, four fundamental elements must exist:\n\n"
                "1. **Offer and Acceptance**: One party proposes specific terms, and the other party clearly accepts them without material modification.\n"
                "2. **Consideration**: Something of legal value must be exchanged (money, goods, services, or a promise to act/refrain from acting).\n"
                "3. **Capacity & Legality**: Both parties must have the legal capacity to contract (adult age, mental competence), and the agreement's purpose must be legal.\n"
                "4. **Mutual Assent ('Meeting of the Minds')**: Both parties must genuinely agree to the terms without fraud, coercion, or misrepresentation.\n\n"
                "*Note: Under the Statute of Frauds, contracts involving real estate or leases exceeding one year must be in writing to be enforceable.*"
            ),
            'citations': [],
            'suggested_followups': [
                'What makes a clause unenforceable?',
                'What is a severability clause?',
                'What is an indemnification clause?'
            ]
        }

    # 7. General Legal Knowledge Base matching
    for key, item in LEGAL_KNOWLEDGE_BASE.items():
        if key in q_lower:
            return {
                'answer': (
                    f"### Legal Insight: {item['topic']}\n\n"
                    f"{item['content']}\n\n"
                    f"*Note: This is general legal information. For jurisdiction-specific legal counsel, consult a qualified attorney.*"
                ),
                'citations': [],
                'suggested_followups': item['followups']
            }

    # 8. Document-grounded matching
    has_chunks = bool(session.get('chunks'))
    if has_chunks:
        matches = retrieve_clauses(session, question)
        if matches:
            top_clause = matches[0]
            citations = [{'clause_ref': c['ref'], 'source_text': c['text'][:700]} for c in matches]
            answer = generate_grounded_answer(top_clause, question, matches[1:])
            followups = build_followups(top_clause, question)
            return {'answer': answer, 'citations': citations, 'suggested_followups': followups}

    # 9. Natural conversational fallback
    return {
        'answer': (
            f"Here is a plain-language legal perspective regarding **{question}**:\n\n"
            "In contract law and legal agreements, this subject typically governs how responsibilities, risks, and remedies are allocated between parties.\n\n"
            "**Key Considerations**:\n"
            "- **Balance of Obligations**: Check whether the requirement applies mutually or places unilateral risk on one party.\n"
            "- **Clear Timelines**: Look for explicit calendar deadlines, business-day calculations, or grace periods.\n"
            "- **Remedies for Breach**: Identify what specific consequences (cure periods, liquidated damages, or termination rights) trigger if this requirement is not met.\n\n"
            "If you have a specific agreement containing this language, upload it on the left panel and I will pinpoint the exact clause wording for you."
        ),
        'citations': [],
        'suggested_followups': [
            'What should I look for before signing an agreement?',
            'How can I negotiate terms with the other party?',
            'What makes a contract legally binding?'
        ]
    }

def generate_grounded_answer(clause: dict[str, Any], question: str, other_clauses: list[dict[str, Any]]) -> str:
    ref = clause['ref']
    text = clause['text']
    clause_type = clause['type'].capitalize()

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 8]

    q_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9$]+', question.lower()) if w.lower() not in STOP_WORDS]
    ranked_sentences = []
    for s in sentences:
        s_lower = s.lower()
        match_count = sum(1 for w in q_words if w in s_lower)
        has_data = any(ch in s for ch in ('$', '%')) or any(w in s_lower for w in ('day', 'days', 'month', 'shall', 'must', 'due', 'pay', 'notice', 'fee', 'deposit', 'repair', 'terminate'))
        score = match_count * 2 + (1.5 if has_data else 0)
        ranked_sentences.append((score, s))

    ranked_sentences.sort(key=lambda x: x[0], reverse=True)
    primary_sentences = [x[1] for x in ranked_sentences if x[0] > 0][:2]
    if not primary_sentences and sentences:
        primary_sentences = sentences[:2]

    direct_finding = " ".join(primary_sentences)

    amounts = re.findall(r'\$[0-9,]+(?:\.[0-9]{2})?', direct_finding)
    deadlines = re.findall(r'\b[0-9]{1,3}\b(?:\s*\(?[0-9]{1,3}\)?)?\s*days?', direct_finding, re.IGNORECASE)

    key_points = []
    if amounts:
        key_points.append(f"**Specific Amounts**: {', '.join(amounts)}")
    if deadlines:
        key_points.append(f"**Timeframes / Notice**: {', '.join(deadlines)}")
    if any(k in direct_finding.lower() for k in ('late fee', 'penalty', 'forfeit', 'interest')):
        key_points.append("**Penalties**: Non-compliance carries financial or contractual consequences.")

    answer_parts = [
        f"Based on **{ref}** ({clause_type}):\n",
        f'> "{direct_finding}"\n',
    ]
    if key_points:
        answer_parts.append("\n**Key Takeaways**:\n" + "\n".join(f"- {pt}" for pt in key_points))
    else:
        answer_parts.append("\n**Summary**: This clause establishes the binding expectations and contractual terms on this subject.")

    answer_parts.append("\n\n*Note: This is document-grounded legal information, not formal legal advice. Consult an attorney for jurisdiction-specific rights.*")
    
    raw_answer = "\n".join(answer_parts)
    return re.sub(r'\[\d+\]', '', raw_answer).strip()

def build_followups(clause: dict[str, Any], question: str) -> list[str]:
    combined = (clause['text'] + ' ' + question).lower()
    if 'rent' in combined or 'fee' in combined:
        return ['When is rent legally considered late?', 'What happens if a late fee is disputed?', 'Can the landlord raise the rent during the term?']
    if 'deposit' in combined:
        return ['What counts as ordinary wear and tear?', 'What deductions are permitted from the deposit?', 'How do I document condition at move-in?']
    if 'notice' in combined or 'vacate' in combined or 'terminate' in combined:
        return ['Can this notice period be negotiated?', 'What happens if I need to leave before the lease ends?', 'Must notice be delivered by certified mail?']
    if 'repair' in combined or 'maintenance' in combined:
        return ['What repairs is the landlord strictly required to make?', 'Can I deduct repair costs from rent?', 'What is an acceptable timeline for repairs?']
    return ['What are my main obligations under this clause?', 'Does this term pose any unexpected liabilities?', 'What specific questions should I ask an attorney?']

def extract_text_from_file(filename: str, data: bytes) -> str:
    name = filename.lower()

    if name.endswith('.txt') or name.endswith('.md'):
        for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode('utf-8', errors='ignore')

    if name.endswith('.pdf'):
        # 1. If not starting with %PDF, treat as plaintext/markdown saved with .pdf
        if not data.startswith(b'%PDF'):
            for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
                try:
                    dec = data.decode(enc)
                    if len(dec.strip()) > 10:
                        return dec
                except Exception:
                    pass

        # 2. Standard pypdf extraction
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text_pages = []
            for i, page in enumerate(reader.pages):
                txt = page.extract_text() or ''
                if txt.strip():
                    text_pages.append(txt.strip())
            full_text = "\n\n".join(text_pages).strip()
            if len(full_text) > 20:
                return full_text
        except Exception as e:
            print(f"pypdf extraction error: {e}")

        raise ValueError("This PDF contains scanned images or non-extractable text. Please copy/paste the text directly or upload a text-based document.")

    if name.endswith('.docx'):
        import zipfile
        import io
        import xml.etree.ElementTree as ET
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                xml_content = zf.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                paragraphs = []
                for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    texts = [node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]
                    if texts:
                        paragraphs.append("".join(texts))
                return "\n\n".join(paragraphs)
        except Exception as e:
            raise ValueError(f"DOCX extraction failed: {e}")

    return data.decode('utf-8', errors='ignore')

class ChatRequest(BaseModel):
    message: str
    api_key: str | None = None

@app.get('/health')
def health():
    return {'status': 'healthy', 'service': 'LegalEase AI'}

@app.post('/api/session')
def create_session():
    import uuid
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {'chunks': [], 'history': [], 'file_names': []}
    return {'session_id': sid}

@app.post('/api/session/{session_id}/document')
@app.post('/api/session/{session_id}/upload')
async def upload_document(session_id: str, file: UploadFile = File(...)):
    s = sessions.get(session_id)
    if not s:
        s = sessions[session_id] = {'chunks': [], 'history': [], 'file_names': []}

    content = await file.read()
    filename = file.filename or 'document.txt'
    try:
        text = extract_text_from_file(filename, content)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    if not text.strip():
        raise HTTPException(status_code=400, detail="The document contained no readable text.")

    clauses = split_document_into_clauses(text, filename)
    s['chunks'].extend(clauses)
    s['file_names'].append(filename)

    counts = Counter(c['type'] for c in s['chunks'])

    return {
        'message': f"I have analyzed **{filename}** and parsed **{len(clauses)} clauses** into your active session.",
        'clauses_count': len(clauses),
        'citations': [{'clause_ref': c['ref'], 'source_text': c['text'][:700]} for c in clauses[:3]],
        'suggested_followups': [
            'What are the key financial terms and rent due dates?',
            'What notice is required before terminating or vacating?',
            'Are there any penalties, fees, or indemnification risks?'
        ],
        'flags': {
            'risk': counts['risk'],
            'obligation': counts['obligation'],
            'right': counts['right'],
            'info': counts['info']
        }
    }

@app.post('/api/session/{session_id}/chat')
def chat(session_id: str, request: ChatRequest):
    s = sessions.get(session_id)
    if not s:
        s = sessions[session_id] = {'chunks': [], 'history': [], 'file_names': []}

    llm_result = try_gemini_llm(request.message, s, request.api_key)
    if llm_result:
        s['history'].append({'role': 'user', 'content': request.message})
        s['history'].append({'role': 'assistant', 'content': llm_result['answer']})
        return llm_result

    result = generate_conversational_response(request.message, s)
    s['history'].append({'role': 'user', 'content': request.message})
    s['history'].append({'role': 'assistant', 'content': result['answer']})
    return result

@app.post('/api/session/{session_id}/prepare-for-lawyer')
def prepare(session_id: str):
    s = sessions.get(session_id)
    if not s or not s.get('chunks'):
        return {
            'questions': [
                "Does this agreement comply with state and local tenant/consumer protection laws?",
                "Are the indemnification and liability limitations enforceable in my jurisdiction?",
                "What remedies do I have if the other party breaches their covenants?",
                "Can any of the liquidated damage provisions be challenged as unreasonable penalties?",
                "Is the dispute resolution/arbitration clause mandatory or can it be negotiated out?"
            ]
        }

    chunks = s['chunks']
    risks = [c for c in chunks if c['type'] == 'risk']
    obs = [c for c in chunks if c['type'] == 'obligation']

    questions = []
    for r in risks[:3]:
        questions.append(f"Regarding '{r['ref']}': Can this penalty/liability be made mutual or capped at a specific dollar amount?")
    for o in obs[:2]:
        questions.append(f"Regarding '{o['ref']}': Is this timeline or obligation standard under local governing law?")

    if not questions:
        questions = [
            "Are there any jurisdiction-specific implied warranties not covered by this document?",
            "What notice requirements must I follow to preserve my legal remedies?"
        ]

    return {'questions': questions}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8001)


