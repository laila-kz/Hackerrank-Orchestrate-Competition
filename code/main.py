#!/usr/bin/env python3
import csv
import sys
from pathlib import Path
from agent_v2 import SupportAgent

def main():
    print("Initializing Support Agent...")
    
    # Check if Ollama is running
    import requests
    try:
        requests.get("http://localhost:11434", timeout=2)
        print("✓ Ollama is running")
    except:
        print("✗ Ollama not running! Please start Ollama first")
        print("  Download from: https://ollama.com/download/windows")
        print("  Then run: ollama pull llama3.2:3b")
        sys.exit(1)
    
    agent = SupportAgent(data_path="../data/")
    
    tickets_path = Path("../support_tickets/support_tickets.csv")
    output_path = Path("../support_tickets/output.csv")
    
    if not tickets_path.exists():
        print(f"Error: {tickets_path} not found!")
        sys.exit(1)
    
    tickets = []
    with open(tickets_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tickets.append(row)
    
    print(f"Processing {len(tickets)} tickets...")
    
    results = []
    for i, ticket in enumerate(tickets, 1):
        print(f"  Processing ticket {i}/{len(tickets)}...")
        
        try:
            result = agent.process_ticket(
                issue=ticket['Issue'],
                subject=ticket.get('Subject', ''),
                company=ticket.get('Company', 'None')
            )
        except Exception as e:
            print(f"    Error: {e}")
            result = {
                "status": "escalated",
                "product_area": "general_support",
                "response": "Error processing this ticket. Escalated to human support.",
                "justification": f"Processing error: {str(e)[:100]}",
                "request_type": "product_issue"
            }
        
        results.append({
            'issue': ticket['Issue'],
            'subject': ticket.get('Subject', ''),
            'company': ticket.get('Company', 'None'),
            'response': result.get('response', ''),
            'product_area': result.get('product_area', ''),
            'status': result.get('status', 'escalated'),
            'request_type': result.get('request_type', 'product_issue'),
            'justification': result.get('justification', '')
        })
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['issue', 'subject', 'company', 'response', 'product_area', 'status', 'request_type', 'justification']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✅ Done! Output written to {output_path}")
    print(f"Processed {len(results)} tickets")

if __name__ == "__main__":
    main()