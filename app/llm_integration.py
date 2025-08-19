import os
import re
import logging
from typing import Dict, List
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

# ML model availability flag
ML_AVAILABLE = False

def generate_insights(text: str, context: str = "") -> Dict:
    """Generate insights using enhanced rule-based methods"""
    if not text.strip():
        return get_empty_insights()
    
    return generate_enhanced_insights(text)

def generate_enhanced_insights(text: str) -> Dict:
    """Enhanced rule-based insights with semantic analysis"""
    key_phrases = extract_key_phrases(text)
    entities = extract_entities(text)
    sentiment = analyze_sentiment(text)
    word_count = len(text.split())
    
    return {
        "key_insights": [
            f"Document contains {word_count} words with key topics: {', '.join(key_phrases[:2])}" if key_phrases else f"Comprehensive content with {word_count} words",
            "Content appears well-structured for technical comprehension",
            "Includes specialized terminology relevant to the subject matter"
        ],
        "did_you_know": [
            f"Discusses concepts like {', '.join(entities[:2])}" if entities else "Contains valuable technical information",
            "The content structure suggests formal documentation standards",
            f"Uses {len(set(text.lower().split()))} unique words with specialized vocabulary"
        ],
        "counterpoints": [
            "Consider alternative interpretations of technical concepts",
            "Different methodologies might yield varying results",
            "Context and application may affect interpretation"
        ],
        "connections": [
            "Relates to broader industry practices and standards",
            "Connects to ongoing developments in related technical fields",
            "Has implications for practical implementation and real-world use"
        ],
        "source": "local_analysis",
        "stats": {
            "word_count": word_count,
            "unique_words": len(set(text.lower().split())),
            "key_phrases": key_phrases[:5],
            "entities": entities[:5]
        }
    }

def extract_key_phrases(text: str, top_n: int = 8) -> List[str]:
    """Extract key phrases using TF-IDF"""
    try:
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if not sentences:
            return []
        
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), 
            stop_words='english', 
            max_features=500,
            min_df=2,
            max_df=0.8
        )
        X = vectorizer.fit_transform(sentences)
        feature_names = vectorizer.get_feature_names_out()
        
        scores = np.asarray(X.mean(axis=0)).ravel()
        top_indices = scores.argsort()[::-1][:top_n]
        
        return [feature_names[i] for i in top_indices if scores[i] > 0.1]
    
    except Exception as e:
        logger.error(f"Key phrase extraction failed: {e}")
        # Fallback to simple frequency analysis
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        words = [w for w in words if w not in get_stopwords()]
        return [w for w, _ in Counter(words).most_common(top_n)]

def extract_entities(text: str) -> List[str]:
    """Simple entity extraction using capitalization patterns"""
    try:
        # Extract capitalized phrases (simple named entity recognition)
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        # Filter out common words and deduplicate
        common_entities = {'The', 'And', 'For', 'With', 'This', 'That', 'These', 'Those'}
        unique_entities = list(set(entities) - common_entities)
        return sorted(unique_entities, key=len, reverse=True)[:10]
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return []

def analyze_sentiment(text: str) -> str:
    """Simple sentiment analysis"""
    positive_words = ["excellent", "great", "amazing", "wonderful", "best", "success", "positive", "effective", "efficient"]
    negative_words = ["poor", "bad", "terrible", "worst", "failure", "negative", "problem", "issue", "limitation", "challenge"]
    
    text_lower = text.lower()
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    else:
        return "neutral"

def detect_topics(text: str) -> List[str]:
    """Detect broad topics based on keyword matching"""
    topic_keywords = {
        "technology": ["algorithm", "software", "system", "data", "code", "computer", "digital", "network"],
        "science": ["research", "experiment", "theory", "analysis", "scientific", "study", "hypothesis"],
        "business": ["market", "strategy", "management", "financial", "business", "company", "organization"],
        "education": ["learning", "teaching", "student", "knowledge", "education", "course", "training"],
        "health": ["medical", "health", "treatment", "patient", "disease", "clinical", "hospital"],
        "engineering": ["design", "engineer", "technical", "manufacturing", "construction", "development"]
    }
    
    text_lower = text.lower()
    detected = []
    
    for topic, keywords in topic_keywords.items():
        keyword_count = sum(1 for keyword in keywords if keyword in text_lower)
        if keyword_count >= 2:  # Require at least 2 keywords for confidence
            detected.append(topic)
    
    return detected if detected else ["general"]

def get_stopwords() -> set:
    """Extended stopwords list"""
    return set([
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", 
        "with", "by", "from", "this", "that", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "must", "can", "shall", "it", "its", "they", "them", "their",
        "what", "which", "who", "whom", "whose", "where", "when", "why", "how"
    ])

def get_empty_insights() -> Dict:
    return {
        "key_insights": ["No content provided for analysis"],
        "did_you_know": ["Please provide text to generate insights"],
        "counterpoints": [],
        "connections": [],
        "source": "empty",
        "stats": {
            "word_count": 0,
            "unique_words": 0,
            "key_phrases": [],
            "entities": []
        }
    }

def generate_podcast_script(main_content: str, related_content: str = "") -> str:
    """Generate podcast script using template-based approach"""
    if not main_content.strip():
        return "Welcome to today's podcast. No content was provided for discussion."
    
    # Extract key elements
    key_phrases = extract_key_phrases(main_content, top_n=3)
    entities = extract_entities(main_content)
    word_count = len(main_content.split())
    
    # Build engaging podcast script
    script = f"""
Welcome to Document Insights Podcast! 

Today we're exploring some fascinating content from your documents. 

Our main discussion revolves around: {main_content[:120]}{'...' if len(main_content) > 120 else ''}

We'll be covering key concepts including {', '.join(key_phrases[:2]) if key_phrases else 'important technical topics'}.

This content contains approximately {word_count} words and discusses entities like {', '.join(entities[:2]) if entities else 'various important concepts'}.

What's particularly interesting is how this material connects to broader industry trends and practical applications. 

Remember, while this information is valuable, it's always good to consider different perspectives and how these concepts might apply in various contexts.

That's all for today's episode. Thank you for listening, and keep exploring knowledge!
"""
    
    return script.strip()

# Remove all ML-related code since we're using rule-based only