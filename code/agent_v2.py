import os
import re
import csv
from typing import Dict, List
from pathlib import Path
from retriever import SupportCorpusRetriever

class SupportAgent:
    def __init__(self, data_path: str = "../data/"):
        self.retriever = SupportCorpusRetriever(data_path)
        
        # Topic-specific response templates based on keywords
        self.topic_responses = {
            "account_access": {
                "keywords": ["access", "login", "password", "sign in", "authentication", "seat", "workspace"],
                "template": "Based on our documentation: To manage workspace access, the workspace owner or admin needs to adjust seat assignments in Settings > Team. If you're not an admin, please contact your workspace administrator."
            },
            "test_issues": {
                "keywords": ["test", "assessment", "challenge", "submission", "score", "grade"],
                "template": "According to HackerRank's documentation: Test issues can be resolved by clearing browser cache, trying an incognito window, or checking system requirements. For scoring disputes, recruiters have final discretion on candidate evaluation."
            },
            "billing": {
                "keywords": ["payment", "refund", "charge", "billing", "subscription", "money", "paid"],
                "template": "Per our billing documentation: Payment issues should be directed to our billing team at billing@company.com. Include your transaction ID for faster resolution."
            },
            "visa_fraud": {
                "keywords": ["visa", "card", "fraud", "stolen", "dispute", "charge"],
                "template": "According to Visa's guidelines: For lost/stolen cards or fraudulent charges, immediately call the number on the back of your card or Visa's Global Customer Assistance at +1 303 967 1090 (available 24/7)."
            },
            "claude_api": {
                "keywords": ["claude", "api", "bedrock", "request", "failing", "error"],
                "template": "Based on Claude documentation: API issues often resolve by checking your API key validity, rate limits, and network connectivity. Visit status.anthropic.com for service status updates."
            }
        }
    
    def process_ticket(self, issue: str, subject: str, company: str) -> Dict:
        """Process ticket using retrieval + topic matching"""
        
        # Step 1: High-risk detection
        if self.is_high_risk(issue):
            return self.high_risk_response()
        
        # Step 2: Retrieve relevant docs
        docs = self.retriever.retrieve(issue, company=company if company != "None" else None, top_k=3)
        
        # Step 3: If we have good docs, use them
        if docs and docs[0]['relevance_score'] > 0.4:
            return self.response_from_docs(issue, company, docs[0])
        
        # Step 4: Topic-based response
        topic_response = self.get_topic_response(issue, company)
        if topic_response:
            return topic_response
        
        # Step 5: Company-specific fallback
        return self.company_fallback(company, issue)
    
    def is_high_risk(self, issue: str) -> bool:
        high_risk = ['stolen', 'fraud', 'identity', 'security vulnerability', 
                    'bug bounty', 'police', 'criminal', 'hacked']
        return any(term in issue.lower() for term in high_risk)
    
    def high_risk_response(self) -> Dict:
        return {
            "status": "escalated",
            "product_area": "security",
            "request_type": "product_issue",
            "response": "This appears to be a sensitive security issue. I've escalated it to our security team who will contact you within 24 hours.",
            "justification": "High-risk content detected requiring human review"
        }
    def response_from_docs(self, issue: str, company: str, doc: Dict) -> Dict:
        """Generate response from retrieved document - extract actual answers"""
        content = doc['content']
        
        # Try to find a relevant paragraph that answers the question
        sentences = content.split('. ')
        relevant_sentences = []
        
        # Look for sentences with key terms from the issue
        issue_terms = set(issue.lower().split()[:5])
        
        for sent in sentences[:10]:  # Check first 10 sentences
            sent_lower = sent.lower()
            if any(term in sent_lower for term in issue_terms):
                relevant_sentences.append(sent.strip())
        
        # If we found relevant sentences, use them
        if relevant_sentences:
            answer = '. '.join(relevant_sentences[:3])
        else:
            # Otherwise take first 400 chars
            answer = content[:400].replace('\n', ' ')
        
        # Determine request type
        request_type = self.classify_request(issue)
        product_area = self.get_product_area_from_doc(content)
        
        # Format the response based on company
        if company == "HackerRank":
            response = f"Based on HackerRank documentation:\n\n{answer}...\n\nFor more details, visit support.hackerrank.com"
        elif company == "Claude":
            response = f"According to Claude Help Center:\n\n{answer}...\n\nNeed more help? Visit support.claude.com"
        elif company == "Visa":
            response = f"Per Visa support:\n\n{answer}...\n\nFor urgent assistance, call the number on your card."
        else:
            response = f"{answer}..."
        
        return {
            "status": "replied",
            "product_area": product_area,
            "request_type": request_type,
            "response": response[:800],
            "justification": f"Answer extracted from {doc['source']}"
        }
    def get_topic_response(self, issue: str, company: str) -> Dict:
        """Match to predefined topics"""
        issue_lower = issue.lower()
        
        # Company-specific responses
        if company == "Visa" and ("card" in issue_lower or "visa" in issue_lower):
            return {
                "status": "replied",
                "product_area": "card_services",
                "request_type": "product_issue",
                "response": "For Visa card inquiries, please call the customer service number on the back of your card or visit visa.com/support. Common issues like lost cards, fraud, or disputes are handled by your card issuer.",
                "justification": "Provided Visa card guidance based on common support patterns"
            }
        
        if company == "Claude" and ("api" in issue_lower or "bedrock" in issue_lower):
            return {
                "status": "replied",
                "product_area": "api",
                "request_type": "bug" if "failing" in issue_lower else "product_issue",
                "response": "For Claude API issues, check:\n1. Your API key is valid\n2. You haven't exceeded rate limits\n3. Service status at status.anthropic.com\n\nIf problems persist, contact support@anthropic.com",
                "justification": "Provided Claude API troubleshooting guidance"
            }
        
        if company == "HackerRank" and ("test" in issue_lower or "assessment" in issue_lower):
            return {
                "status": "replied",
                "product_area": "assessment",
                "request_type": "product_issue",
                "response": "For HackerRank test issues:\n1. Try clearing browser cache\n2. Use Chrome/Firefox browsers\n3. Check system requirements at support.hackerrank.com\n\nFor specific test problems, please contact your test administrator.",
                "justification": "Provided HackerRank test troubleshooting"
            }
        
        return None
    
    def classify_request(self, issue: str) -> str:
        issue_lower = issue.lower()
        if 'bug' in issue_lower or 'error' in issue_lower or 'not working' in issue_lower:
            return 'bug'
        elif 'feature' in issue_lower or 'suggest' in issue_lower:
            return 'feature_request'
        elif len(issue.split()) < 5:
            return 'invalid'
        return 'product_issue'
    
    def get_product_area_from_doc(self, content: str) -> str:
        content_lower = content.lower()
        if 'account' in content_lower:
            return 'account_access'
        elif 'billing' in content_lower or 'payment' in content_lower:
            return 'billing'
        elif 'test' in content_lower or 'assessment' in content_lower:
            return 'assessment'
        elif 'api' in content_lower:
            return 'api'
        return 'general_support'
    
    def company_fallback(self, company: str, issue: str) -> Dict:
        responses = {
            "HackerRank": "For HackerRank support, visit help.hackerrank.com or email support@hackerrank.com. They typically respond within 24-48 hours.",
            "Claude": "For Claude support, check help.claude.com or email support@anthropic.com. Include your conversation ID for faster assistance.",
            "Visa": "For Visa support, call the number on the back of your card. For general inquiries, visit visa.com/support.",
            "None": "Please specify which product you need help with: HackerRank, Claude, or Visa. I'll provide the appropriate support resources."
        }
        
        return {
            "status": "replied",
            "product_area": "general_support",
            "request_type": "product_issue",
            "response": responses.get(company, responses["None"]),
            "justification": f"Provided general support guidance for {company}"
        }