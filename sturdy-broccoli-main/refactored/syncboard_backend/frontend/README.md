# SyncBoard 3.0 Frontend

Modern React/Next.js frontend for SyncBoard Knowledge Management System.

## Tech Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Zustand** - State management
- **Axios** - HTTP client
- **Lucide React** - Icons
- **React Hot Toast** - Notifications

## Features

### Core Features
- User authentication (login/register)
- Document management (upload, view, delete)
- Semantic search with filters
- Cluster organization
- Analytics dashboard
- Build suggestions (AI-powered)

### Knowledge Tools (11 AI-Powered Features)
- Gap Analysis - Find knowledge gaps
- Flashcards - Generate study cards
- Weekly Digest - Learning summaries
- Learning Path - Optimize learning order
- Document Quality - Score documents
- KB Chat - Conversational RAG
- Code Generator - Generate code from concepts
- Document Comparison - Find overlaps/contradictions
- ELI5 Explainer - Simple explanations
- Interview Prep - Practice questions
- Debug Assistant - Debug with KB context

### Advanced Features
- Cloud integrations (Google Drive, Dropbox, GitHub, Notion)
- Knowledge bases management
- Project tracking
- N8N workflow generation
- Generated code management

## Setup

```bash
# Install dependencies
npm install

# Set environment variables
cp .env.example .env.local
# Edit .env.local and set NEXT_PUBLIC_API_URL

# Run development server
npm run dev

# Build for production
npm run build
npm start
```

## Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── login/             # Authentication
│   ├── dashboard/         # Main dashboard
│   ├── documents/         # Document management
│   ├── clusters/          # Cluster management
│   ├── search/            # Search interface
│   ├── analytics/         # Analytics dashboard
│   ├── build/             # Build suggestions
│   ├── integrations/      # Cloud integrations
│   ├── knowledge-bases/   # KB management
│   ├── knowledge-tools/   # 11 AI tools
│   ├── projects/          # Project tracking
│   ├── workflows/         # N8N workflows
│   └── admin/             # Admin panel
├── components/            # Reusable components
│   └── Sidebar.tsx        # Navigation sidebar
├── lib/
│   └── api.ts             # API client (120+ endpoints)
├── stores/
│   └── auth.ts            # Auth state management
└── types/
    └── api.ts             # TypeScript types
```

## API Coverage

The frontend includes a complete API client covering all 120+ backend endpoints:

- Authentication (2 endpoints)
- Uploads (6 endpoints)
- Search (3 endpoints)
- Documents (6 endpoints)
- Clusters (4 endpoints)
- Build Suggestions (5 endpoints)
- Analytics (1 endpoint)
- AI Generation (2 endpoints)
- Duplicates (3 endpoints)
- Tags (6 endpoints)
- Saved Searches (4 endpoints)
- Relationships (4 endpoints)
- Jobs (3 endpoints)
- Integrations (7 endpoints)
- Knowledge Bases (6 endpoints)
- Admin (2 endpoints)
- Knowledge Graph (8 endpoints)
- Project Goals (6 endpoints)
- Project Tracking (6 endpoints)
- N8N Workflows (6 endpoints)
- Generated Code (5 endpoints)
- Knowledge Tools (12 endpoints)

## Extending

To add new pages, create a new directory in `src/app/` with a `page.tsx` file.
Copy the layout from an existing authenticated page to use the sidebar navigation.

All API calls should go through the `api` client in `src/lib/api.ts`.
