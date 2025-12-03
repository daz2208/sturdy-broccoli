// =============================================================================
// SyncBoard 3.0 - Complete API Types
// =============================================================================

// Auth
export interface User {
  username: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
}

// Documents
export interface Document {
  id: number;
  title: string;
  content?: string;
  source_type: string;
  ingested_at: string;
  chunking_status: string;
  cluster_id: number | null;
  primary_topic?: string;
  skill_level?: string;
  knowledge_base_id?: string;  // UUID string from backend
}

export interface DocumentMetadata {
  title?: string;
  cluster_id?: number;
  skill_level?: string;
  primary_topic?: string;
}

export interface Concept {
  name: string;
  frequency: number;
}

// Clusters
export interface Cluster {
  id: number;
  name: string;
  doc_ids?: number[];
  concepts?: string[];
  primary_concepts?: string[];
  skill_level?: string;
}

// Upload
export interface UploadResponse {
  document_id: number;
  cluster_id: number;
  concepts: Concept[];
  title: string;
  source_type: string;
  primary_topic?: string;
  job_id?: string;  // For async/Celery processing
}

export interface BatchUploadResponse {
  documents: UploadResponse[];
  total_uploaded: number;
  failed: number;
}

// Search
export interface SearchResult {
  doc_id: number;
  title: string;
  content?: string;
  snippet?: string;
  similarity_score: number;
  source_type: string;
  cluster_id: number;
  metadata?: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResult[];
  grouped_by_cluster?: Record<string, SearchResult[]>;
}

// Build Suggestions
// Content Generation
export interface Industry {
  id: string;
  name: string;
  description: string;
  style?: string;
  citation_style?: string;
}

export interface ContentTemplate {
  name: string;
  description: string;
  type: string;
}

export interface IndustryProfile {
  industry: Industry;
  templates: ContentTemplate[];
  categories: Array<{ name: string; description: string }>;
  skill_levels: string[];
}

export interface IndustryDetectionRequest {
  text: string;
}

export interface IndustryDetectionResponse {
  detected_industry: string;
  confidence: 'high' | 'medium' | 'low';
  available_templates: ContentTemplate[];
}

export interface ContentGenerationRequest {
  template_name: string;
  topic?: string;
  cluster_ids?: number[];
  doc_ids?: string[];
  target_length?: 'short' | 'medium' | 'long';
  include_citations?: boolean;
  skill_level?: string;
}

export interface ContentSection {
  title: string;
  content: string;
  citations?: string[];
}

export interface ContentGenerationResponse {
  status: string;
  title: string;
  sections: ContentSection[];
  metadata: {
    template_used: string;
    industry: string;
    word_count: number;
    sources_used: number;
    generated_at: string;
  };
}

export interface SetKBIndustryRequest {
  industry: string;
}

export interface BuildSuggestion {
  title: string;
  description: string;
  feasibility: string;
  effort_estimate: string;
  complexity_level?: string;
  required_skills: string[];
  missing_knowledge?: string[];
  relevant_clusters?: number[];
  starter_steps?: string[];
  file_structure?: string;
  starter_code?: string;
  learning_path?: string[];
  recommended_resources?: string[];
  expected_outcomes?: string[];
  troubleshooting_tips?: string[];
  knowledge_coverage?: string;
  // Legacy fields for backward compatibility
  estimated_effort?: string;
  market_potential?: string;
  difficulty?: string;
  tech_stack?: string[];
}

export interface BuildSuggestionsResponse {
  suggestions: BuildSuggestion[];
  knowledge_summary: {
    total_docs: number;
    total_clusters: number;
    clusters: string[];
  };
}

export interface MarketValidationRequest {
  project_title: string;
  project_description: string;
  target_market?: string;
}

export interface MarketValidationResponse {
  id: number;
  user_id: string;
  market_size_estimate: string;
  competition_level: string;
  competitors: string[];
  unique_advantage: string;
  potential_revenue_estimate?: string;
  validation_sources: string[];
  recommendation: string;
  reasoning: string;
  confidence_score: number;
  created_at: string;
}

export interface QuickIdea {
  id: number;
  title: string;
  description: string;
  difficulty: string;
  feasibility: string | null;
  effort_estimate: string | null;
  dependencies: string[] | null;
  source_document: {
    id: string | null;
    filename: string | null;
    source_type: string | null;
  };
  created_at: string | null;
}

// Analytics
export interface AnalyticsOverview {
  total_docs: number;
  clusters: number;
  concepts: number;
}

