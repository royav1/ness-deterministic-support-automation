## activation commands
uvicorn app.main:app --reload

## redis:
redis-server

## first 2 massages for testing:
1. 

{
  "message": "VPN is not working"
}

2. 

{
  "session_id": "PASTE_SESSION_ID_HERE",
  "message": "Windows"
}

3. last massage

{
  "session_id": "5827589e-4bc1-4b09-b0ca-ab19ea45544e",
  "message": "hello"
}

## what different pages do:
VPN flow → behavior
handoff summary → facts
internal tags → meaning (normalized)
Jira payload → formatting
tenant mapping (next) → translation
You are currently exactly at the “meaning” layer.



Chatbox Support Automation (Backend)

A stateful IT support chatbot backend that simulates how internal enterprise support systems handle troubleshooting, context, and escalation.

The project focuses on deterministic automation, session-based conversation handling, and structured escalation to human support, rather than a purely generative AI chatbot.


Project Goals

This project was built to realistically demonstrate experience with:

Internal IT support automation

Session-based conversational systems

Deterministic NLP (intent classification & entity extraction)

Multi-step troubleshooting workflows

Escalation and handoff logic

Redis-backed persistence

Clean, production-style backend architecture

The design mirrors how enterprise IT chatbots are typically built before introducing LLMs.


Technology Stack

Python

FastAPI – REST API

Redis – session persistence & TTL handling

Docker-ready (Dockerization planned as final step)

Rule-based NLP (regex + context)

No frontend (API-first design)







High-Level Architecture
Request Flow

Client sends a message to /api/chat

Backend loads or creates a session

User message is stored in session history

Intent routing:

If VPN troubleshooting is active → force VPN flow

Otherwise → rule-based intent classification

Message is processed by:

VPN state machine or

Static responder

Assistant reply is stored and returned

Session state is updated in Redis

Session & Persistence Model

Sessions are identified by session_id and stored in Redis.

Each session stores:

Full message history

Last detected intent

VPN troubleshooting context (state machine data)

Session Expiration

Redis TTL automatically expires inactive sessions

No background cleanup jobs required

TTL resets on activity

VPN Troubleshooting Flow

VPN issues are handled using a deterministic state machine, not free-form chat.

States

VPN_START

VPN_ASK_OS

VPN_ASK_CLIENT

VPN_ASK_SYMPTOM

VPN_ASK_ERROR_CODE

VPN_GIVE_STEPS

VPN_CHECK_RESULT

VPN_HANDOFF

Behavior

Collects high-value information first

Uses NLP to extract entities from free text

Generates targeted troubleshooting steps

Allows a single retry

Escalates after repeated failure

Escalation & Handoff

When troubleshooting fails:

Session enters terminal state VPN_HANDOFF

A structured handoff summary is generated

API response includes handoff = true

Further chat attempts return:




NLP Usage

This project uses deterministic NLP, including:

Intent classification (VPN, email, password reset, general)

Entity extraction:

Operating system

VPN client

Symptom type

Error codes

Context-aware interpretation of replies

The system is LLM-ready, but intentionally does not depend on LLMs to function correctly.

Design Principles

Stateless API with external session store

Deterministic, auditable logic

Clear separation of concerns:

API routing

Business logic

Persistence

Enterprise-realistic escalation boundaries

Easy future integration with:

LLMs

Jira

Email systems

Planned Extensions

Docker Compose setup (FastAPI + Redis)

Jira ticket creation integration

LLM-based intent classification & entity extraction

Additional IT domains (email, password reset)

Optional frontend client