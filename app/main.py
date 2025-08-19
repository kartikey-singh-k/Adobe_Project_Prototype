import os
import shutil
import uuid
import traceback
import logging
from datetime import datetime
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import fitz  # PyMuPDF

from outline import outline_from_pdf
from insights import summarize, keyphrases, build_search_index, search
from llm_integration import generate_insights, generate_podcast_script
from audio_generation import text_to_speech

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document Intelligence System",
    version="1.0",
    description="AI-powered document analysis and insights"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE, "data", "uploads")
STATIC_DIR = os.path.join(BASE, "static")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Serve static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=DATA_DIR), name="uploads")

# In-memory storage
indexes: Dict[str, Dict] = {}
documents_metadata: Dict[str, Dict] = {}

@app.get("/", response_class=HTMLResponse)
def home():
    """Serve the main application"""
    idx = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(idx):
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Document Intelligence System</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                h1 { color: #333; }
                .container { max-width: 800px; margin: 0 auto; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Document Intelligence System</h1>
                <p>UI is being initialized. Please check if index.html exists in static folder.</p>
                <p>Upload PDFs at <code>/upload</code> endpoint.</p>
            </div>
        </body>
        </html>
        """)
    return FileResponse(idx)

@app.post("/api/upload/bulk")
async def bulk_upload(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Upload multiple PDFs for background processing"""
    results = []
    for file in files:
        if file.content_type != "application/pdf":
            continue
        
        uid = str(uuid.uuid4())
        pdf_path = os.path.join(DATA_DIR, f"{uid}.pdf")
        
        try:
            # Save file
            with open(pdf_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # Process in background
            background_tasks.add_task(process_document_async, uid, pdf_path)
            
            results.append({
                "doc_id": uid,
                "filename": file.filename,
                "status": "processing"
            })
            
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
    
    return {"uploaded": len(results), "documents": results}

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a single PDF"""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    uid = str(uuid.uuid4())
    pdf_path = os.path.join(DATA_DIR, f"{uid}.pdf")
    
    try:
        # Save file
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Process document
        result = await process_document(uid, pdf_path)
        return JSONResponse(result)
        
    except Exception as e:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        logger.error(f"Upload failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

async def process_document_async(doc_id: str, pdf_path: str):
    """Background processing for bulk uploads"""
    try:
        result = await process_document(doc_id, pdf_path)
        logger.info(f"Background processing completed for {doc_id}: {result['title']}")
    except Exception as e:
        logger.error(f"Background processing failed for {doc_id}: {e}")

async def process_document(doc_id: str, pdf_path: str):
    """Process PDF document and extract insights"""
    try:
        # Extract outline and text
        ol = outline_from_pdf(pdf_path)
        doc = fitz.open(pdf_path)
        
        pages_text = []
        docs = []
        pid = 0
        
        for pno, page in enumerate(doc):
            t = page.get_text()
            pages_text.append(t)
            # Split by paragraphs
            paragraphs = [p.strip() for p in t.split('\n\n') if p.strip()]
            for para in paragraphs:
                docs.append({
                    "id": pid, 
                    "text": para, 
                    "meta": {"page": pno + 1, "doc_id": doc_id}
                })
                pid += 1
        
        full_text = "\n".join(pages_text)
        
        # Build search index
        idx = build_search_index(docs)
        idx["docs"] = docs
        indexes[doc_id] = idx
        
        # Store metadata
        documents_metadata[doc_id] = {
            "title": ol.get("title") or os.path.basename(pdf_path).replace('.pdf', ''),
            "outline": ol.get("outline", []),
            "page_count": len(doc),
            "processed_at": datetime.now().isoformat(),
            "filename": os.path.basename(pdf_path)
        }
        
        doc.close()
        
        return {
            "doc_id": doc_id,
            "title": documents_metadata[doc_id]["title"],
            "outline": documents_metadata[doc_id]["outline"],
            "page_count": documents_metadata[doc_id]["page_count"],
            "viewer_url": f"/uploads/{doc_id}.pdf"
        }
        
    except Exception as e:
        logger.error(f"Processing failed: {traceback.format_exc()}")
        raise e

@app.get("/api/documents")
def list_documents():
    """List all processed documents"""
    return {
        "documents": [
            {
                "id": doc_id,
                **metadata,
                "has_index": doc_id in indexes
            }
            for doc_id, metadata in documents_metadata.items()
        ]
    }

@app.get("/api/pdf/{doc_id}")
def get_pdf(doc_id: str):
    """Serve PDF file"""
    pdf_path = os.path.join(DATA_DIR, f"{doc_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf")

@app.get("/api/outline/{doc_id}")
def get_outline(doc_id: str):
    """Get document outline"""
    if doc_id not in documents_metadata:
        raise HTTPException(status_code=404, detail="Document not found")
    return documents_metadata[doc_id]["outline"]

@app.get("/api/search")
def api_search(doc_id: str, q: str, k: int = 6):
    """Search within a document"""
    if doc_id not in indexes:
        raise HTTPException(status_code=404, detail="Document index not found")
    return search(indexes[doc_id], q, top_k=k)

@app.get("/api/related")
def api_related(doc_id: str, text: str, k: int = 5):
    """Find related sections"""
    if doc_id not in indexes:
        raise HTTPException(status_code=404, detail="Document index not found")
    return search(indexes[doc_id], text, top_k=k)

@app.get("/api/cross-document-search")
def cross_document_search(q: str, k: int = 10):
    """Search across all documents"""
    results = []
    for doc_id, index in indexes.items():
        doc_results = search(index, q, top_k=min(3, k))
        for result in doc_results:
            result["doc_id"] = doc_id
            result["doc_title"] = documents_metadata.get(doc_id, {}).get("title", "Unknown")
            results.append(result)
    
    # Sort by score and return top K
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:k]
@app.post("/api/insights/{doc_id}")
def generate_document_insights(doc_id: str, section_text: str = Form(None)):
    """Generate insights using local ML methods"""
    if doc_id not in indexes:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # If no specific text provided, use the document's content
        if not section_text or section_text.strip() == "Full document analysis requested":
            # Get text from the document's index
            doc_texts = [d["text"] for d in indexes[doc_id]["docs"] if d["text"].strip()]
            section_text = " ".join(doc_texts[:10])  # Use first 10 paragraphs
        
        # Get relevant context
        context = ""
        if section_text and len(section_text) > 50:
            related = search(indexes[doc_id], section_text, top_k=3)
            context = "\n".join([r['text'] for r in related])
        
        # Generate insights
        insights = generate_insights(section_text, context)
        return {"insights": insights}
    
    except Exception as e:
        logger.error(f"Insights generation failed: {e}")
        from app.llm_integration import get_empty_insights
        return {"insights": get_empty_insights(), "error": str(e)}

@app.post("/api/podcast/{doc_id}")
def generate_podcast(doc_id: str, section_text: str = Form(...)):
    """Generate podcast script for browser TTS"""
    if doc_id not in indexes:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Get related content for context
        related = search(indexes[doc_id], section_text, top_k=3)
        context = "\n".join([r['text'] for r in related])
        
        # Generate podcast script
        script = generate_podcast_script(section_text, context)
        
        # Create text file for browser TTS
        audio_path = text_to_speech(script, doc_id)
        
        return {
            "script": script,
            "audio_url": f"/static/audio/{os.path.basename(audio_path)}",
            "text_content": script,  # For browser TTS
            "duration": "2-3 minutes",
            "instructions": "Use browser's text-to-speech functionality to play this content"
        }
        
    except Exception as e:
        logger.error(f"Podcast generation failed: {e}")
        return {
            "error": "Podcast generation requires browser text-to-speech",
            "fallback": "Please use your browser's built-in text reading functionality"
        }

@app.get("/api/health")
def health_check():
    """System health check"""
    total_size = 0
    if os.path.exists(DATA_DIR):
        for file in os.listdir(DATA_DIR):
            file_path = os.path.join(DATA_DIR, file)
            if os.path.isfile(file_path):
                total_size += os.path.getsize(file_path)
    
    return {
        "status": "healthy",
        "documents_processed": len(documents_metadata),
        "indexes_loaded": len(indexes),
        "storage_usage": f"{total_size / (1024*1024):.2f} MB"
    }

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    """Delete a document and its index"""
    try:
        # Remove from memory
        if doc_id in indexes:
            del indexes[doc_id]
        if doc_id in documents_metadata:
            del documents_metadata[doc_id]
        
        # Remove file
        pdf_path = os.path.join(DATA_DIR, f"{doc_id}.pdf")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        return {"status": "deleted", "doc_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.get("/api/extract-text/{doc_id}")
async def extract_text(doc_id: str, max_pages: int = 10):
    """Extract text from PDF for analysis"""
    pdf_path = os.path.join(DATA_DIR, f"{doc_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    
    try:
        text_content = []
        doc = fitz.open(pdf_path)
        
        # Extract text from pages
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_content.append(f"Page {page_num + 1}:\n{text}")
        
        doc.close()
        
        full_text = "\n\n".join(text_content)
        return {
            "text": full_text,
            "total_pages": len(doc),
            "extracted_pages": min(len(doc), max_pages)
        }
        
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")