# 🚀 STURDY BROCCOLI - FEATURE ROADMAP

**Current Status:** 473/475 tests passing, production-ready core system

---

## 🎯 IMMEDIATE WINS (1-2 Hours Each)

### 1. Fix Build Suggester Quality Filter

**Problem:** Filter too strict - marks everything "low" coverage, users see zero suggestions

**Location:** `backend/llm_providers.py` line 345

**Current Code:**
```python
if s.get("knowledge_coverage", "low") in ["high"]:
    filtered.append(s)
```

**Fix Option A - Accept Medium Too:**
```python
if s.get("knowledge_coverage", "low") in ["high", "medium"]:
    filtered.append(s)
```

**Fix Option B - Default Filter to OFF:**
In `backend/routers/build_suggestions.py` line 112:
```python
enable_quality_filter: bool = False  # Changed from True
```

**Why:** Users with <20 docs get frustrated seeing "no suggestions" when AI has generated 5 ideas marked "low" coverage. Better to show them with warnings.

---

### 2. Force Re-cluster Button

**What:** Let users manually trigger re-clustering of all their documents

**Where:** New endpoint in `backend/routers/clusters.py`

**Implementation:**
```python
@router.post("/recluster")
async def force_recluster_all(
    current_user: User = Depends(get_current_user)
):
    """
    Force re-clustering of all user's documents.
    
    Useful when:
    - User has added lots of new content
    - Existing clusters seem wrong
    - Want to start fresh with clustering
    """
    from ..dependencies import get_documents, get_metadata, get_clusters
    from ..clustering_improved import ImprovedClusteringEngine
    
    documents = get_documents()
    metadata = get_metadata()
    clusters = get_clusters()
    
    # Get all user's doc IDs across all KBs
    user_doc_ids = []
    for kb_id, kb_metadata in metadata.items():
        for doc_id, meta in kb_metadata.items():
            if meta.owner == current_user.username:
                user_doc_ids.append(doc_id)
    
    # Clear existing clusters for this user
    # (Keep the cluster structure, just remove doc assignments)
    
    # Re-run clustering
    clustering_engine = ImprovedClusteringEngine()
    new_clusters = clustering_engine.cluster_documents(
        doc_ids=user_doc_ids,
        documents=documents,
        metadata=metadata
    )
    
    # Update cluster assignments
    # Save to database
    
    return {
        "message": f"Re-clustered {len(user_doc_ids)} documents",
        "clusters_created": len(new_clusters),
        "doc_count": len(user_doc_ids)
    }
```

**Frontend:** Add button in Clusters view: "Re-cluster All Documents"

**Why:** Sometimes auto-clustering gets it wrong after you've added 50 docs. Give users the reset button.

---

### 3. Batch Upload Progress Bar

**Problem:** Uploading 10 files shows "processing..." with no progress

**What:** Show real-time progress: "Processing file 3 of 10... Extracting text from PDF..."

**Where:** 
- Backend: Already tracked in Celery tasks (`backend/tasks.py`)
- Frontend: Poll `/jobs/{job_id}/status` endpoint

**Frontend Implementation (in `app.js`):**
```javascript
async function uploadMultipleFiles(files) {
    const progressDiv = document.getElementById('upload-progress');
    progressDiv.innerHTML = `
        <div class="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
        </div>
        <p id="progress-text">Uploading 0 of ${files.length}...</p>
    `;
    
    let completed = 0;
    for (const file of files) {
        const jobId = await uploadFile(file);
        
        // Poll for completion
        const result = await pollJobStatus(jobId);
        
        completed++;
        updateProgress(completed, files.length);
    }
}

function updateProgress(current, total) {
    const percent = (current / total) * 100;
    document.getElementById('progress-fill').style.width = `${percent}%`;
    document.getElementById('progress-text').textContent = 
        `Processing ${current} of ${total}...`;
}
```

**Why:** User feedback. Big uploads feel faster when you see progress.

---

## 🔨 MEDIUM EFFORT (Next Week)

