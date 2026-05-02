# Support Triage Agent for HackerRank Orchestrate

## Overview

A terminal-based AI agent that automatically triages and responds to support tickets across three product ecosystems:
- **HackerRank** - Assessment platform support
- **Claude** - AI assistant help center  
- **Visa** - Card services and fraud support

The agent uses RAG (Retrieval-Augmented Generation) with a vector database to ground answers in official support documentation, ensuring no hallucinated policies or incorrect information.

## Features

- ✅ **Multi-company support** - Automatically detects and routes HackerRank, Claude, and Visa tickets
- ✅ **Smart escalation** - Identifies high-risk issues (fraud, security vulnerabilities, identity theft) for human review
- ✅ **Document-grounded responses** - Answers based on 3,221 indexed support document chunks
- ✅ **Terminal-based** - Runs completely from command line
- ✅ **CSV input/output** - Processes batch tickets and generates predictions

## Technology Stack

| Component | Technology |
|-----------|------------|
| Vector Database | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Classification | Rule-based pattern matching |
| Language | Python 3.9+ |

## Installation

### Prerequisites
```bash
Python 3.9 or higher
pip package manager
