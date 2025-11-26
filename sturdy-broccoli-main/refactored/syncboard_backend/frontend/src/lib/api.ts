// =============================================================================
// SyncBoard 3.0 - Complete API Client (120+ Endpoints)
// =============================================================================

import axios, { AxiosInstance, AxiosError } from 'axios';
import * as Types from '@/types/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      headers: { 'Content-Type': 'application/json' },
    });

    // Add auth token to requests
    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }
      return config;
    });

    // Handle errors globally
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          this.clearToken();
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }
        }
        throw error;
      }
    );

    // Load token from localStorage
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('token');
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('token', token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
    }
  }

  isAuthenticated() {
    return !!this.token;
  }

  // ==========================================================================
  // HEALTH
  // ==========================================================================
  async getHealth(): Promise<Types.HealthResponse> {
    const { data } = await this.client.get('/health');
    return data;
  }

  // ==========================================================================
  // AUTH
  // ==========================================================================
  async register(username: string, password: string): Promise<Types.User> {
    const { data } = await this.client.post('/users', { username, password });
    return data;
  }

  async login(username: string, password: string): Promise<Types.TokenResponse> {
    const { data } = await this.client.post('/token', { username, password });
    this.setToken(data.access_token);
    return data;
  }

  logout() {
    this.clearToken();
  }

  // ==========================================================================
  // UPLOADS
  // ==========================================================================
  async uploadText(content: string, title?: string, skill_level?: string): Promise<Types.UploadResponse> {
    const { data } = await this.client.post('/upload_text', { content, title, skill_level });
    return data;
  }

  async uploadUrl(url: string, title?: string): Promise<Types.UploadResponse> {
    const { data } = await this.client.post('/upload', { url, title });
    return data;
  }

  async uploadFile(file_base64: string, filename: string, skill_level?: string): Promise<Types.UploadResponse> {
    // Backend expects 'content' not 'file_base64'
    const { data } = await this.client.post('/upload_file', { content: file_base64, filename, skill_level });
    return data;
  }

  async uploadImage(image_base64: string, filename?: string, description?: string): Promise<Types.UploadResponse> {
    // Backend expects 'content' not 'image_base64'
    const { data } = await this.client.post('/upload_image', { content: image_base64, filename, description });
    return data;
  }

  async uploadBatch(files: { file_base64: string; filename: string }[]): Promise<Types.BatchUploadResponse> {
    // Backend expects 'content' not 'file_base64' in each file
    const filesWithContent = files.map(f => ({ content: f.file_base64, filename: f.filename }));
    const { data } = await this.client.post('/upload_batch', { files: filesWithContent });
    return data;
  }

  async uploadBatchUrls(urls: string[]): Promise<Types.BatchUploadResponse> {
    const { data } = await this.client.post('/upload_batch_urls', { urls });
    return data;
  }

  // ==========================================================================
  // SEARCH
  // ==========================================================================
  async search(params: {
    q: string;
    top_k?: number;
    cluster_id?: number;
    full_content?: boolean;
    source_type?: string;
    skill_level?: string;
    date_from?: string;
    date_to?: string;
  }): Promise<Types.SearchResponse> {
    const { data } = await this.client.get('/search_full', { params });
    return data;
  }

  async searchSummaries(q: string, top_k?: number): Promise<{ results: Types.SearchResult[] }> {
    const { data } = await this.client.get('/search/summaries', { params: { q, top_k } });
    return data;
  }

  async getSummaryStats(): Promise<{ total_summaries: number; average_length: number; coverage_percentage: number }> {
    const { data } = await this.client.get('/search/summaries/stats');
    return data;
  }

  // ==========================================================================
  // DOCUMENTS
  // ==========================================================================
  async getDocuments(): Promise<{ documents: Types.Document[]; total: number; knowledge_base_id: number }> {
    const { data } = await this.client.get('/documents');
    return data;
  }

  async getDocument(docId: number): Promise<Types.Document & { cluster: Types.Cluster }> {
    const { data } = await this.client.get(`/documents/${docId}`);
    return data;
  }

  async deleteDocument(docId: number): Promise<{ message: string; document_id: number }> {
    const { data } = await this.client.delete(`/documents/${docId}`);
    return data;
  }

  async updateDocumentMetadata(docId: number, metadata: Types.DocumentMetadata): Promise<{ message: string; updated_metadata: Types.DocumentMetadata }> {
    const { data } = await this.client.put(`/documents/${docId}/metadata`, metadata);
    return data;
  }

  async getDocumentSummaries(docId: number): Promise<{ summaries: { text: string; length: number; creation_date: string }[] }> {
    const { data } = await this.client.get(`/documents/${docId}/summaries`);
    return data;
  }

  async summarizeDocument(docId: number, summary_type?: string): Promise<{ summaries: { text: string; length: number }[]; job_id?: string }> {
    const { data } = await this.client.post(`/documents/${docId}/summarize`, { summary_type });
    return data;
  }

  // ==========================================================================
  // CLUSTERS
  // ==========================================================================
  async getClusters(): Promise<{ clusters: Types.Cluster[]; total: number; knowledge_base_id: number }> {
    const { data } = await this.client.get('/clusters');
    return data;
  }

  async updateCluster(clusterId: number, updates: { name?: string; skill_level?: string }): Promise<{ message: string; cluster: Types.Cluster }> {
    const { data } = await this.client.put(`/clusters/${clusterId}`, updates);
    return data;
  }

  async exportCluster(clusterId: number, format: 'json' | 'markdown' = 'json'): Promise<Blob> {
    const { data } = await this.client.get(`/export/cluster/${clusterId}`, { params: { format }, responseType: 'blob' });
    return data;
  }

  async exportAll(format: 'json' | 'markdown' = 'json'): Promise<Blob> {
    const { data } = await this.client.get('/export/all', { params: { format }, responseType: 'blob' });
    return data;
  }

  // ==========================================================================
  // BUILD SUGGESTIONS
  // ==========================================================================
  async whatCanIBuild(max_suggestions?: number, enable_quality_filter?: boolean): Promise<Types.BuildSuggestionsResponse> {
    const { data } = await this.client.post('/what_can_i_build', { max_suggestions, enable_quality_filter });
    return data;
  }

  async whatCanIBuildGoalDriven(max_suggestions?: number, enable_quality_filter?: boolean, goal_id?: number): Promise<Types.BuildSuggestionsResponse> {
    const { data } = await this.client.post('/what_can_i_build/goal-driven', { max_suggestions, enable_quality_filter, goal_id });
    return data;
  }

  async getIdeaSeeds(difficulty?: string, limit?: number): Promise<{ idea_seeds: Types.BuildSuggestion[] }> {
    const { data } = await this.client.get('/idea-seeds', { params: { difficulty, limit } });
    return data;
  }

  async generateIdeaSeeds(doc_id: number): Promise<{ idea_seeds: Types.BuildSuggestion[] }> {
    const { data } = await this.client.post('/idea-seeds/generate', { doc_id });
    return data;
  }

  async getCombinedIdeaSeeds(doc_ids: number[]): Promise<{ idea_seeds: Types.BuildSuggestion[] }> {
    const { data } = await this.client.get('/idea-seeds/combined', { params: { doc_ids } });
    return data;
  }

  async saveIdea(idea: {
    idea_seed_id?: number;
    custom_title?: string;
    custom_description?: string;
    custom_data?: any;
    notes?: string;
    status?: string;
  }): Promise<{ message: string; saved_idea: any }> {
    const { data } = await this.client.post('/ideas/save', null, {
      params: {
        idea_seed_id: idea.idea_seed_id,
        title: idea.custom_title,
        description: idea.custom_description,
        suggestion_data: idea.custom_data ? JSON.stringify(idea.custom_data) : undefined,
        notes: idea.notes
      }
    });
    return data;
  }

  async getSavedIdeas(status?: string, limit?: number): Promise<{ count: number; saved_ideas: any[] }> {
    const { data } = await this.client.get('/ideas/saved', { params: { status, limit } });
    return data;
  }

  async updateSavedIdea(savedId: number, updates: { status?: string; notes?: string }): Promise<any> {
    const { data } = await this.client.put(`/ideas/saved/${savedId}`, null, {
      params: { status: updates.status, notes: updates.notes }
    });
    return data;
  }

  async deleteSavedIdea(savedId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/ideas/saved/${savedId}`);
    return data;
  }

  async createMegaProject(ideaIds: number[], title?: string): Promise<{
    status: string;
    mega_project: {
      title: string;
      description: string;
      value_proposition: string;
      tech_stack: {
        languages: string[];
        frameworks: string[];
        databases: string[];
        tools: string[];
      };
      architecture: string;
      file_structure: string;
      starter_code: string;
      modules: Array<{
        name: string;
        purpose: string;
        files: string[];
        from_idea: string;
      }>;
      implementation_roadmap: Array<{
        phase: number;
        title: string;
        tasks: string[];
        estimated_hours: number;
      }>;
      learning_path: string[];
      complexity_level: string;
      total_effort_estimate: string;
      expected_outcomes: string[];
      potential_extensions: string[];
      source_ideas: Array<{ id: number; title: string }>;
      combined_skills: string[];
    };
  }> {
    const { data } = await this.client.post('/ideas/mega-project', null, {
      params: { idea_ids: ideaIds, title }
    });
    return data;
  }

  // ==========================================================================
  // ANALYTICS
  // ==========================================================================
  async getAnalytics(time_period?: number): Promise<Types.AnalyticsResponse> {
    const { data } = await this.client.get('/analytics', { params: { time_period } });
    return data;
  }

  // ==========================================================================
  // AI GENERATION
  // ==========================================================================
  async generate(req: Types.GenerateRequest): Promise<Types.GenerateResponse> {
    const { data } = await this.client.post('/generate', req);
    return data;
  }

  async generateEnhanced(req: Types.GenerateRequest & { retrieve_top_k?: number }): Promise<Types.GenerateResponse & { metadata: Record<string, unknown> }> {
    const { data } = await this.client.post('/generate/enhanced', req);
    return data;
  }

  // ==========================================================================
  // DUPLICATES
  // ==========================================================================
  async findDuplicates(threshold?: number, limit?: number): Promise<{ duplicate_groups: Types.DuplicateGroup[] }> {
    const { data } = await this.client.get('/duplicates', { params: { threshold, limit } });
    return data;
  }

  async compareDuplicates(doc_id1: number, doc_id2: number): Promise<{ doc_id1: number; doc_id2: number; similarity_score: number; content_comparison: { matches: string[]; differences: string[] } }> {
    const { data } = await this.client.get(`/duplicates/${doc_id1}/${doc_id2}`);
    return data;
  }

  async mergeDuplicates(keep_doc_id: number, delete_doc_ids: number[]): Promise<{ message: string; merged_count: number; deleted_count: number }> {
    const { data } = await this.client.post('/duplicates/merge', { keep_doc_id, delete_doc_ids });
    return data;
  }

  // ==========================================================================
  // TAGS
  // ==========================================================================
  async createTag(name: string, color?: string): Promise<Types.Tag> {
    const { data } = await this.client.post('/tags', { name, color });
    return data;
  }

  async getTags(): Promise<{ tags: Types.Tag[] }> {
    const { data } = await this.client.get('/tags');
    return data;
  }

  async addTagToDocument(docId: number, tagId: number): Promise<{ message: string }> {
    const { data } = await this.client.post(`/documents/${docId}/tags/${tagId}`);
    return data;
  }

  async removeTagFromDocument(docId: number, tagId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/documents/${docId}/tags/${tagId}`);
    return data;
  }

  async getDocumentTags(docId: number): Promise<{ tags: Types.Tag[] }> {
    const { data } = await this.client.get(`/documents/${docId}/tags`);
    return data;
  }

  async deleteTag(tagId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/tags/${tagId}`);
    return data;
  }

  // ==========================================================================
  // SAVED SEARCHES
  // ==========================================================================
  async saveSearch(name: string, query: string, filters?: Record<string, unknown>): Promise<Types.SavedSearch> {
    const { data } = await this.client.post('/saved-searches', { name, query, filters });
    return data;
  }

  async getSavedSearches(): Promise<{ saved_searches: Types.SavedSearch[] }> {
    const { data } = await this.client.get('/saved-searches');
    return data;
  }

  async useSavedSearch(searchId: number): Promise<{ query: string; filters: Record<string, unknown>; id: number }> {
    const { data } = await this.client.post(`/saved-searches/${searchId}/use`);
    return data;
  }

  async deleteSavedSearch(searchId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/saved-searches/${searchId}`);
    return data;
  }

  // ==========================================================================
  // RELATIONSHIPS
  // ==========================================================================
  async createRelationship(sourceDocId: number, targetDocId: number, relationship_type: string, strength?: number): Promise<Types.DocumentRelationship> {
    const { data } = await this.client.post(`/documents/${sourceDocId}/relationships`, { target_doc_id: targetDocId, relationship_type, strength });
    return data;
  }

  async getRelationships(docId: number, relationship_type?: string): Promise<{ relationships: Types.DocumentRelationship[] }> {
    const { data } = await this.client.get(`/documents/${docId}/relationships`, { params: { relationship_type } });
    return data;
  }

  async deleteRelationship(sourceDocId: number, targetDocId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/documents/${sourceDocId}/relationships/${targetDocId}`);
    return data;
  }

  async discoverRelatedDocuments(docId: number, top_k?: number, min_similarity?: number): Promise<{ doc_id: number; related_documents: { doc_id: number; similarity_score: number }[]; count: number }> {
    const { data } = await this.client.get(`/documents/${docId}/discover-related`, { params: { top_k, min_similarity } });
    return data;
  }

  // ==========================================================================
  // JOBS
  // ==========================================================================
  async getJobStatus(jobId: string): Promise<Types.JobStatus> {
    const { data } = await this.client.get(`/jobs/${jobId}/status`);
    return data;
  }

  async cancelJob(jobId: string): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/jobs/${jobId}`);
    return data;
  }

  async getJobs(limit?: number): Promise<{ jobs: Types.JobStatus[] }> {
    const { data } = await this.client.get('/jobs', { params: { limit } });
    return data;
  }

  // ==========================================================================
  // INTEGRATIONS
  // ==========================================================================
  getOAuthUrl(service: string): string {
    return `${API_BASE}/integrations/${service}/authorize`;
  }

  async getIntegrationStatus(): Promise<{ integrations: Record<string, Types.IntegrationStatus> }> {
    const { data } = await this.client.get('/integrations/status');
    return data;
  }

  async disconnectIntegration(service: string): Promise<{ message: string }> {
    const { data } = await this.client.post(`/integrations/${service}/disconnect`);
    return data;
  }

  async listCloudFiles(service: string, path?: string, limit?: number): Promise<{ files: Types.CloudFile[] }> {
    const { data } = await this.client.get(`/integrations/${service}/files`, { params: { path, limit } });
    return data;
  }

  async importCloudFile(service: string, file_path: string, folder_path?: string): Promise<{ document_id: number; title: string; import_status: string }> {
    const { data } = await this.client.post(`/integrations/${service}/import`, { file_path, folder_path });
    return data;
  }

  async getGithubRepos(org?: string): Promise<{ repos: { name: string; url: string; stars: number; description: string }[] }> {
    const { data } = await this.client.get('/integrations/github/repos', { params: { org } });
    return data;
  }

  // ==========================================================================
  // KNOWLEDGE BASES
  // ==========================================================================
  async getKnowledgeBases(): Promise<{ knowledge_bases: Types.KnowledgeBase[]; total: number }> {
    const { data } = await this.client.get('/knowledge-bases');
    return data;
  }

  async createKnowledgeBase(name: string, description?: string, is_default?: boolean): Promise<Types.KnowledgeBase> {
    const { data } = await this.client.post('/knowledge-bases', { name, description, is_default });
    return data;
  }

  async getKnowledgeBase(kbId: number): Promise<Types.KnowledgeBase> {
    const { data } = await this.client.get(`/knowledge-bases/${kbId}`);
    return data;
  }

  async updateKnowledgeBase(kbId: number, updates: { name?: string; description?: string; is_default?: boolean }): Promise<Types.KnowledgeBase> {
    const { data } = await this.client.patch(`/knowledge-bases/${kbId}`, updates);
    return data;
  }

  async deleteKnowledgeBase(kbId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/knowledge-bases/${kbId}`);
    return data;
  }

  async getKnowledgeBaseStats(kbId: number): Promise<{ total_documents: number; total_clusters: number; total_concepts: number; disk_usage_mb: number }> {
    const { data } = await this.client.get(`/knowledge-bases/${kbId}/stats`);
    return data;
  }

  // ==========================================================================
  // ADMIN
  // ==========================================================================
  async getChunkStatus(): Promise<{ total_documents: number; chunked_documents: number; pending_documents: number; failed_documents: number; total_chunks: number; chunks_with_embeddings: number }> {
    const { data } = await this.client.get('/admin/chunk-status');
    return data;
  }

  async backfillChunks(max_documents?: number, generate_embeddings?: boolean): Promise<{ processed: number; succeeded: number; failed: number; skipped: number; results: { doc_id: number; status: string; chunk_count: number }[] }> {
    const { data } = await this.client.post('/admin/backfill-chunks', { max_documents, generate_embeddings });
    return data;
  }

  // ==========================================================================
  // KNOWLEDGE GRAPH
  // ==========================================================================
  async getKnowledgeGraphStats(): Promise<{ knowledge_base_id: number; stats: Types.KnowledgeGraphStats }> {
    const { data } = await this.client.get('/knowledge-graph/stats');
    return data;
  }

  async buildKnowledgeGraph(): Promise<{ status: string; knowledge_base_id: number; stats: Types.KnowledgeGraphStats }> {
    const { data } = await this.client.post('/knowledge-graph/build');
    return data;
  }

  async getGraphRelated(docId: number, relationship_type?: string, min_strength?: number, limit?: number): Promise<{ doc_id: number; related_documents: { doc_id: number; relationship_type: string; strength: number }[] }> {
    const { data } = await this.client.get(`/knowledge-graph/related/${docId}`, { params: { relationship_type, min_strength, limit } });
    return data;
  }

  async getConcepts(limit?: number): Promise<{ concepts: Types.ConceptCloud[] }> {
    const { data } = await this.client.get('/knowledge-graph/concepts', { params: { limit } });
    return data;
  }

  async getTechnologies(limit?: number): Promise<{ technologies: { tech: string; frequency: number; documents: number[] }[] }> {
    const { data } = await this.client.get('/knowledge-graph/technologies', { params: { limit } });
    return data;
  }

  async findLearningPath(source_concept: string, target_concept: string): Promise<{ path: { concept: string; distance: number }[]; total_steps: number }> {
    const { data } = await this.client.get('/knowledge-graph/path', { params: { source_concept, target_concept } });
    return data;
  }

  async getDocumentsByConcept(concept: string, limit?: number): Promise<{ concept: string; documents: { doc_id: number; title: string; relevance: number }[] }> {
    const { data } = await this.client.get(`/knowledge-graph/by-concept/${encodeURIComponent(concept)}`, { params: { limit } });
    return data;
  }

  async getDocumentsByTech(technology: string, limit?: number): Promise<{ technology: string; documents: { doc_id: number; title: string; relevance: number }[] }> {
    const { data } = await this.client.get(`/knowledge-graph/by-tech/${encodeURIComponent(technology)}`, { params: { limit } });
    return data;
  }

  // ==========================================================================
  // PROJECT GOALS
  // ==========================================================================
  async getProjectGoals(): Promise<Types.ProjectGoal[]> {
    const { data } = await this.client.get('/project-goals');
    return data;
  }

  async getPrimaryGoal(): Promise<Types.ProjectGoal> {
    const { data } = await this.client.get('/project-goals/primary');
    return data;
  }

  async getProjectGoal(goalId: number): Promise<Types.ProjectGoal> {
    const { data } = await this.client.get(`/project-goals/${goalId}`);
    return data;
  }

  async createProjectGoal(goal_type: string, priority: number, constraints?: Record<string, unknown>): Promise<Types.ProjectGoal> {
    const { data } = await this.client.post('/project-goals', { goal_type, priority, constraints });
    return data;
  }

  async updateProjectGoal(goalId: number, updates: { goal_type?: string; priority?: number; constraints?: Record<string, unknown> }): Promise<Types.ProjectGoal> {
    const { data } = await this.client.put(`/project-goals/${goalId}`, updates);
    return data;
  }

  async deleteProjectGoal(goalId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/project-goals/${goalId}`);
    return data;
  }

  // ==========================================================================
  // PROJECT TRACKING
  // ==========================================================================
  async getProjects(status?: string, limit?: number, offset?: number): Promise<Types.ProjectAttempt[]> {
    const { data } = await this.client.get('/projects', { params: { status, limit, offset } });
    return data;
  }

  async getProjectStats(): Promise<Types.ProjectStats> {
    const { data } = await this.client.get('/projects/stats');
    return data;
  }

  async getProject(projectId: number): Promise<Types.ProjectAttempt> {
    const { data } = await this.client.get(`/projects/${projectId}`);
    return data;
  }

  async createProject(title: string, description: string, goal_id?: number): Promise<Types.ProjectAttempt> {
    const { data } = await this.client.post('/projects', { title, description, goal_id });
    return data;
  }

  async updateProject(projectId: number, updates: { title?: string; status?: string; time_spent_hours?: number; revenue_generated?: number }): Promise<Types.ProjectAttempt> {
    const { data } = await this.client.put(`/projects/${projectId}`, updates);
    return data;
  }

  async deleteProject(projectId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/projects/${projectId}`);
    return data;
  }

  // ==========================================================================
  // N8N WORKFLOWS
  // ==========================================================================
  async generateN8NWorkflow(task_description: string, available_integrations?: string[]): Promise<{ workflow_id: number; workflow: Record<string, unknown>; setup_instructions: string; required_credentials: string[]; testing_steps: string[]; potential_improvements: string[]; download_url: string }> {
    const { data } = await this.client.post('/n8n-workflows/generate', { task_description, available_integrations });
    return data;
  }

  async getN8NWorkflows(limit?: number, offset?: number): Promise<Types.N8NWorkflow[]> {
    const { data } = await this.client.get('/n8n-workflows', { params: { limit, offset } });
    return data;
  }

  async getN8NWorkflow(workflowId: number): Promise<Types.N8NWorkflow> {
    const { data } = await this.client.get(`/n8n-workflows/${workflowId}`);
    return data;
  }

  async updateN8NWorkflow(workflowId: number, updates: { title?: string; description?: string }): Promise<Types.N8NWorkflow> {
    const { data } = await this.client.put(`/n8n-workflows/${workflowId}`, updates);
    return data;
  }

  async deleteN8NWorkflow(workflowId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/n8n-workflows/${workflowId}`);
    return data;
  }

  getN8NWorkflowDownloadUrl(workflowId: number): string {
    return `${API_BASE}/n8n-workflows/${workflowId}/download`;
  }

  // ==========================================================================
  // GENERATED CODE
  // ==========================================================================
  async getGeneratedCode(project_id?: number, language?: string, generation_type?: string, limit?: number, offset?: number): Promise<Types.GeneratedCode[]> {
    const { data } = await this.client.get('/generated-code', { params: { project_id, language, generation_type, limit, offset } });
    return data;
  }

  async getGeneratedCodeFile(codeId: number): Promise<Types.GeneratedCode> {
    const { data } = await this.client.get(`/generated-code/${codeId}`);
    return data;
  }

  getCodeDownloadUrl(codeId: number): string {
    return `${API_BASE}/generated-code/${codeId}/download`;
  }

  async getProjectCodeFiles(projectId: number): Promise<Types.GeneratedCode[]> {
    const { data } = await this.client.get(`/generated-code/project/${projectId}/files`);
    return data;
  }

  getProjectZipUrl(projectId: number): string {
    return `${API_BASE}/generated-code/project/${projectId}/zip`;
  }

  // ==========================================================================
  // KNOWLEDGE TOOLS
  // ==========================================================================
  async analyzeKnowledgeGaps(): Promise<Types.GapAnalysisResponse> {
    const { data } = await this.client.get('/knowledge/gaps');
    return data;
  }

  async generateFlashcards(docId: number, num_cards?: number, difficulty_mix?: string): Promise<{ flashcards: Types.Flashcard[]; cards_generated: number; doc_id: number }> {
    const { data } = await this.client.post(`/knowledge/flashcards/${docId}`, { num_cards, difficulty_mix });
    return data;
  }

  async getWeeklyDigest(days?: number): Promise<Types.WeeklyDigest & { status: string; period: { start: string; end: string; days: number } }> {
    const { data } = await this.client.get('/knowledge/digest', { params: { days } });
    return data;
  }

  async optimizeLearningPath(goal: string): Promise<Types.LearningPath & { status: string }> {
    const { data } = await this.client.post('/knowledge/learning-path', { goal });
    return data;
  }

  async scoreDocumentQuality(docId: number): Promise<{ status: string; doc_id: number; scores: { information_density: number; actionability: number; currency: number; uniqueness: number; overall: number }; key_excerpts: string[]; sections_to_skip: string[]; missing_context: string[] }> {
    const { data } = await this.client.get(`/knowledge/quality/${docId}`);
    return data;
  }

  async knowledgeChat(query: string, conversation_history?: { user: string; assistant: string }[]): Promise<{ status: string; response: string; follow_ups?: string[] }> {
    const { data } = await this.client.post('/knowledge/chat', { query, conversation_history });
    return data;
  }

  // Backend returns files as array [{filename, content, purpose}] - frontend transforms it
  async generateCodeFromKB(project_type?: string, language?: string): Promise<{
    status: string;
    files?: Array<{ filename: string; content: string; purpose?: string }> | Record<string, string>;
    concepts_demonstrated?: string[];
    concepts_used?: string[];
    setup_instructions?: string | string[];
    project_name?: string;
    description?: string;
    run_command?: string;
    next_steps?: string[];
  }> {
    const { data } = await this.client.post('/knowledge/generate-code', { project_type, language });
    return data;
  }

  async compareDocuments(doc_a_id: number, doc_b_id: number): Promise<Types.DocumentComparison & { status: string }> {
    const { data } = await this.client.post('/knowledge/compare', { doc_a_id, doc_b_id });
    return data;
  }

  async explainELI5(topic: string): Promise<{ status: string; simple_explanation: string; analogy?: string; why_it_matters?: string; simple_example?: string; learn_next?: string[] }> {
    const { data } = await this.client.post('/knowledge/eli5', { topic });
    return data;
  }

  async generateInterviewPrep(role?: string, level?: string): Promise<Types.InterviewPrep & { status: string; topics_covered: string[] }> {
    const { data } = await this.client.post('/knowledge/interview-prep', { role, level });
    return data;
  }

  async debugError(error_message: string, code_snippet?: string, context?: string): Promise<Types.DebugResult & { status: string }> {
    const { data } = await this.client.post('/knowledge/debug', { error_message, code_snippet, context });
    return data;
  }

  async getKnowledgeToolsStatus(): Promise<{ status: string; services_available: boolean; features: Record<string, boolean>; endpoints: string[] }> {
    const { data } = await this.client.get('/knowledge/status');
    return data;
  }

  // ==========================================================================
  // USAGE & BILLING
  // ==========================================================================
  async getUsage(): Promise<Types.UsageResponse> {
    const { data } = await this.client.get('/usage');
    return data;
  }

  async getUsageHistory(months?: number): Promise<Types.UsageHistoryRecord[]> {
    const { data } = await this.client.get('/usage/history', { params: { months } });
    return data;
  }

  async getSubscription(): Promise<Types.SubscriptionResponse> {
    const { data } = await this.client.get('/usage/subscription');
    return data;
  }

  async upgradeSubscription(plan: string): Promise<{ message: string; plan: string; limits: Record<string, unknown> }> {
    const { data } = await this.client.post('/usage/subscription/upgrade', { plan });
    return data;
  }

  async getPlans(): Promise<Types.PlanResponse[]> {
    const { data } = await this.client.get('/usage/plans');
    return data;
  }

  // ==========================================================================
  // TEAMS
  // ==========================================================================
  async createTeam(name: string, description?: string): Promise<Types.Team> {
    const { data } = await this.client.post('/teams', { name, description });
    return data;
  }

  async getTeams(): Promise<Types.Team[]> {
    const { data } = await this.client.get('/teams');
    return data;
  }

  async getTeam(teamId: number): Promise<Types.Team> {
    const { data } = await this.client.get(`/teams/${teamId}`);
    return data;
  }

  async updateTeam(teamId: number, updates: { name?: string; description?: string }): Promise<Types.Team> {
    const { data } = await this.client.patch(`/teams/${teamId}`, updates);
    return data;
  }

  async deleteTeam(teamId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/teams/${teamId}`);
    return data;
  }

  async getTeamMembers(teamId: number): Promise<Types.TeamMember[]> {
    const { data } = await this.client.get(`/teams/${teamId}/members`);
    return data;
  }

  async updateTeamMember(teamId: number, username: string, updates: { role?: string; can_invite?: boolean; can_edit_docs?: boolean; can_delete_docs?: boolean }): Promise<Types.TeamMember> {
    const { data } = await this.client.patch(`/teams/${teamId}/members/${username}`, updates);
    return data;
  }

  async removeTeamMember(teamId: number, username: string): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/teams/${teamId}/members/${username}`);
    return data;
  }

  async createTeamInvitation(teamId: number, email: string, role?: string): Promise<Types.TeamInvitation> {
    const { data } = await this.client.post(`/teams/${teamId}/invitations`, { email, role });
    return data;
  }

  async getTeamInvitations(teamId: number): Promise<Types.TeamInvitation[]> {
    const { data } = await this.client.get(`/teams/${teamId}/invitations`);
    return data;
  }

  async cancelTeamInvitation(teamId: number, invitationId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/teams/${teamId}/invitations/${invitationId}`);
    return data;
  }

  async acceptTeamInvitation(token: string): Promise<{ message: string; team_id: number; team_name: string }> {
    const { data } = await this.client.post(`/teams/invitations/${token}/accept`);
    return data;
  }

  async getTeamActivity(teamId: number, limit?: number): Promise<Types.TeamActivity[]> {
    const { data } = await this.client.get(`/teams/${teamId}/activity`, { params: { limit } });
    return data;
  }

  async linkKnowledgeBaseToTeam(teamId: number, kbId: number, permission?: string): Promise<{ message: string }> {
    const { data } = await this.client.post(`/teams/${teamId}/knowledge-bases`, { knowledge_base_id: kbId, permission });
    return data;
  }

  async getTeamKnowledgeBases(teamId: number): Promise<{ knowledge_base_id: number; name: string; permission: string }[]> {
    const { data } = await this.client.get(`/teams/${teamId}/knowledge-bases`);
    return data;
  }

  async unlinkKnowledgeBaseFromTeam(teamId: number, kbId: number): Promise<{ message: string }> {
    const { data } = await this.client.delete(`/teams/${teamId}/knowledge-bases/${kbId}`);
    return data;
  }

  // ==========================================================================
  // AGENTIC LEARNING - FEEDBACK & VALIDATION (Phase A/B/C)
  // ==========================================================================

  /**
   * Get validation prompts for low-confidence AI decisions
   */
  async getValidationPrompts(limit: number = 10): Promise<Types.ValidationPromptsResponse> {
    const { data } = await this.client.get('/feedback/validation-prompts', { params: { limit } });
    return data;
  }

  /**
   * Submit user feedback for an AI decision
   */
  async submitFeedback(request: Types.SubmitFeedbackRequest): Promise<Types.UserFeedback> {
    const { data } = await this.client.post('/feedback/submit', request);
    return data;
  }

  /**
   * Get all low-confidence decisions that need validation
   */
  async getLowConfidenceDecisions(limit: number = 20): Promise<Types.AIDecision[]> {
    const { data } = await this.client.get('/feedback/low-confidence-decisions', { params: { limit } });
    return data;
  }

  /**
   * Get accuracy metrics showing how AI is improving
   */
  async getAccuracyMetrics(): Promise<Types.AccuracyMetrics> {
    const { data } = await this.client.get('/feedback/accuracy-metrics');
    return data;
  }

  /**
   * Get AI decision history for a specific document
   */
  async getDecisionHistory(documentId: number): Promise<Types.AIDecision[]> {
    const { data } = await this.client.get(`/feedback/decisions/document/${documentId}`);
    return data;
  }

  /**
   * Get all user feedback submitted
   */
  async getUserFeedback(limit: number = 50): Promise<Types.UserFeedback[]> {
    const { data } = await this.client.get('/feedback/user-feedback', { params: { limit } });
    return data;
  }

  // ==========================================================================
  // AUTONOMOUS AGENTS (Learning Agent + Maverick)
  // ==========================================================================

  /**
   * Get combined overview of all agents
   */
  async getAgentsOverview(): Promise<{
    learning_agent: {
      role: string;
      description: string;
      status: string;
      mode: string;
      current_strategy: string;
      total_observations: number;
      total_actions: number;
      autonomous_rules_created: number;
      accuracy_trend: string;
    };
    maverick_agent: {
      role: string;
      description: string;
      mood: string;
      curiosity: number;
      confidence: number;
      hypotheses_proposed: number;
      hypotheses_validated: number;
      hypotheses_applied: number;
    };
    collaboration: {
      description: string;
      maverick_hypotheses: { proposed: number; validated: number; applied: number };
      active_tests: number;
      recent_insights: string[];
      expertise: Record<string, number>;
    };
  }> {
    const { data } = await this.client.get('/learning/agents/overview');
    return data;
  }

  /**
   * Get Learning Agent status
   */
  async getLearningAgentStatus(): Promise<{
    is_autonomous: boolean;
    status: string;
    mode: string;
    current_strategy: string;
    total_observations: number;
    total_actions: number;
    autonomous_rules_created: number;
    autonomous_decisions: number;
    last_observation: any;
    last_action: any;
    accuracy_history: Array<{ accuracy: number; sample_size: number; timestamp: string }>;
  }> {
    const { data } = await this.client.get('/learning/agent/status');
    return data;
  }

  /**
   * Get autonomous decisions made by the agent
   */
  async getAgentDecisions(limit: number = 20): Promise<{
    count: number;
    autonomous_decisions: Array<{
      id: number;
      type: string;
      condition: any;
      action: any;
      confidence: number;
      times_applied: number;
      times_overridden: number;
      active: boolean;
      created_at: string;
      accuracy: number | null;
    }>;
  }> {
    const { data } = await this.client.get('/learning/agent/decisions', { params: { limit } });
    return data;
  }

  /**
   * Manually trigger a Learning Agent task
   */
  async triggerLearningAgentTask(taskName: string): Promise<{ message: string; task_id: string }> {
    const { data } = await this.client.post(`/learning/agent/trigger/${taskName}`);
    return data;
  }

  /**
   * Get Maverick Agent status
   */
  async getMaverickStatus(): Promise<{
    agent: string;
    tagline: string;
    mood: string;
    curiosity: number;
    confidence: number;
    hypotheses_proposed: number;
    hypotheses_tested: number;
    hypotheses_validated: number;
    hypotheses_applied: number;
    expertise: Record<string, number>;
  }> {
    const { data } = await this.client.get('/learning/maverick/status');
    return data;
  }

  /**
   * Get Maverick's hypotheses
   */
  async getMaverickHypotheses(): Promise<{
    hypotheses_proposed: number;
    hypotheses_tested: number;
    hypotheses_validated: number;
    hypotheses_applied: number;
    pending: Array<{
      id: string;
      category: string;
      description: string;
      target: string;
      reasoning: string;
      expected_improvement: string;
      created_at: string;
    }>;
    active_tests: Array<{
      id: string;
      category: string;
      description: string;
      target: string;
      test_start: string;
      baseline_metrics: any;
    }>;
    recent_results: Array<{
      id: string;
      category: string;
      description: string;
      status: string;
      improvement_score: number;
    }>;
  }> {
    const { data } = await this.client.get('/learning/maverick/hypotheses');
    return data;
  }

  /**
   * Get Maverick's learning insights
   */
  async getMaverickInsights(): Promise<{
    total_insights: number;
    insights: Array<{
      insight: string;
      category: string;
      confidence: number;
      discovered_at: string;
    }>;
    effective_strategies: Record<string, number>;
    expertise: Record<string, number>;
  }> {
    const { data } = await this.client.get('/learning/maverick/insights');
    return data;
  }

  /**
   * Get Maverick's activity log
   */
  async getMaverickActivity(): Promise<{
    mood: string;
    curiosity: number;
    confidence: number;
    recent_activity: string[];
    improvement_history: Array<{ timestamp: string; action: string; result: string }>;
  }> {
    const { data } = await this.client.get('/learning/maverick/activity');
    return data;
  }

  /**
   * Trigger a Maverick task
   */
  async triggerMaverickTask(taskName: string): Promise<{ message: string; task_id: string; maverick_says: string }> {
    const { data } = await this.client.post(`/learning/maverick/trigger/${taskName}`);
    return data;
  }

  /**
   * Get learned rules
   */
  async getLearnedRules(ruleType?: string, includeInactive?: boolean): Promise<{
    count: number;
    rules: Array<{
      id: number;
      type: string;
      condition: any;
      action: any;
      confidence: number;
      times_applied: number;
      times_overridden: number;
      active: boolean;
      created_at: string;
    }>;
  }> {
    const { data } = await this.client.get('/learning/rules', {
      params: { rule_type: ruleType, include_inactive: includeInactive }
    });
    return data;
  }

  /**
   * Get concept vocabulary
   */
  async getVocabulary(): Promise<{
    count: number;
    vocabulary: Array<{
      id: number;
      canonical_name: string;
      category: string;
      variants: string[];
      always_include: boolean;
      never_include: boolean;
      times_seen: number;
      times_kept: number;
      times_removed: number;
    }>;
  }> {
    const { data } = await this.client.get('/learning/vocabulary');
    return data;
  }

  // Generic request methods for flexibility
  async get<T = unknown>(path: string, params?: Record<string, unknown>): Promise<T> {
    const { data } = await this.client.get(path, { params });
    return data;
  }

  async post<T = unknown>(path: string, body?: Record<string, unknown>): Promise<T> {
    const { data } = await this.client.post(path, body);
    return data;
  }

  async put<T = unknown>(path: string, body?: Record<string, unknown>): Promise<T> {
    const { data } = await this.client.put(path, body);
    return data;
  }

  async patch<T = unknown>(path: string, body?: Record<string, unknown>): Promise<T> {
    const { data } = await this.client.patch(path, body);
    return data;
  }

  async delete<T = unknown>(path: string): Promise<T> {
    const { data } = await this.client.delete(path);
    return data;
  }
}

// Export singleton instance
export const api = new ApiClient();
export default api;