### 4. Wire Up Document Relationships

**Status:** Database tables exist (`DBDocumentRelationship`), not connected

**What:** Show related documents:
- "Documents similar to this one"
- "Prerequisites" - read these first
- "Follow-up" - read these next
- "Alternative perspectives"

**Implementation Plan:**

**Step 1 - Auto-discovery (use existing vector search):**
```python
# In backend/advanced_features_service.py (already exists!)
def find_related_documents(doc_id: int, top_k: int = 5):
    """Find documents similar to this one using vector search."""
    doc_content = documents[doc_id]
    
    # Search for similar docs
    results = vector_store.search(doc_content, top_k=top_k+1)
    
    # Filter out self, return top_k
    related = [r for r in results if r[0] != doc_id][:top_k]
    
    return related
```

**Step 2 - Add endpoint:**
```python
# In backend/routers/relationships.py (file exists, needs implementation)
@router.get("/documents/{doc_id}/related")
async def get_related_documents(
    doc_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get documents related to this one."""
    # Check ownership
    # Find related docs
    # Return with similarity scores
    pass
```

**Step 3 - Frontend widget:**
Add "Related Documents" section when viewing a doc.

**Why:** Makes knowledge exploration organic. Users discover connections they didn't know existed.

---

### 5. Smart Notifications

**What:** System notices patterns and suggests actions

**Examples:**
- "You uploaded 5 FastAPI docs yesterday. Generate a summary?"
- "You have 3 Python scripts with no cluster. Want me to organize them?"
- "Your 'Machine Learning' cluster has 50 docs. Split it?"

**Implementation:**
```python
# New file: backend/notification_engine.py
class NotificationEngine:
    def analyze_recent_activity(self, user: str, days: int = 7):
        """Analyze user's recent uploads and suggest actions."""
        recent_docs = get_recent_docs(user, days)
        
        notifications = []
        
        # Pattern 1: Lots of docs on same topic
        topic_clusters = group_by_topic(recent_docs)
        for topic, docs in topic_clusters.items():
            if len(docs) >= 3:
                notifications.append({
                    "type": "summary_suggestion",
                    "message": f"You uploaded {len(docs)} docs about {topic}. Generate a summary?",
                    "action": "generate_summary",
                    "doc_ids": docs
                })
        
        # Pattern 2: Unclustered docs
        unclustered = [d for d in recent_docs if not d.cluster_id]
        if len(unclustered) >= 5:
            notifications.append({
                "type": "cluster_suggestion",
                "message": f"{len(unclustered)} recent docs aren't clustered. Organize them?",
                "action": "force_recluster"
            })
        
        # Pattern 3: Huge clusters
        large_clusters = find_large_clusters(user, threshold=50)
        for cluster in large_clusters:
            notifications.append({
                "type": "split_suggestion",
                "message": f"'{cluster.name}' has {cluster.doc_count} docs. Split it into sub-topics?",
                "action": "split_cluster",
                "cluster_id": cluster.id
            })
        
        return notifications
```

**Endpoint:**
```python
@router.get("/notifications")
async def get_smart_notifications(
    current_user: User = Depends(get_current_user)
):
    """Get AI-suggested actions based on recent activity."""
    engine = NotificationEngine()
    notifications = engine.analyze_recent_activity(current_user.username)
    return {"notifications": notifications}
```

**Why:** Proactive help. System becomes an assistant, not just a database.

---

### 6. Export to Obsidian/Notion/Roam

**What:** Let users export knowledge base to popular tools

**Formats:**