export interface AnalyticsResponse {
  overview: AnalyticsOverview;
  timeseries: { date: string; count: number }[];
  distributions: {
    by_source: Record<string, number>;
    by_skill_level: Record<string, number>;
  };
  top_concepts: { concept: string; count: number }[];
  recent_activity: { action: string; timestamp: string; details: string }[];
}

// AI Generation
export interface GenerateRequest {
  prompt: string;
  model?: string;
  use_chunks?: boolean;
}

export interface GenerateResponse {
  response: string;
  citations: { source: string; doc_id: number; content: string }[];
}

// Duplicates
export interface DuplicateDoc {
  doc_id: number;
  similarity: number;
  title?: string;
  source_type?: string;
  source_url?: string;
  filename?: string;
  skill_level?: string;
  cluster_id?: number;
  created_at?: string;
}

export interface DuplicateGroup {
  primary_doc: DuplicateDoc;
  duplicates: DuplicateDoc[];
  group_size: number;
}

// Tags
export interface Tag {
  id: number;
  name: string;
  color: string;
  usage_count: number;
}

// Saved Searches
export interface SavedSearch {
  id: number;
  name: string;
  query: string;
  filters?: Record<string, unknown>;
  usage_count: number;
  last_used?: string;
}

// Relationships
export interface DocumentRelationship {
  target_doc_id: number;
  relationship_type: string;
  strength: number;
  target_metadata?: Record<string, unknown>;
}

// Jobs
export interface JobStatus {
  job_id: string;
  status: 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED';
  progress?: number;
  current_step?: string;
  message?: string;
  error?: string;
}

// Integrations
export interface IntegrationStatus {
  connected: boolean;
  last_connected?: string;
  user?: string;
}

export interface CloudFile {
  name: string;
  path: string;
  modified: string;
  size: number;
  type: 'file' | 'folder';
}

// Knowledge Bases
export interface KnowledgeBase {
  id: string;  // UUID string from backend
  name: string;
  description?: string;
  owner_username: string;
  is_default: boolean;
  document_count: number;
  created_at: string;
  updated_at?: string;
}

// Knowledge Graph
export interface KnowledgeGraphStats {
  total_documents: number;
  total_relationships: number;
  unique_concepts: number;
  unique_technologies: number;
}

export interface ConceptCloud {
  concept: string;
  frequency: number;
  relationships?: string[];
}

// Project Goals
export interface ProjectGoal {
  id: number;
  user_id: number;
  goal_type: string;
  priority: number;
  constraints?: Record<string, unknown>;
  created_at: string;
}

// Project Tracking
export interface ProjectAttempt {
  id: number;
  title: string;
  description: string;
  status: 'planned' | 'in_progress' | 'completed' | 'abandoned';
  created_at: string;
  completed_at?: string;
  time_spent_hours?: number;
  revenue_generated?: number;
  learnings?: string;
}

export interface ProjectStats {
  total_projects: number;
  completed: number;
  in_progress: number;
  abandoned: number;
  planned: number;
  completion_rate: number;
  average_time_hours: number;
  total_revenue: number;
}

// N8N Workflows
export interface N8NWorkflow {
  id: number;
  title: string;
  description: string;
  workflow_json: Record<string, unknown>;
  task_description?: string;
  trigger_type?: string;
  estimated_complexity?: string;
  created_at: string;
}

// Generated Code
export interface GeneratedCode {
  id: number;
  filename: string;
  language: string;
  code_content: string;
  generation_type: string;
  project_attempt_id?: number;
  description?: string;
  dependencies?: string[];
  setup_instructions?: string;
  created_at: string;
}

export interface StoreCodeRequest {
  project_id?: number;
  generation_type?: string;
  language?: string;
  filename: string;
  code_content: string;
  description?: string;
  dependencies?: string[];
  setup_instructions?: string;
}

export interface StoreBatchCodeRequest {
  project_id: number;
  files: Record<string, string>; // filename -> content mapping
}

// Admin
export interface LLMProviderStatus {
  provider: string;
  status: string;
  details: Record<string, any>;
}

export interface LLMProviderTestResult {
  status: string;
  provider: string;
  response: string;
}

export interface ReprocessDocumentResult {
  doc_id: number;
  status: string;
  chunks: number;
  embeddings: number;
}

// Knowledge Tools
export interface KnowledgeGap {
  area: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  suggested_topics: string[];
  learning_priority: number;
}

export interface GapAnalysisResponse {
  total_documents: number;
  total_concepts: number;
  inferred_goal?: string;
  strongest_areas: string[];
  gaps: KnowledgeGap[];
  shallow_areas: string[];
  recommended_learning_path: string[];
}

export interface Flashcard {
  front: string;
  back: string;
  difficulty: 'easy' | 'medium' | 'hard';
  concept: string;
  source_section?: string;
}

