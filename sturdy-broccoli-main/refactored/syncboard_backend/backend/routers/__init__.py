"""
API Routers for SyncBoard 3.0 Knowledge Bank.

Each router handles a specific domain:
- auth: User authentication (register, login)
- uploads: Content upload endpoints (text, URL, file, image)
- search: Semantic search functionality
- clusters: Cluster management
- documents: Document CRUD operations
- build_suggestions: Build suggestion generation
- analytics: Analytics dashboard
- ai_generation: AI content generation
- duplicates: Duplicate detection (Phase 7.2)
- tags: Tagging system (Phase 7.3)
- saved_searches: Saved searches (Phase 7.4)
- relationships: Document relationships (Phase 7.5)
- jobs: Background job status (Celery integration - Phase 2)
- integrations: Cloud service integrations (Phase 5)
- knowledge_bases: Multi-KB support (Phase 8)
- admin: Admin utilities (Phase 9)
- knowledge_graph: Knowledge graph and relationships (Phase 10)
- project_goals: User project goals management (Phase 10)
- project_tracking: Project attempts and learnings (Phase 10)
- n8n_workflows: n8n workflow generation (Phase 10)
- generated_code: Generated code storage (Phase 10)
- knowledge_tools: Knowledge gap analysis, flashcards, learning paths, etc.
"""

from . import (
    auth,
    uploads,
    search,
    clusters,
    documents,
    build_suggestions,
    analytics,
    ai_generation,
    duplicates,
    tags,
    saved_searches,
    relationships,
    jobs,
    integrations,
    knowledge_bases,
    admin,
    knowledge_graph,
    # Phase 10: SyncBoard 3.0 Enhancement routers
    project_goals,
    project_tracking,
    n8n_workflows,
    generated_code,
    # Knowledge enhancement tools
    knowledge_tools,
    # Real-time collaboration
    websocket,
    # Usage & billing
    usage,
    # Multi-industry content generation
    content_generation,
    # Agentic learning system
    feedback,
    learning,
)