**Obsidian (Markdown vault):**
```python
@router.get("/export/obsidian")
async def export_to_obsidian(
    kb_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Export KB as Obsidian vault (zip of markdown files).
    
    Structure:
    - One .md file per document
    - Folders for clusters
    - [[wiki-links]] between related docs
    - Frontmatter with metadata
    """
    vault_structure = {
        "README.md": "# My Knowledge Base\n\nExported from SyncBoard",
        "clusters/": {}
    }
    
    for cluster in clusters:
        cluster_folder = f"clusters/{sanitize(cluster.name)}/"
        for doc in cluster.documents:
            # Create markdown file
            content = f"""---
title: {doc.title}
source: {doc.source_url}
ingested: {doc.ingested_at}
tags: {doc.concepts}
---

# {doc.title}

{doc.content}

## Related
{generate_wikilinks(doc.related_docs)}
"""
            vault_structure[f"{cluster_folder}{doc.id}.md"] = content
    
    # Zip it up
    zip_file = create_zip(vault_structure)
    return FileResponse(zip_file, filename="obsidian_vault.zip")
```

**Notion (via API):**
```python
@router.post("/export/notion")
async def export_to_notion(
    notion_token: str,
    kb_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Export KB to Notion workspace.
    
    Creates:
    - Database for documents
    - Pages for clusters
    - Linked database views
    """
    from notion_client import Client
    
    notion = Client(auth=notion_token)
    
    # Create database
    database = notion.databases.create(
        parent={"type": "page_id", "page_id": workspace_id},
        title=[{"type": "text", "text": {"content": "SyncBoard Knowledge Base"}}],
        properties={
            "Name": {"title": {}},
            "Source": {"url": {}},
            "Cluster": {"select": {}},
            "Concepts": {"multi_select": {}}
        }
    )
    
    # Add all docs as pages
    for doc in documents:
        notion.pages.create(
            parent={"database_id": database["id"]},
            properties={
                "Name": {"title": [{"text": {"content": doc.title}}]},
                "Source": {"url": doc.source_url},
                "Cluster": {"select": {"name": doc.cluster_name}},
                "Concepts": {"multi_select": [{"name": c} for c in doc.concepts]}
            },
            children=[{
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": doc.content}}]}
            }]
        )
    
    return {"message": f"Exported to Notion database", "url": database["url"]}
```

**Why:** Reduces lock-in fear. Users more likely to commit if they know they can leave.

---

## 🏗️ BIGGER VISION (Next Month)

### 7. Conversational Interface

**What:** Replace all the buttons with chat

**Instead of:**
- Click "What Can I Build"
- Click "Search"  
- Click "Generate"

**Just type:**
- "What do I know about Docker?"
- "Find all my Python examples"
- "What can I build with my FastAPI knowledge?"
- "Summarize the YouTube videos I uploaded this week"

**Implementation:**
```python
# New file: backend/conversational_interface.py
class ConversationalAgent:
    def __init__(self, user, vector_store, documents, metadata):
        self.user = user
        self.vector_store = vector_store
        self.documents = documents
        self.metadata = metadata
        self.conversation_history = []
    
    async def process_message(self, user_message: str):
        """
        Process user message and determine intent.
        
        Intents:
        - search: "find", "show me", "what do I have about"
        - summarize: "summarize", "what's the gist"
        - build: "what can I build", "project ideas"
        - analyze: "how much", "what's my knowledge of"
        - generate: "write", "create", "explain"
        """
        # Classify intent using small LLM call
        intent = await self.classify_intent(user_message)
        
        if intent == "search":
            results = self.vector_store.search(user_message, top_k=5)
            return self.format_search_results(results)
        
        elif intent == "build":
            suggestions = await self.generate_build_suggestions()
            return self.format_build_suggestions(suggestions)
        
        elif intent == "generate":
            response = await self.generate_with_rag(user_message)
            return response
        
        elif intent == "analyze":
            stats = self.analyze_knowledge(user_message)
            return self.format_stats(stats)
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now()
        })
```

**Frontend:**
Replace entire UI with chat window:
```html
<div id="chat-container">
    <div id="messages"></div>
    <input id="message-input" placeholder="Ask me anything about your knowledge...">
</div>
```

**Why:** Chat is the future. Buttons are the past. Make it conversational.

---

### 8. Source Citation

**What:** When AI answers, show which docs it used