export interface WeeklyDigest {
  period_start: string;
  period_end: string;
  documents_added: number;
  executive_summary: string;
  new_concepts: string[];
  skills_improved: string[];
  focus_suggestions: string[];
  quick_wins: string[];
}

export interface LearningPath {
  goal: string;
  total_documents: number;
  estimated_hours: number;
  ordered_docs: {
    doc_id: number;
    title: string;
    // Frontend field names
    time_estimate?: string;
    reason?: string;
    // Backend field names
    time_estimate_minutes?: number;
    why_this_order?: string;
    checkpoint?: string;
    order?: number;
  }[];
  skip_list: string[] | number[];
  external_resources: string[];
}

export interface DocumentQuality {
  doc_id: number;
  information_density: number;
  actionability: number;
  currency: number;
  uniqueness: number;
  overall_score: number;
  key_excerpts: string[];
  sections_to_skip: string[];
  missing_context: string[];
}

export interface DocumentComparison {
  doc_a_id: number;
  doc_b_id: number;
  overlapping_concepts: string[];
  contradictions: string[];
  complementary_info: string[];
  more_authoritative?: string;
  recommended_order?: string;
  synthesis?: string;
}

export interface InterviewQuestion {
  question: string;
  answer?: string;
  guidance?: string;
  approach?: string;
  trap?: string;
}

export interface InterviewPrep {
  topics: string[];
  behavioral_questions: InterviewQuestion[];
  technical_questions: InterviewQuestion[];
  system_design_questions: InterviewQuestion[];
  gotcha_questions: InterviewQuestion[];
  study_recommendations: string[];
}

export interface DebugResult {
  error_message: string;
  likely_cause: string;
  step_by_step_fix: string[];
  explanation: string;
  prevention_tips: string[];
  related_docs: { doc_id: number; title?: string; relevance?: number }[];
  code_suggestion?: string;
  confidence: number;
}

// Health
export interface HealthResponse {
  status: string;
  timestamp: string;
  statistics: {
    documents: number;
    clusters: number;
    users: number;
    vector_store_size: number;
  };
  dependencies: {
    disk_space_gb: number;
    disk_healthy: boolean;
    storage_file_mb: number;
    openai_configured: boolean;
    database: boolean;
  };
}

// Usage & Billing
export interface UsageResponse {
  period_start: string;
  period_end: string;
  api_calls: number;
  documents_uploaded: number;
  ai_requests: number;
  storage_bytes: number;
  search_queries: number;
  build_suggestions: number;
  limits: {
    api_calls_per_minute: number;
    api_calls_per_day: number;
    documents_per_month: number;
    ai_requests_per_day: number;
    storage_mb: number;
    knowledge_bases: number;
    team_members: number;
    [key: string]: number;
  };
  usage_percentage: {
    api_calls: number;
    documents: number;
    ai_requests: number;
    storage: number;
    [key: string]: number;
  };
}

export interface UsageHistoryRecord {
  period: string;
  api_calls: number;
  documents_uploaded: number;
  ai_requests: number;
  storage_bytes: number;
  search_queries: number;
}

export interface SubscriptionResponse {
  plan: string;
  status: string;
  started_at: string;
  expires_at: string | null;
  trial_ends_at: string | null;
  limits: Record<string, unknown>;
}

export interface PlanResponse {
  id: string;
  name: string;
  price_monthly: number;
  limits: {
    api_calls_per_minute: number;
    api_calls_per_day: number;
    documents_per_month: number;
    ai_requests_per_day: number;
    storage_mb: number;
    knowledge_bases: number;
    team_members: number;
    [key: string]: number;
  };
  features: string[];
}

// Teams
export interface Team {
  id: number;
  name: string;
  slug: string;
  description?: string;
  owner_username: string;
  is_public: boolean;
  member_count: number;
  created_at: string;
  updated_at?: string;
}

export interface TeamMember {
  id: number;
  team_id: number;
  username: string;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  can_invite: boolean;
  can_edit_docs: boolean;
  can_delete_docs: boolean;
  can_manage_kb: boolean;
  joined_at: string;
}

export interface TeamInvitation {
  id: number;
  team_id: number;
  email: string;
  token: string;
  role: string;
  invited_by: string;
  status: 'pending' | 'accepted' | 'expired' | 'cancelled';
  created_at: string;
  expires_at: string;
}

export interface TeamActivity {
  id: number;
  team_id: number;
  username: string;
  action: string;
  entity_type: string;
  entity_id?: number;
  details?: Record<string, unknown>;
  created_at: string;
}

