"""
Self-Learning Semantic Dictionary for Concept Matching.

FEATURES:
1. Large seed dictionary (50+ concept mappings)
2. LLM-powered similarity detection for new concepts
3. In-memory caching (instant lookups)
4. JSON persistence (Docker-compatible)
5. Automatic growth based on user's content
"""

import os
import json
import logging
import asyncio
from typing import Set, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# Large seed dictionary - common concept relationships
SEED_SYNONYMS = {
    # AI/ML/Data Science
    "ai": {"artificial intelligence", "machine learning", "ml", "deep learning", "neural network", "llm", "gpt", "nlp"},
    "machine learning": {"ai", "ml", "artificial intelligence", "data science", "predictive modeling"},
    "ml": {"ai", "machine learning", "artificial intelligence", "deep learning"},
    "deep learning": {"neural network", "ai", "ml", "cnn", "rnn", "transformer"},
    "neural network": {"deep learning", "ai", "ml", "perceptron", "backpropagation"},
    "nlp": {"natural language processing", "text analysis", "ai", "language model"},
    "llm": {"large language model", "gpt", "ai", "nlp", "transformer"},
    "data science": {"analytics", "data analysis", "statistics", "ml", "python"},
    "computer vision": {"cv", "image processing", "cnn", "deep learning", "ai"},

    # Web Development - Frontend
    "javascript": {"js", "ecmascript", "node", "nodejs", "frontend"},
    "js": {"javascript", "ecmascript", "node"},
    "react": {"reactjs", "jsx", "frontend", "javascript", "component"},
    "reactjs": {"react", "jsx", "frontend", "javascript"},
    "vue": {"vuejs", "frontend", "javascript", "component"},
    "angular": {"angularjs", "frontend", "javascript", "typescript"},
    "frontend": {"web development", "ui", "user interface", "css", "html", "javascript"},
    "ui": {"user interface", "frontend", "ux", "design"},
    "ux": {"user experience", "ui", "design", "frontend"},
    "html": {"markup", "web", "frontend", "html5"},
    "css": {"stylesheet", "styling", "frontend", "sass", "scss"},
    "typescript": {"ts", "javascript", "typed", "frontend", "backend"},
    "webpack": {"bundler", "build tool", "javascript", "frontend"},
    "nextjs": {"next", "react", "ssr", "frontend", "fullstack"},

    # Web Development - Backend
    "backend": {"server", "api", "server-side", "web development"},
    "api": {"rest", "restful", "graphql", "endpoint", "backend", "web service"},
    "rest": {"restful", "api", "http", "web service"},
    "graphql": {"api", "query language", "backend"},
    "nodejs": {"node", "javascript", "backend", "server"},
    "express": {"expressjs", "nodejs", "backend", "web framework"},
    "fastapi": {"python", "backend", "api", "async", "web framework"},
    "django": {"python", "backend", "web framework", "orm"},
    "flask": {"python", "backend", "web framework", "micro"},

    # Databases
    "database": {"db", "data storage", "persistence", "sql", "nosql"},
    "sql": {"database", "mysql", "postgresql", "postgres", "relational"},
    "nosql": {"mongodb", "database", "redis", "document store", "non-relational"},
    "mysql": {"sql", "database", "relational", "rdbms"},
    "postgresql": {"postgres", "sql", "database", "relational", "rdbms"},
    "postgres": {"postgresql", "sql", "database", "relational"},
    "mongodb": {"nosql", "database", "document store", "json"},
    "redis": {"cache", "nosql", "in-memory", "database", "key-value"},
    "sqlite": {"sql", "database", "embedded", "relational"},
    "orm": {"object relational mapping", "database", "sqlalchemy", "django"},

    # Cloud & Infrastructure
    "docker": {"container", "containerization", "virtualization", "devops"},
    "container": {"docker", "containerization", "kubernetes", "virtualization"},
    "kubernetes": {"k8s", "container orchestration", "docker", "devops", "cloud"},
    "k8s": {"kubernetes", "container orchestration", "docker", "devops"},
    "aws": {"amazon web services", "cloud", "ec2", "s3", "lambda"},
    "azure": {"microsoft azure", "cloud", "cloud computing"},
    "gcp": {"google cloud platform", "cloud", "cloud computing"},
    "cloud": {"aws", "azure", "gcp", "cloud computing", "saas", "paas", "iaas"},
    "serverless": {"lambda", "cloud functions", "faas", "cloud"},
    "microservices": {"distributed", "architecture", "api", "backend"},

    # DevOps & CI/CD
    "devops": {"ci/cd", "deployment", "infrastructure", "automation", "docker"},
    "ci/cd": {"continuous integration", "continuous deployment", "devops", "pipeline"},
    "jenkins": {"ci/cd", "automation", "build", "devops"},
    "github actions": {"ci/cd", "automation", "workflow", "devops"},
    "terraform": {"infrastructure as code", "iac", "devops", "cloud"},
    "ansible": {"automation", "configuration management", "devops", "iac"},

    # Programming Languages
    "python": {"programming", "scripting", "data science", "backend", "ml"},
    "java": {"programming", "jvm", "enterprise", "backend", "oop"},
    "c++": {"cpp", "programming", "systems", "performance"},
    "cpp": {"c++", "programming", "systems", "performance"},
    "go": {"golang", "programming", "backend", "systems", "concurrency"},
    "golang": {"go", "programming", "backend", "systems"},
    "rust": {"programming", "systems", "performance", "memory safe"},
    "ruby": {"programming", "rails", "backend", "scripting"},
    "php": {"programming", "backend", "web", "server-side"},
    "swift": {"programming", "ios", "apple", "mobile"},
    "kotlin": {"programming", "android", "jvm", "mobile"},

    # Mobile Development
    "mobile": {"ios", "android", "app development", "smartphone"},
    "ios": {"swift", "objective-c", "apple", "mobile", "iphone"},
    "android": {"kotlin", "java", "mobile", "google"},
    "react native": {"mobile", "react", "javascript", "cross-platform"},
    "flutter": {"mobile", "dart", "cross-platform", "google"},

    # Testing & Quality
    "testing": {"qa", "quality assurance", "unit test", "integration test"},
    "unit test": {"testing", "pytest", "jest", "junit"},
    "integration test": {"testing", "e2e", "qa"},
    "pytest": {"python", "testing", "unit test"},
    "jest": {"javascript", "testing", "unit test", "react"},

    # Security
    "security": {"cybersecurity", "infosec", "authentication", "encryption"},
    "authentication": {"auth", "login", "oauth", "jwt", "security"},
    "auth": {"authentication", "authorization", "security"},
    "oauth": {"authentication", "security", "sso", "authorization"},
    "jwt": {"json web token", "authentication", "security", "token"},
    "encryption": {"crypto", "security", "ssl", "tls"},

    # Blockchain & Web3
    "blockchain": {"crypto", "web3", "distributed ledger", "bitcoin", "ethereum"},
    "crypto": {"cryptocurrency", "blockchain", "bitcoin", "ethereum"},
    "web3": {"blockchain", "decentralized", "ethereum", "dapp"},
    "ethereum": {"blockchain", "smart contract", "web3", "crypto"},
    "solidity": {"ethereum", "smart contract", "blockchain", "programming"},

    # Game Development
    "game development": {"gamedev", "unity", "unreal", "gaming"},
    "unity": {"game development", "game engine", "c#", "3d"},
    "unreal": {"unreal engine", "game development", "game engine", "c++"},

    # Tools & Editors
    "git": {"version control", "github", "gitlab", "vcs"},
    "github": {"git", "version control", "repository", "code hosting"},
    "vscode": {"visual studio code", "editor", "ide", "microsoft"},
    "vim": {"editor", "text editor", "terminal", "vi"},
}


