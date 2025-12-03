# Prompt Optimization Log

This document tracks changes to AI prompts for token efficiency and cost reduction.

---

## 2025-12-03: Build Suggestions - Removed Flask Code Example

### Change
Removed 50-line Flask authentication code example from build suggestions prompt.

### Location
`backend/llm_providers.py` - `generate_build_suggestions_improved()` method (line ~660)

### Old Prompt (starter_code field):
```
"starter_code": "# main.py - Production-ready example with auth, database, error handling
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'change-this-in-production')
db = SQLAlchemy(app)
jwt = JWTManager(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        user = User(username=data['username'], email=data['email'])
        db.session.add(user)
        db.session.commit()
        return jsonify({'message': 'User created', 'id': user.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user:
        token = create_access_token(identity=user.id)
        return jsonify({'token': token}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/users', methods=['GET'])
@jwt_required()
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)"
```

### New Prompt (starter_code field):
```
"starter_code": "Complete, working code that includes:
  - Main entry point with proper imports and dependencies
  - Database models with relationships and constraints
  - API routes with error handling and input validation
  - Authentication/authorization where relevant
  - Environment configuration (.env support)
  - Ready to run immediately (e.g., 'python main.py' or 'npm start')

Quality standard: Production-ready, not tutorial code. Include realistic error handling, proper validation, and production-grade patterns."
```

### Rationale
- GPT-5-mini has seen millions of Flask examples in training data
- The embedded example adds ~650 tokens per request
- Quality bar is maintained through clear requirements instead of example code
- The AI already knows how to write production-ready Flask code

### Expected Impact
- **Token savings**: ~650 tokens per build suggestion request
- **Risk**: Output quality might decrease if the example was acting as a "quality anchor"

### Testing Instructions
1. Generate build suggestions with the new prompt
2. Compare output quality to previous suggestions
3. Check if starter code is still production-ready (includes auth, error handling, env vars)
4. If quality drops, revert this commit: `git revert HEAD`

### Additional Changes in Same Commit
- Removed non-functional `temperature=0.5` parameter (GPT-5 ignores it)
- Added comment noting temperature removal

---

## Rollback Instructions

If build suggestion quality degrades:

```bash
# View this specific change
git log --oneline | grep "prompt optimization"

# Revert the commit
git revert <commit-hash>

# Push the revert
git push origin claude/review-recent-changes-01CM4zVUANAyHqx1mqko2jYZ
```

Or manually restore the old prompt from this log file.

---

## Future Optimization Candidates

### Not Yet Implemented:

1. **Extract category definitions to constant** (Medium impact)
   - Category definitions repeated in multiple prompts
   - Savings: ~300-400 tokens per concept extraction call

2. **Simplify CAPS emphasis** (Low impact)
   - Replace "IMPORTANT:", "DO NOT", "MUST" with normal case
   - Savings: ~50-100 tokens per prompt

3. **Remove temperature from all other prompts** (No token impact, code clarity)
   - Clean up non-functional parameters throughout codebase

---

*Log maintained by: daz2208*
