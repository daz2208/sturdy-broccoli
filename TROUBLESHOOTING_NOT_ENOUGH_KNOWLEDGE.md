# Troubleshooting: "Not Enough Knowledge" Error

If you're seeing "Add more content to your knowledge bank for better suggestions!" when trying to generate build ideas, follow these steps:

## Step 1: Restart Backend (IMPORTANT!)

The fixes need the backend to be restarted to take effect:

```bash
cd sturdy-broccoli-main/refactored/syncboard_backend
docker-compose restart backend
```

Wait 10-15 seconds for it to fully restart.

## Step 2: Run Diagnostic

This will tell you exactly what's wrong:

```bash
docker-compose exec backend python diagnose_knowledge.py
```

The script will show you:
- ✅ What's working
- ❌ What's missing
- 💡 What to do about it

## Common Issues & Solutions

### Issue 1: No Concepts Found (MOST COMMON)

**Symptoms:**
```
❌ CRITICAL PROBLEM: NO CONCEPTS FOUND!
```

**Causes:**
- Documents uploaded before concept extraction was working
- OpenAI API key invalid/missing
- Concept extraction failing

**Solution:**
1. Check OpenAI API key in `.env`:
   ```bash
   cat .env | grep OPENAI_API_KEY
   ```

2. Check backend logs for errors:
   ```bash
   docker-compose logs backend | grep -i "concept\|error" | tail -50
   ```

3. **Re-upload your documents** - this will trigger concept extraction

### Issue 2: Not Enough Content

**Symptoms:**
```
⚠️ WARNING: Only 1 unique concepts (minimum: 2)
```

**Solution:**
- Upload more diverse content (different topics, languages, frameworks)
- Upload at least 2-3 documents with varied content

### Issue 3: No Clusters

**Symptoms:**
```
❌ PROBLEM: No clusters found!
```

**Solution:**
- Clusters are created automatically during upload
- Try re-uploading documents
- Check backend logs for clustering errors

## Step 3: Check Backend Logs

After restarting, try generating ideas again and watch the logs:

```bash
docker-compose logs -f backend
```

Look for:
```
Knowledge validation check:
  Documents: X (min: 1)
  Unique concepts: X (min: 2)  <-- This is the key one
  Clusters: X (min: 1)
  Content length: X chars (min: 200)
```

If you see:
```
Knowledge validation FAILED: Only X unique concepts (need 2+)
```

Then you know concepts aren't being loaded. Check Step 1 (restart) was done.

## Step 4: Force Concept Extraction

If concepts still aren't showing up, you may need to re-upload content:

1. Note your current documents (take screenshots if needed)
2. Delete a document from your knowledge base
3. Re-upload it through the UI

This will trigger fresh concept extraction.

## Still Not Working?

Check:
1. ✅ Backend was restarted: `docker-compose ps` (should show "Up X seconds/minutes")
2. ✅ Using updated code: `git log -1` (should show commit about validation)
3. ✅ OpenAI API key is valid and has quota
4. ✅ No errors in logs: `docker-compose logs backend | grep ERROR`

## Requirements (After Fixes)

Your knowledge base needs:
- ✅ At least **1 document**
- ✅ At least **2 unique concepts** (reduced from 3)
- ✅ At least **1 cluster**
- ✅ At least **200 characters** of content

The concept extraction happens automatically when you upload documents via:
- File upload
- URL/YouTube video
- Text paste
- API upload