class SemanticDictionaryManager:
    """
    Manages semantic concept relationships with self-learning capabilities.

    Features:
    - Large seed dictionary (50+ concepts)
    - LLM-powered similarity detection
    - In-memory caching for instant lookups
    - JSON persistence (Docker-compatible)
    """

    def __init__(
        self,
        persistence_path: Optional[str] = None,
        llm_provider = None
    ):
        """
        Initialize semantic dictionary manager.

        Args:
            persistence_path: Path to JSON file for learned synonyms
            llm_provider: LLM provider for similarity detection
        """
        self.seed_synonyms = SEED_SYNONYMS
        self.learned_synonyms: Dict[str, Set[str]] = {}
        self.similarity_cache: Dict[tuple, bool] = {}  # (concept_a, concept_b) -> is_similar

        # Persistence
        if persistence_path:
            self.persistence_path = Path(persistence_path)
        else:
            # Default: store in backend directory
            backend_dir = Path(__file__).parent
            self.persistence_path = backend_dir / "learned_synonyms.json"

        self.llm_provider = llm_provider
        self._lock = asyncio.Lock()

        # Load existing learned synonyms
        self._load_learned_synonyms()

        logger.info(
            f"Initialized SemanticDictionary: "
            f"{len(self.seed_synonyms)} seed concepts, "
            f"{len(self.learned_synonyms)} learned concepts"
        )

    def _load_learned_synonyms(self):
        """Load learned synonyms from JSON file."""
        if not self.persistence_path.exists():
            logger.info("No learned synonyms file found - starting fresh")
            return

        try:
            with open(self.persistence_path, 'r') as f:
                data = json.load(f)

            # Convert lists back to sets
            self.learned_synonyms = {
                concept: set(synonyms)
                for concept, synonyms in data.items()
            }

            logger.info(f"Loaded {len(self.learned_synonyms)} learned concept mappings")

        except Exception as e:
            logger.error(f"Failed to load learned synonyms: {e}")
            self.learned_synonyms = {}

    def _save_learned_synonyms(self):
        """Save learned synonyms to JSON file."""
        try:
            # Convert sets to lists for JSON serialization
            data = {
                concept: list(synonyms)
                for concept, synonyms in self.learned_synonyms.items()
            }

            # Ensure directory exists
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.persistence_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self.learned_synonyms)} learned concepts to {self.persistence_path}")

        except Exception as e:
            logger.error(f"Failed to save learned synonyms: {e}")

    def get_synonyms(self, concept: str) -> Set[str]:
        """
        Get all synonyms for a concept (seed + learned).

        Args:
            concept: Concept name

        Returns:
            Set of synonym strings
        """
        concept_lower = concept.lower()
        synonyms = set()

        # Add from seed
        if concept_lower in self.seed_synonyms:
            synonyms.update(self.seed_synonyms[concept_lower])

        # Add from learned
        if concept_lower in self.learned_synonyms:
            synonyms.update(self.learned_synonyms[concept_lower])

        return synonyms

    def expand_concepts(self, concept_names: list) -> Set[str]:
        """
        Expand concept list to include all synonyms.

        Args:
            concept_names: List of concept names

        Returns:
            Expanded set including synonyms
        """
        expanded = set()

        for name in concept_names:
            name_lower = name.lower()
            expanded.add(name_lower)
            expanded.update(self.get_synonyms(name_lower))

        return expanded

    async def are_concepts_similar(
        self,
        concept_a: str,
        concept_b: str,
        threshold: float = 0.7
    ) -> bool:
        """
        Check if two concepts are semantically similar.

        Uses:
        1. Seed dictionary (instant)
        2. Learned dictionary (instant)
        3. Cache (instant)
        4. LLM (one-time, then cached)

        Args:
            concept_a: First concept
            concept_b: Second concept
            threshold: Similarity threshold (0-1)

        Returns:
            True if concepts are similar
        """
        a_lower = concept_a.lower()
        b_lower = concept_b.lower()

        # Exact match
        if a_lower == b_lower:
            return True

        # Check seed dictionary
        if a_lower in self.seed_synonyms and b_lower in self.seed_synonyms[a_lower]:
            return True
        if b_lower in self.seed_synonyms and a_lower in self.seed_synonyms[b_lower]:
            return True

        # Check learned dictionary
        if a_lower in self.learned_synonyms and b_lower in self.learned_synonyms[a_lower]:
            return True
        if b_lower in self.learned_synonyms and a_lower in self.learned_synonyms[b_lower]:
            return True

        # Check cache
        cache_key = tuple(sorted([a_lower, b_lower]))
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]

        # Ask LLM (only if provider available)
        if self.llm_provider is None:
            return False

        try:
            is_similar = await self._ask_llm_similarity(a_lower, b_lower, threshold)

            # Cache result
            self.similarity_cache[cache_key] = is_similar

            # If similar, add to learned dictionary
            if is_similar:
                await self._add_learned_synonym(a_lower, b_lower)

            return is_similar

        except Exception as e:
            logger.error(f"LLM similarity check failed: {e}")
            return False

    async def _ask_llm_similarity(
        self,
        concept_a: str,
        concept_b: str,
        threshold: float
    ) -> bool:
        """
        Ask LLM if two concepts are semantically similar.

        This is only called once per concept pair, then cached.
        """
        prompt = f"""Are these two concepts semantically related or similar?

Concept A: "{concept_a}"
Concept B: "{concept_b}"

Consider:
- Are they synonyms? (e.g., "AI" and "machine learning")
- Do they belong to the same domain? (e.g., "docker" and "kubernetes")
- Would someone learning about one likely learn about the other?

Respond with ONLY a JSON object:
{{
    "similar": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}
"""

        try:
            # Use a simple chat completion
            response = await self.llm_provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            # Parse JSON response
            result = json.loads(response)

            is_similar = result.get("similar", False) and result.get("confidence", 0) >= threshold

            logger.info(
                f"LLM similarity: '{concept_a}' vs '{concept_b}' -> {is_similar} "
                f"(confidence: {result.get('confidence', 0):.2f})"
            )

            return is_similar

        except Exception as e:
            logger.error(f"LLM parsing error: {e}")
            return False

    async def _add_learned_synonym(self, concept_a: str, concept_b: str):
        """
        Add bidirectional learned synonym relationship.

        Thread-safe with async lock.
        """
        async with self._lock:
            # Add A -> B
            if concept_a not in self.learned_synonyms:
                self.learned_synonyms[concept_a] = set()
            self.learned_synonyms[concept_a].add(concept_b)

            # Add B -> A (bidirectional)
            if concept_b not in self.learned_synonyms:
                self.learned_synonyms[concept_b] = set()
            self.learned_synonyms[concept_b].add(concept_a)

            logger.info(f"Learned synonym: '{concept_a}' <-> '{concept_b}'")

            # Save to disk
            self._save_learned_synonyms()

    def get_stats(self) -> Dict:
        """Get statistics about the dictionary."""
        return {
            "seed_concepts": len(self.seed_synonyms),
            "learned_concepts": len(self.learned_synonyms),
            "cache_size": len(self.similarity_cache),
            "total_seed_relationships": sum(len(v) for v in self.seed_synonyms.values()),
            "total_learned_relationships": sum(len(v) for v in self.learned_synonyms.values()),
        }
