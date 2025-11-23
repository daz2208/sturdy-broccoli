'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { BookOpen, ChevronLeft, ChevronRight, RotateCcw, Loader2 } from 'lucide-react';
import type { Flashcard, Document } from '@/types/api';

export default function FlashcardsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<number | null>(null);
  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [numCards, setNumCards] = useState(10);

  useEffect(() => { loadDocuments(); }, []);

  const loadDocuments = async () => {
    try {
      const data = await api.getDocuments();
      setDocuments(data.documents);
    } catch {
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const generateFlashcards = async () => {
    if (!selectedDoc) {
      toast.error('Please select a document');
      return;
    }
    setGenerating(true);
    try {
      const result = await api.generateFlashcards(selectedDoc, numCards);
      setFlashcards(result.flashcards);
      setCurrentIndex(0);
      setShowAnswer(false);
      toast.success(`Generated ${result.cards_generated} flashcards`);
    } catch {
      toast.error('Failed to generate flashcards');
    } finally {
      setGenerating(false);
    }
  };

  const nextCard = () => {
    setShowAnswer(false);
    setCurrentIndex((prev) => (prev + 1) % flashcards.length);
  };

  const prevCard = () => {
    setShowAnswer(false);
    setCurrentIndex((prev) => (prev - 1 + flashcards.length) % flashcards.length);
  };

  const DIFFICULTY_COLORS = {
    easy: 'text-green-400 bg-green-400/10',
    medium: 'text-yellow-400 bg-yellow-400/10',
    hard: 'text-red-400 bg-red-400/10',
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Flashcards</h1>
        <p className="text-gray-500">Generate study flashcards from your documents</p>
      </div>

      {/* Controls */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Select Document</label>
            <select
              value={selectedDoc || ''}
              onChange={(e) => setSelectedDoc(Number(e.target.value))}
              className="input w-full"
            >
              <option value="">Choose a document...</option>
              {documents.map(doc => (
                <option key={doc.id} value={doc.id}>{doc.title}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Number of Cards</label>
            <input
              type="number"
              value={numCards}
              onChange={(e) => setNumCards(Number(e.target.value))}
              min={1}
              max={50}
              className="input w-full"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={generateFlashcards}
              disabled={generating || !selectedDoc}
              className="btn btn-primary w-full flex items-center justify-center gap-2"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
              {generating ? 'Generating...' : 'Generate'}
            </button>
          </div>
        </div>
      </div>

      {/* Flashcard Display */}
      {flashcards.length > 0 && (
        <div className="flex flex-col items-center">
          {/* Progress */}
          <div className="text-sm text-gray-500 mb-4">
            Card {currentIndex + 1} of {flashcards.length}
          </div>

          {/* Card */}
          <div
            onClick={() => setShowAnswer(!showAnswer)}
            className="w-full max-w-2xl bg-dark-100 rounded-xl border border-dark-300 p-8 min-h-[300px] cursor-pointer hover:border-primary transition-colors flex flex-col"
          >
            <div className="flex justify-between items-start mb-4">
              <span className={`px-2 py-1 rounded text-xs ${DIFFICULTY_COLORS[flashcards[currentIndex].difficulty]}`}>
                {flashcards[currentIndex].difficulty}
              </span>
              <span className="text-xs text-gray-500">
                {flashcards[currentIndex].concept}
              </span>
            </div>

            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                {!showAnswer ? (
                  <>
                    <p className="text-xl text-gray-200 mb-4">{flashcards[currentIndex].front}</p>
                    <p className="text-sm text-gray-500">Click to reveal answer</p>
                  </>
                ) : (
                  <>
                    <p className="text-lg text-primary mb-2">{flashcards[currentIndex].back}</p>
                    <p className="text-sm text-gray-500">Click to hide answer</p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex items-center gap-4 mt-6">
            <button onClick={prevCard} className="btn btn-secondary">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button onClick={() => { setCurrentIndex(0); setShowAnswer(false); }} className="btn btn-secondary">
              <RotateCcw className="w-5 h-5" />
            </button>
            <button onClick={nextCard} className="btn btn-secondary">
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {flashcards.length === 0 && !generating && (
        <div className="text-center py-12 text-gray-500">
          <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Select a document and generate flashcards to start studying</p>
        </div>
      )}
    </div>
  );
}