**Example:**
```
User: "What's the best way to deploy FastAPI?"

AI: "Based on your notes, there are three approaches:

1. Docker (from 'FastAPI Deployment Guide' [View])
   - Containerize with uvicorn
   - Use multi-stage builds

2. Kubernetes (from 'Scaling FastAPI Apps' [View])
   - Auto-scaling with HPA
   - Health checks on /health

3. Serverless (from 'AWS Lambda FastAPI' [View])
   - Use Mangum adapter
   - Cold start considerations

[View all 3 source documents]"
```

**Implementation:**
```python
# Modify generate_with_rag in ai_generation_real.py
async def generate_with_rag(prompt, ...):
    # ... existing code to get relevant_docs ...
    
    # Build context with doc IDs
    context_with_ids = []
    for i, doc in enumerate(relevant_docs):
        context_with_ids.append({
            "doc_id": doc["doc_id"],
            "content": doc["content"],
            "relevance": doc["relevance"]
        })
    
    # Enhanced system prompt
    system_message = """You are an AI assistant helping users with their knowledge bank.

IMPORTANT: When you reference information from documents, cite them like this:
"According to Document 1, ..." or "[Source: Document 2]"

Documents are numbered in the context below."""
    
    # Generate response
    response = await client.chat.completions.create(...)
    
    # Return response WITH source document IDs
    return {
        "text": generated_text,
        "sources": [
            {
                "doc_id": doc["doc_id"],
                "title": get_doc_title(doc["doc_id"]),
                "relevance": doc["relevance"]
            }
            for doc in context_with_ids
        ]
    }
```

**Frontend:**
Show source docs as clickable pills below AI response.

**Why:** Trust. Users need to verify AI isn't hallucinating.

---

### 9. YouTube Channel Monitoring

**What:** Auto-ingest new videos from subscribed channels

**How:**
```python
# New table in db_models.py
class DBYouTubeSubscription(Base):
    __tablename__ = "youtube_subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.username"))
    channel_id = Column(String, nullable=False)
    channel_name = Column(String)
    last_checked = Column(DateTime)
    auto_ingest = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Background job (runs daily)
@celery_app.task
def check_youtube_subscriptions():
    """Check all YouTube subscriptions for new videos."""
    from yt_dlp import YoutubeDL
    
    subscriptions = get_all_subscriptions()
    
    for sub in subscriptions:
        # Get channel's recent videos
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with YoutubeDL(ydl_opts) as ydl:
            playlist_url = f"https://youtube.com/channel/{sub.channel_id}/videos"
            info = ydl.extract_info(playlist_url, download=False)
            
            for video in info['entries'][:5]:  # Last 5 videos
                video_url = f"https://youtube.com/watch?v={video['id']}"
                
                # Check if already ingested
                if not video_already_ingested(video_url):
                    # Queue for ingestion
                    process_youtube_upload.delay(
                        url=video_url,
                        username=sub.user_id
                    )
                    logger.info(f"Auto-ingesting {video['title']} for {sub.user_id}")
        
        # Update last_checked
        sub.last_checked = datetime.utcnow()
```

**Endpoint:**
```python
@router.post("/subscriptions/youtube")
async def subscribe_to_youtube_channel(
    channel_url: str,
    current_user: User = Depends(get_current_user)
):
    """Subscribe to a YouTube channel for auto-ingestion."""
    # Extract channel ID from URL
    # Create subscription
    # Return success
```

**Why:** Keeps knowledge base current. Set it and forget it.

---

### 10. Collaborative Knowledge Bases

**What:** Let teams share knowledge bases

**Features:**
- Invite users by email
- Permission levels (Owner, Editor, Viewer)
- Shared clusters
- Activity feed ("Sarah added 3 docs to 'Python Best Practices'")

