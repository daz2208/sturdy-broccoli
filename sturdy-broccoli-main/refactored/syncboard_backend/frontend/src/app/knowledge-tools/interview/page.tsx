'use client';

import { useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { UserCheck, MessageSquare, Code, Server, AlertTriangle, BookOpen, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import type { InterviewPrep, InterviewQuestion } from '@/types/api';

const ROLES = ['Frontend Developer', 'Backend Developer', 'Full Stack Developer', 'DevOps Engineer', 'Data Scientist', 'Software Architect'];
const LEVELS = ['Junior', 'Mid-level', 'Senior', 'Staff', 'Principal'];

function QuestionCard({ question, type }: { question: InterviewQuestion; type: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-dark-200 rounded-lg p-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start justify-between text-left"
      >
        <p className="text-gray-200 font-medium pr-4">{question.question}</p>
        {expanded ? <ChevronUp className="w-5 h-5 text-gray-500 flex-shrink-0" /> : <ChevronDown className="w-5 h-5 text-gray-500 flex-shrink-0" />}
      </button>

      {expanded && (
        <div className="mt-4 space-y-3 pt-4 border-t border-dark-300">
          {question.answer && (
            <div>
              <p className="text-xs text-gray-500 uppercase mb-1">Answer</p>
              <p className="text-gray-300 text-sm">{question.answer}</p>
            </div>
          )}
          {question.guidance && (
            <div>
              <p className="text-xs text-gray-500 uppercase mb-1">Guidance</p>
              <p className="text-gray-400 text-sm">{question.guidance}</p>
            </div>
          )}
          {question.approach && (
            <div>
              <p className="text-xs text-gray-500 uppercase mb-1">Approach</p>
              <p className="text-gray-400 text-sm">{question.approach}</p>
            </div>
          )}
          {question.trap && (
            <div className="bg-yellow-400/5 border border-yellow-400/20 rounded p-2">
              <p className="text-xs text-yellow-400 uppercase mb-1">Watch out for</p>
              <p className="text-yellow-400/80 text-sm">{question.trap}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function InterviewPage() {
  const [role, setRole] = useState('');
  const [level, setLevel] = useState('');
  const [prep, setPrep] = useState<InterviewPrep | null>(null);
  const [loading, setLoading] = useState(false);

  const generatePrep = async () => {
    setLoading(true);
    try {
      const data = await api.generateInterviewPrep(role || undefined, level || undefined);
      setPrep(data);
    } catch {
      toast.error('Failed to generate interview prep');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Interview Prep</h1>
        <p className="text-gray-500">Generate personalized interview preparation materials</p>
      </div>

      {/* Controls */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Role (optional)</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="input w-full"
            >
              <option value="">Auto-detect from KB</option>
              {ROLES.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Level (optional)</label>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="input w-full"
            >
              <option value="">Auto-detect</option>
              {LEVELS.map(l => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={generatePrep}
              disabled={loading}
              className="btn btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserCheck className="w-4 h-4" />}
              Generate Prep
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {prep && (
        <div className="space-y-6">
          {/* Topics */}
          {prep.topics.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Topics Covered</h2>
              <div className="flex flex-wrap gap-2">
                {prep.topics.map((topic, i) => (
                  <span key={i} className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Behavioral Questions */}
          {prep.behavioral_questions.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <MessageSquare className="w-5 h-5 text-blue-400" />
                <h2 className="text-lg font-semibold text-gray-200">Behavioral Questions</h2>
              </div>
              <div className="space-y-3">
                {prep.behavioral_questions.map((q, i) => (
                  <QuestionCard key={i} question={q} type="behavioral" />
                ))}
              </div>
            </div>
          )}

          {/* Technical Questions */}
          {prep.technical_questions.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Code className="w-5 h-5 text-green-400" />
                <h2 className="text-lg font-semibold text-gray-200">Technical Questions</h2>
              </div>
              <div className="space-y-3">
                {prep.technical_questions.map((q, i) => (
                  <QuestionCard key={i} question={q} type="technical" />
                ))}
              </div>
            </div>
          )}

          {/* System Design Questions */}
          {prep.system_design_questions.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Server className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-semibold text-gray-200">System Design Questions</h2>
              </div>
              <div className="space-y-3">
                {prep.system_design_questions.map((q, i) => (
                  <QuestionCard key={i} question={q} type="system_design" />
                ))}
              </div>
            </div>
          )}

          {/* Gotcha Questions */}
          {prep.gotcha_questions.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-5 h-5 text-yellow-400" />
                <h2 className="text-lg font-semibold text-gray-200">Gotcha Questions</h2>
              </div>
              <div className="space-y-3">
                {prep.gotcha_questions.map((q, i) => (
                  <QuestionCard key={i} question={q} type="gotcha" />
                ))}
              </div>
            </div>
          )}

          {/* Study Recommendations */}
          {prep.study_recommendations.length > 0 && (
            <div className="bg-primary/10 border border-primary/30 rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <BookOpen className="w-5 h-5 text-primary" />
                <h2 className="text-lg font-semibold text-gray-200">Study Recommendations</h2>
              </div>
              <ul className="space-y-2">
                {prep.study_recommendations.map((rec, i) => (
                  <li key={i} className="text-gray-300 flex items-start gap-2">
                    <span className="text-primary">•</span> {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {!prep && !loading && (
        <div className="text-center py-12 text-gray-500">
          <UserCheck className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Generate interview prep materials based on your knowledge base</p>
        </div>
      )}
    </div>
  );
}
