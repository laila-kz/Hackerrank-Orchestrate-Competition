"""
Production-Grade Support Triage Agent.

Combines risk assessment, RAG vector retrieval, pattern matching,
and strict output schema formatting for multi-domain support tickets.
"""

import csv
from pathlib import Path

from classifier import TicketClassifier
from retriever import SupportCorpusRetriever


class SupportAgent:
    """Multi-domain support ticket triage agent."""

    def __init__(self, data_path: str | None = None):
        self.retriever = SupportCorpusRetriever(data_path=data_path)
        self.classifier = TicketClassifier()
        self.sample_patterns: list[dict] = []
        self._load_sample_patterns()

    def _load_sample_patterns(self):
        """
        Load gold-standard sample ticket patterns for high-precision matching.

        ``Status``, ``Product Area`` and ``Request Type`` are normalised to lower
        case on load. The sample CSV mixes capitalisation ("Replied" alongside
        "escalated"), and the output schema in problem_statement.md requires
        ``replied`` / ``escalated``. Copying the raw value leaked "Replied" into
        output.csv and broke downstream status counting.
        """
        base_dir = Path(__file__).resolve().parent
        sample_path = (base_dir / "../support_tickets/sample_support_tickets.csv").resolve()

        if sample_path.exists():
            try:
                with open(sample_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        issue_str = row.get("Issue", "").strip()
                        if issue_str:
                            self.sample_patterns.append({
                                "issue_keywords": [w.lower() for w in issue_str.split() if len(w) > 3],
                                "company": row.get("Company", "None"),
                                "response": row.get("Response", ""),
                                "product_area": row.get("Product Area", "general_support").strip().lower(),
                                "status": row.get("Status", "replied").strip().lower(),
                                "request_type": row.get("Request Type", "product_issue").strip().lower(),
                            })
            except (OSError, csv.Error, UnicodeDecodeError) as e:
                print(f"Warning: Failed to load sample patterns: {e}")

    def process_ticket(self, issue: str, subject: str = "", company: str = "None") -> dict[str, str]:
        """
        Process a support ticket through the multi-stage triage pipeline.

        Returns:
            Dict containing: status, product_area, response, justification, request_type
        """
        issue_clean = issue.strip()
        subject_clean = subject.strip()
        company_clean = company.strip() if company and company != "None" else "None"

        # Stage 1: High-Risk Security & Safety Assessment
        is_high_risk, risk_reason = self.classifier.evaluate_risk(issue_clean, subject_clean)
        if is_high_risk:
            return {
                "status": "escalated",
                "product_area": "security_compliance",
                "response": "This request involves sensitive security, fraud, or compliance concerns. It has been escalated to our human security response team.",
                "justification": f"Escalated due to security assessment: {risk_reason}",
                "request_type": "product_issue",
            }

        # Stage 2: Out-of-Scope / Invalid Request Check
        if self.classifier.is_invalid_or_out_of_scope(issue_clean):
            request_type = "invalid"
            if any(w in issue_clean.lower() for w in ["thank", "thanks", "hello", "hi"]):
                return {
                    "status": "replied",
                    "product_area": "general_support",
                    "response": "Happy to help! Please let us know if you have any further support questions.",
                    "justification": "Conversational greeting or thank-you message acknowledged",
                    "request_type": "invalid",
                }
            return {
                "status": "replied",
                "product_area": "general_support",
                "response": "I am sorry, this query is outside the scope of our supported product documentation.",
                "justification": "Out-of-scope query identified; general out-of-scope response issued",
                "request_type": "invalid",
            }

        # Stage 3: System Down / Critical Bug Escalation
        if any(term in issue_clean.lower() for term in ["site is down", "none of the pages are accessible", "outage", "system crash"]):
            return {
                "status": "escalated",
                "product_area": "general_support",
                "response": "Escalate to a human",
                "justification": "System outage / critical infrastructure bug reported",
                "request_type": "bug",
            }

        # Stage 4: Sample Ticket Grounding Match
        sample_match = self._match_sample_pattern(issue_clean, company_clean)
        if sample_match:
            return sample_match

        # Stage 5: Vector DB RAG Retrieval
        retrieved_docs = self.retriever.retrieve(issue_clean, company=company_clean, top_k=3)

        if retrieved_docs and retrieved_docs[0]["relevance_score"] >= 0.40:
            top_doc = retrieved_docs[0]
            extracted_answer = self._extract_grounded_answer(issue_clean, top_doc["content"])
            product_area = self.classifier.extract_product_area(top_doc["content"], default_company=company_clean)
            request_type = self.classifier.classify_request_type(issue_clean)

            return {
                "status": "replied",
                "product_area": product_area,
                "response": extracted_answer,
                "justification": f"Grounded response extracted from documentation chunk ({top_doc['source']}, score: {top_doc['relevance_score']})",
                "request_type": request_type,
            }

        # Stage 6: Fallback Response Generation
        request_type = self.classifier.classify_request_type(issue_clean)
        product_area = self.classifier.extract_product_area(issue_clean, default_company=company_clean)
        fallback_response = self._get_company_fallback_response(company_clean)

        return {
            "status": "replied",
            "product_area": product_area,
            "response": fallback_response,
            "justification": f"No high-confidence doc match found (best score < 0.40); provided standard support portal guidance for {company_clean}",
            "request_type": request_type,
        }

    def _match_sample_pattern(self, issue: str, company: str) -> dict[str, str] | None:
        """Match ticket against pre-seeded sample patterns."""
        issue_lower = issue.lower()
        issue_words = {w for w in issue_lower.split() if len(w) > 3}

        for pattern in self.sample_patterns:
            if company != "None" and pattern["company"] != "None" and pattern["company"] != company:
                continue

            kw_set = set(pattern["issue_keywords"])
            common = issue_words.intersection(kw_set)
            if len(common) >= 5 or (len(kw_set) > 0 and len(common) / len(kw_set) > 0.6):
                return {
                    "status": pattern["status"],
                    "product_area": pattern["product_area"],
                    "response": pattern["response"],
                    "justification": f"Matched verified resolution pattern for {company}",
                    "request_type": pattern["request_type"],
                }
        return None

    def _extract_grounded_answer(self, issue: str, doc_content: str) -> str:
        """Extract relevant concise paragraphs from retrieved document content."""
        paragraphs = [p.strip() for p in doc_content.split("\n\n") if p.strip()]
        issue_terms = {w.lower() for w in issue.split() if len(w) > 3}

        relevant_paras = []
        for para in paragraphs:
            para_lower = para.lower()
            if any(term in para_lower for term in issue_terms):
                relevant_paras.append(para)

        if relevant_paras:
            answer = "\n\n".join(relevant_paras[:2])
        else:
            answer = doc_content[:500].strip()

        if len(answer) > 800:
            answer = answer[:797] + "..."

        return answer

    def _get_company_fallback_response(self, company: str) -> str:
        """Provide domain-specific fallback support instructions."""
        guides = {
            "HackerRank": (
                "For HackerRank account, test, or candidate support issues, please visit our help center at "
                "support.hackerrank.com or contact support@hackerrank.com with your test ID or candidate email."
            ),
            "Claude": (
                "For Claude API, billing, or account management questions, visit help.claude.com or status.anthropic.com. "
                "For account privacy requests, refer to privacy.claude.com."
            ),
            "Visa": (
                "For Visa card inquiries, lost/stolen cards, or emergency assistance, please call the number on the back "
                "of your card or Visa Global Customer Assistance (+1 303 967 1090 / 000-800-100-1219 in India)."
            ),
            "None": (
                "Please specify whether your request pertains to HackerRank, Claude, or Visa so we can direct you to "
                "the appropriate support resources."
            )
        }
        return guides.get(company, guides["None"])