**Database Changes:**
```python
# New table
class DBKnowledgeBasePermission(Base):
    __tablename__ = "kb_permissions"
    
    id = Column(Integer, primary_key=True)
    kb_id = Column(String, ForeignKey("knowledge_bases.id"))
    user_id = Column(String, ForeignKey("users.username"))
    role = Column(String)  # owner, editor, viewer
    invited_by = Column(String)
    invited_at = Column(DateTime)
    accepted_at = Column(DateTime)

# Activity feed
class DBKnowledgeBaseActivity(Base):
    __tablename__ = "kb_activity"
    
    id = Column(Integer, primary_key=True)
    kb_id = Column(String, ForeignKey("knowledge_bases.id"))
    user_id = Column(String)
    action = Column(String)  # "added_doc", "created_cluster", "invited_user"
    target_type = Column(String)  # "document", "cluster", "user"
    target_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Endpoints:**
```python
@router.post("/knowledge-bases/{kb_id}/invite")
async def invite_user_to_kb(
    kb_id: str,
    email: str,
    role: str,
    current_user: User = Depends(get_current_user)
):
    """Invite user to collaborate on knowledge base."""
    # Check if current user is owner
    # Send email invitation
    # Create pending permission
    pass

@router.get("/knowledge-bases/{kb_id}/activity")
async def get_kb_activity(
    kb_id: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Get recent activity in knowledge base."""
    # Check user has access
    # Return activity feed
    pass
```

**Why:** Moves from personal tool to team tool. That's where the money is.

---

## 💰 THE COMMERCIAL PLAY

If you wanted to actually SELL this:

### **Free Tier:**
- 100 documents max
- 5 clusters
- Basic search only
- Solo use only
- Community support

### **Pro Tier ($10/month):**
- Unlimited documents
- Unlimited clusters
- AI features (generate, build suggestions)
- Team sharing (up to 5 users)
- Priority processing
- Email support

### **Team Tier ($50/month):**
- Everything in Pro
- Up to 20 users
- Admin dashboard
- Usage analytics
- API access
- Custom integrations
- Priority support
- SSO (Google/Microsoft)

### **Enterprise (Custom):**
- Unlimited everything
- Self-hosted option
- Custom AI models
- Dedicated support
- SLA guarantees
- White-label option

---

## 🎯 MY HONEST RECOMMENDATION

**Don't try to build everything.** Pick ONE direction:

### **Option A: Make it Social**
Focus on #10 (Collaborative KBs) + Activity feeds + Sharing
- Like "GitHub for knowledge"
- Teams can build knowledge together
- Public/private knowledge bases
- Follow other users

### **Option B: Make it Conversational**
Focus on #7 (Chat interface) + #8 (Source citation)
- Kill all the buttons
- Pure chat with your knowledge
- "ChatGPT but it knows YOUR stuff"

### **Option C: Make it Specialized**
Pick ONE niche and dominate:
- **Developer knowledge:** Code snippets, docs, Stack Overflow answers
- **Research papers:** Academic research organization
- **Course notes:** Student knowledge management
- **Content creators:** Script ideas, research, content planning

### **Option D: Keep it Personal**
Just fix the build suggester filter and use it yourself.
You've got a working system - nothing wrong with that!

---

## 📝 IMPLEMENTATION PRIORITY

If I were you, I'd do these in order:

1. **Fix build suggester filter** (10 mins) - immediate UX win
2. **Add source citations** (2 hours) - builds trust in AI
3. **Document relationships** (4 hours) - makes exploration better
4. **Smart notifications** (6 hours) - makes system proactive
5. **Conversational interface** (2 days) - transforms the UX

Everything else is nice-to-have.

---

## 🤝 WORKING WITH "MAD BRO CLAUDE CODE"

When you chat with Claude Code about these features:

**Give him this file** - he'll understand the context

**Be specific:**
- ❌ "Add document relationships"
- ✅ "Implement the document relationships feature from FEATURE_ROADMAP.md section 4, starting with the auto-discovery function"

**Give him the file locations:**
- All the code examples above include file paths
- He can read your existing code to understand the patterns

**Test incrementally:**
- Build one feature at a time
- Run your test suite after each change
- You've got 473 passing tests - use them!

---

**Good luck pushing this beast further, Daz!** 🚀

You've built something real. Now make it legendary.
