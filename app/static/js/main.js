// Set PDF.js worker path
pdfjsLib = window['pdfjs-dist/build/pdf'];
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';

let currentDocumentId = null;
let currentDocumentText = null;
let currentPodcastText = null;
let speechSynthesis = window.speechSynthesis;
let documents_metadata = {};

// File selection handling
document.getElementById('fileInput').addEventListener('change', function(e) {
    const files = e.target.files;
    const fileList = document.getElementById('selectedFiles');
    
    if (files.length > 0) {
        fileList.innerHTML = `<strong>Selected files:</strong> ${files.length} PDF(s) ready for upload`;
    } else {
        fileList.innerHTML = '';
    }
});

async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) {
        alert('Please select at least one PDF file');
        return;
    }
    
    showLoading(true);
    
    const formData = new FormData();
    for (const file of fileInput.files) {
        formData.append('files', file);
    }
    
    try {
        const response = await fetch('/api/upload/bulk', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`✅ Successfully uploaded ${result.uploaded} documents! Processing in background...`);
            fileInput.value = '';
            document.getElementById('selectedFiles').innerHTML = '';
            loadDocuments();
        } else {
            throw new Error('Upload failed');
        }
    } catch (error) {
        alert('❌ Upload failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

async function loadDocuments() {
    try {
        const response = await fetch('/api/documents');
        const data = await response.json();
        documents_metadata = data.documents.reduce((acc, doc) => {
            acc[doc.id] = doc;
            return acc;
        }, {});
        displayDocuments(data.documents);
    } catch (error) {
        console.error('Failed to load documents:', error);
    }
}

function displayDocuments(documents) {
    const grid = document.getElementById('documentsGrid');
    
    if (documents.length === 0) {
        grid.innerHTML = `
            <div style="text-align: center; padding: 3rem; color: #7f8c8d;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">📄</div>
                <h3>No documents yet</h3>
                <p>Upload PDF files to get started with document intelligence</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = documents.map(doc => `
        <div class="document-card">
            <h3>${escapeHtml(doc.title)}</h3>
            <div class="document-stats">
                <span>📄 ${doc.page_count} pages</span>
                <span> ${new Date(doc.processed_at).toLocaleDateString()}</span>
            </div>
            <p><small>${doc.filename || 'Document'}</small></p>
            <button onclick="viewDocument('${doc.id}')"> View & Analyze</button>
            <button onclick="quickAnalyzeDocument('${doc.id}')" class="secondary"> Quick Insights</button>
            <button onclick="deleteDocument('${doc.id}')" style="background: #e74c3c;">Delete</button>
        </div>
    `).join('');
}

function viewDocument(docId) {
    currentDocumentId = docId;
    document.getElementById('documentsSection').style.display = 'none';
    document.getElementById('documentView').style.display = 'block';
    
    // Load PDF in viewer
    const viewer = document.getElementById('pdfViewer');
    viewer.src = `/api/pdf/${docId}`;
    
    // Update title
    const doc = documents_metadata[docId];
    if (doc) {
        document.getElementById('currentDocTitle').textContent = doc.title;
    }
    
    // Hide previous results
    document.getElementById('insightsContainer').style.display = 'none';
    document.getElementById('podcastContainer').style.display = 'none';
    document.getElementById('relatedSections').style.display = 'none';
}

function goBack() {
    document.getElementById('documentView').style.display = 'none';
    document.getElementById('documentsSection').style.display = 'block';
    document.getElementById('insightsContainer').style.display = 'none';
    document.getElementById('podcastContainer').style.display = 'none';
    document.getElementById('relatedSections').style.display = 'none';
    currentDocumentId = null;
}

// NEW FUNCTION: Quick analyze without opening the document
async function quickAnalyzeDocument(docId) {
    showLoading(true);
    
    try {
        // Extract a sample of text for quick analysis (first few paragraphs)
        const sampleText = await extractSampleTextFromPDF(docId);
        
        if (!sampleText || sampleText.trim().length < 30) {
            alert('Could not extract enough text for quick analysis. Please view the document for full analysis.');
            showLoading(false);
            return;
        }
        
        const formData = new FormData();
        formData.append('section_text', sampleText);
        
        const response = await fetch(`/api/insights/${docId}`, {
            method: 'POST',
            body: formData
        });
        
        const insights = await response.json();
        
        // Show insights in a modal or alert
        showQuickInsights(insights, documents_metadata[docId].title);
        
    } catch (error) {
        console.error('Quick analysis failed:', error);
        alert('Quick analysis failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

async function extractSampleTextFromPDF(docId) {
    try {
        const pdfUrl = `/api/pdf/${docId}`;
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        const pdf = await loadingTask.promise;
        
        let sampleText = '';
        const samplePages = Math.min(pdf.numPages, 3); // Only first 3 pages for quick analysis
        
        for (let pageNum = 1; pageNum <= samplePages; pageNum++) {
            const page = await pdf.getPage(pageNum);
            const textContent = await page.getTextContent();
            const pageText = textContent.items.map(item => item.str).join(' ');
            sampleText += pageText + '\n\n';
            
            // Limit to first 1000 characters for quick analysis
            if (sampleText.length > 1000) {
                sampleText = sampleText.substring(0, 1000) + '...';
                break;
            }
        }
        
        return sampleText.trim();
    } catch (error) {
        console.error('PDF sample extraction failed:', error);
        return "Document content analysis for quick insights.";
    }
}
function showQuickInsights(insights, docTitle) {
    const keyInsights = insights.insights?.key_insights || ['No key insights available'];
    const quickFacts = insights.insights?.did_you_know || ['No additional facts available'];
    
    const modalHtml = `
        <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000;">
            <div style="background: white; padding: 2rem; border-radius: 15px; max-width: 600px; max-height: 80vh; overflow-y: auto;">
                <h2 style="color: #2c3e50; margin-bottom: 1rem;">💡 Quick Insights</h2>
                <h3 style="color: #3498db; margin-bottom: 1.5rem;">${escapeHtml(docTitle)}</h3>
                
                <div style="margin: 1.5rem 0;">
                    <h4 style="color: #2c3e50; display: flex; align-items: center; gap: 0.5rem;">
                        <span>🔑</span> Key Insights:
                    </h4>
                    <ul style="list-style: none; padding-left: 1rem;">
                        ${keyInsights.map(insight => `
                            <li style="padding: 0.5rem 0; border-bottom: 1px solid #eee;">
                                ✅ ${escapeHtml(insight)}
                            </li>
                        `).join('')}
                    </ul>
                </div>
                
                <div style="margin: 1.5rem 0;">
                    <h4 style="color: #2c3e50; display: flex; align-items: center; gap: 0.5rem;">
                        <span>ℹ️</span> Quick Facts:
                    </h4>
                    <ul style="list-style: none; padding-left: 1rem;">
                        ${quickFacts.map(fact => `
                            <li style="padding: 0.5rem 0; border-bottom: 1px solid #eee;">
                                📌 ${escapeHtml(fact)}
                            </li>
                        `).join('')}
                    </ul>
                </div>
                
                <div style="text-align: center; margin-top: 2rem;">
                    <button onclick="closeModal()" style="
                        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
                        color: white; 
                        border: none; 
                        padding: 0.8rem 2rem; 
                        border-radius: 25px; 
                        cursor: pointer; 
                        font-weight: 600;
                        transition: all 0.3s ease;
                    " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='none'">
                        👍 Got It!
                    </button>
                </div>
                
                <p style="text-align: center; margin-top: 1rem; color: #7f8c8d; font-size: 0.9rem;">
                    💡 Tip: Click "View & Analyze" for detailed document exploration
                </p>
            </div>
        </div>
    `;
    
    const modal = document.createElement('div');
    modal.innerHTML = modalHtml;
    modal.id = 'quickInsightsModal';
    document.body.appendChild(modal);
}

function closeModal() {
    const modal = document.getElementById('quickInsightsModal');
    if (modal) {
        modal.remove();
    }
}

async function analyzeDocument(docId, specificText = null) {
    showLoading(true);
    
    try {
        let textToAnalyze = specificText;
        
        // If no specific text provided, extract text from the PDF
        if (!textToAnalyze) {
            textToAnalyze = await extractTextFromPDF(docId);
        }
        
        if (!textToAnalyze || textToAnalyze.trim().length < 50) {
            alert('Could not extract enough text from the PDF for analysis. Please try another document.');
            showLoading(false);
            return;
        }
        
        const formData = new FormData();
        formData.append('section_text', textToAnalyze);
        
        const response = await fetch(`/api/insights/${docId}`, {
            method: 'POST',
            body: formData
        });
        
        const insights = await response.json();
        displayInsights(insights);
        
        // Also show related sections
        await showRelatedSections(docId, textToAnalyze);
        
    } catch (error) {
        console.error('Analysis failed:', error);
        alert('Analysis failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

async function extractTextFromPDF(docId) {
    try {
        const pdfUrl = `/api/pdf/${docId}`;
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        const pdf = await loadingTask.promise;
        
        let fullText = '';
        const maxPages = Math.min(pdf.numPages, 10);
        
        for (let pageNum = 1; pageNum <= maxPages; pageNum++) {
            const page = await pdf.getPage(pageNum);
            const textContent = await page.getTextContent();
            const pageText = textContent.items.map(item => item.str).join(' ');
            fullText += pageText + '\n\n';
        }
        
        return fullText.trim();
    } catch (error) {
        console.error('PDF text extraction failed:', error);
        return "Document content analysis. This PDF contains valuable information for review.";
    }
}

function displayInsights(insights) {
    const container = document.getElementById('insightsContainer');
    const content = document.getElementById('insightsContent');
    
    if (!insights.insights) {
        content.innerHTML = '<p>No insights generated. Please try again.</p>';
        container.style.display = 'block';
        return;
    }
    
    content.innerHTML = `
        <div class="insight-section">
            <h4>💡 Key Insights</h4>
            <ul class="insight-list">
                ${(insights.insights.key_insights || ['No key insights available']).map(i => `<li>${escapeHtml(i)}</li>`).join('')}
            </ul>
        </div>
        
        <div class="insight-section">
            <h4>🤔 Did You Know?</h4>
            <ul class="insight-list">
                ${(insights.insights.did_you_know || ['No additional facts available']).map(i => `<li>${escapeHtml(i)}</li>`).join('')}
            </ul>
        </div>
        
        <div class="insight-section">
            <h4>⚖️ Counterpoints</h4>
            <ul class="insight-list">
                ${(insights.insights.counterpoints || ['No counterpoints available']).map(i => `<li>${escapeHtml(i)}</li>`).join('')}
            </ul>
        </div>
        
        <div class="insight-section">
            <h4>🔗 Connections</h4>
            <ul class="insight-list">
                ${(insights.insights.connections || ['No connections available']).map(i => `<li>${escapeHtml(i)}</li>`).join('')}
            </ul>
        </div>
    `;
    
    container.style.display = 'block';
}

async function showRelatedSections(docId, text) {
    if (!text) return;
    
    try {
        const response = await fetch(`/api/related?doc_id=${docId}&text=${encodeURIComponent(text)}&k=5`);
        const relatedSections = await response.json();
        
        const container = document.getElementById('relatedContent');
        if (relatedSections && relatedSections.length > 0) {
            container.innerHTML = relatedSections.map(section => `
                <div class="related-card" onclick="highlightSection('${section.text}')">
                    <strong>Page ${section.meta?.page || 'N/A'}</strong>
                    <p>${escapeHtml(section.text.substring(0, 100))}...</p>
                    <small>Score: ${section.score?.toFixed(2) || '0.00'}</small>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p>No related sections found.</p>';
        }
        
        document.getElementById('relatedSections').style.display = 'block';
    } catch (error) {
        console.error('Failed to load related sections:', error);
    }
}

function highlightSection(text) {
    alert(`Would highlight: "${text.substring(0, 50)}..."`);
}

async function generatePodcast() {
    if (!currentDocumentId) return;
    
    showLoading(true);
    
    try {
        // Extract text from the current PDF for podcast
        const pdfText = await extractTextFromPDF(currentDocumentId);
        
        if (!pdfText || pdfText.trim().length < 100) {
            alert('Not enough text extracted for podcast generation. Please try another document.');
            showLoading(false);
            return;
        }
        
        const formData = new FormData();
        formData.append('section_text', pdfText);
        
        const response = await fetch(`/api/podcast/${currentDocumentId}`, {
            method: 'POST',
            body: formData
        });
        
        const podcast = await response.json();
        currentPodcastText = podcast.script || podcast.text_content || pdfText;
        
        const podcastContent = document.getElementById('podcastContent');
        podcastContent.innerHTML = `
            <p><strong>Podcast based on document content:</strong></p>
            <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 5px; margin: 1rem 0; max-height: 200px; overflow-y: auto;">
                ${escapeHtml(currentPodcastText.substring(0, 500))}...
            </div>
        `;
        
        document.getElementById('podcastContainer').style.display = 'block';
        
    } catch (error) {
        console.error('Podcast generation failed:', error);
        alert('Podcast generation failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function playPodcast() {
    if (!currentPodcastText) return;
    
    if (speechSynthesis.speaking) {
        speechSynthesis.cancel();
    }
    
    const utterance = new SpeechSynthesisUtterance(currentPodcastText);
    utterance.rate = 0.8;
    utterance.pitch = 1;
    utterance.volume = 1;
    
    speechSynthesis.speak(utterance);
}

function stopPodcast() {
    if (speechSynthesis.speaking) {
        speechSynthesis.cancel();
    }
}

async function deleteDocument(docId) {
    if (!confirm('Are you sure you want to delete this document?')) return;
    
    try {
        const response = await fetch(`/api/documents/${docId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            alert('Document deleted successfully');
            loadDocuments();
        } else {
            throw new Error('Delete failed');
        }
    } catch (error) {
        alert('Delete failed: ' + error.message);
    }
}

function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function analyzeFullDocument() {
    if (!currentDocumentId) return;
    analyzeDocument(currentDocumentId);
}

// Load documents on page load
loadDocuments();