// =============================================================================
// Agentic Learning System (Phase A/B/C)
// =============================================================================

export interface AIDecision {
  id: number;
  decision_type: string;
  username: string;
  knowledge_base_id: string | null;
  document_id: number | null;
  cluster_id: number | null;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  confidence_score: number;
  model_name: string | null;
  model_version: string | null;
  validated: boolean;
  validation_result: string | null;
  validation_timestamp: string | null;
  created_at: string;
}

export interface UserFeedback {
  id: number;
  feedback_type: string;
  username: string;
  knowledge_base_id: string | null;
  document_id: number | null;
  ai_decision_id: number | null;
  original_value: Record<string, unknown> | null;
  new_value: Record<string, unknown>;
  context: Record<string, unknown> | null;
  user_reasoning: string | null;
  processed: boolean;
  processed_at: string | null;
  improvement_score: number | null;
  created_at: string;
}

export interface ValidationPrompt {
  decision_id: number;
  document_id: number | null;
  cluster_id: number | null;
  created_at: string;
  title: string;
  message: string;
  concepts?: string[];
  question: string;
  options: ValidationOption[];
  confidence: number;
  decision_type: string;
}

export interface ValidationOption {
  value: string;
  label: string;
  feedback_type: string;
  requires_edit?: boolean;
}

export interface ValidationPromptsResponse {
  prompts: ValidationPrompt[];
  summary: ValidationSummary;
  count: number;
}

export interface ValidationSummary {
  total_pending: number;
  average_confidence: number;
  by_type: Record<string, number>;
  urgency_level: 'low' | 'medium' | 'high';
}

export interface SubmitFeedbackRequest {
  decision_id: number;
  validation_result: 'accepted' | 'rejected' | 'partial';
  new_value?: Record<string, unknown>;
  user_reasoning?: string;
}

export interface AccuracyMetrics {
  overall_accuracy: number;
  by_confidence_range: Record<string, { accuracy: number; count: number }>;
  improvement_trend: number;
  total_decisions: number;
  validated_decisions: number;
}

export interface ClusterMoveRequest {
  document_id: number;
  from_cluster_id: number | null;
  to_cluster_id: number;
  ai_decision_id?: number;
  user_reasoning?: string;
}

export interface ConceptEditRequest {
  document_id: number;
  original_concepts: string[];
  new_concepts: string[];
  ai_decision_id?: number;
  user_reasoning?: string;
}

export interface ValidationRequest {
  ai_decision_id: number;
  accepted: boolean;
  user_reasoning?: string;
}

export interface LearningMetrics {
  total_ai_decisions: number;
  acceptance_rate: number;
  average_confidence: number;
  total_feedback: number;
  unprocessed_feedback: number;
  by_decision_type: Record<string, {
    total: number;
    accepted: number;
    rejected: number;
    average_confidence: number;
  }>;
}

export interface FeedbackPatterns {
  total_feedback: number;
  by_type: Record<string, number>;
  most_common_corrections: Array<{
    feedback_type: string;
    count: number;
  }>;
  cluster_preferences?: Record<string, unknown>;
  concept_preferences?: Record<string, unknown>;
}

export interface PendingValidations {
  pending_decisions: Array<AIDecision & { needs_validation: boolean }>;
  count: number;
  message: string;
}

export interface LearningProfile {
  has_profile: boolean;
  username?: string;
  accuracy_rate?: number;
  confidence_threshold?: number;
  last_learning_run?: string;
  total_rules?: number;
  total_vocabulary?: number;
  calibrated_thresholds?: Record<string, number>;
  message?: string;
}

export interface LearningStatus {
  username: string;
  profile: {
    accuracy_rate: number;
    confidence_threshold: number;
    last_learning_run: string | null;
  };
  rules: {
    total: number;
    by_type: Record<string, number>;
    top_applied: Array<{
      rule_type: string;
      condition: Record<string, unknown>;
      action: Record<string, unknown>;
      times_applied: number;
    }>;
  };
  vocabulary: {
    total: number;
    top_terms: Array<{
      canonical_name: string;
      category: string;
      times_seen: number;
    }>;
  };
  pending_feedback: {
    unprocessed: number;
    oldest_unprocessed: string | null;
  };
}

export interface LearningRunResult {
  message: string;
  rules_created: number;
  rules_updated: number;
  vocabulary_added: number;
  vocabulary_updated: number;
  feedback_processed: number;
}

export interface CalibrationResult {
  message: string;
  min_required?: number;
  old_thresholds?: Record<string, number>;
  new_thresholds?: Record<string, number>;
  accuracy_by_threshold?: Record<string, number>;
  recommended_threshold?: number;
}
