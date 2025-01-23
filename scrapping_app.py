# main.py
# main.py
import json
import time
import base64
import requests
import streamlit as st
from datetime import datetime
from typing import List, Dict
from io import BytesIO

# Configuration
NEWS_API_URL = "https://newsapi.org/v2/everything"
GUARDIAN_API_URL = "https://content.guardianapis.com/search"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MAX_API_CALLS_PER_DAY = 500
API_CALL_LOG = []
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif"]
MAX_IMAGE_SIZE_MB = 5
POSTS_TO_SHOW = 5  # Increased from 4 to 5

class Article:
    def __init__(self, title: str, description: str, url: str, source: str):
        self.title = title
        self.description = description
        self.url = url
        self.source = source
        self.scores: Dict[str, float] = {}

def rate_limited(max_calls: int):
    def decorator(func):
        def wrapper(*args, **kwargs):
            global API_CALL_LOG
            now = time.time()
            API_CALL_LOG = [t for t in API_CALL_LOG if now - t < 86400]
            
            if len(API_CALL_LOG) >= max_calls:
                oldest = datetime.fromtimestamp(API_CALL_LOG[0])
                next_avail = datetime.fromtimestamp(API_CALL_LOG[0] + 86400)
                st.error(f"API limit reached. First call: {oldest}. Next available: {next_avail}")
                st.stop()
                
            result = func(*args, **kwargs)
            API_CALL_LOG.append(time.time())
            return result
        return wrapper
    return decorator

class NewsAPIClient:
    @staticmethod
    @rate_limited(MAX_API_CALLS_PER_DAY)
    def fetch_articles(query: str) -> List[Article]:
        time.sleep(1)
        params = {
            "apiKey": st.secrets["NEWS_API_KEY"],
            "q": query,
            "pageSize": 20,  # Increased for more results
            "language": "en",
            "sortBy": "relevancy"
        }
        try:
            response = requests.get(NEWS_API_URL, params=params, timeout=10)
            return [
                Article(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    url=item.get("url", ""),
                    source=item.get("source", {}).get("name", "")
                ) for item in response.json().get("articles", [])
            ]
        except Exception as e:
            st.error(f"News API Error: {str(e)}")
            return []

class GuardianAPIClient:
    @staticmethod
    @rate_limited(MAX_API_CALLS_PER_DAY)
    def fetch_articles(query: str) -> List[Article]:
        time.sleep(1)
        params = {
            "api-key": st.secrets["GUARDIAN_API_KEY"],
            "q": query,
            "page-size": 20,  # Increased for more results
            "show-fields": "headline,trailText"
        }
        try:
            response = requests.get(GUARDIAN_API_URL, params=params, timeout=10)
            return [
                Article(
                    title=item.get("fields", {}).get("headline", ""),
                    description=item.get("fields", {}).get("trailText", ""),
                    url=item.get("webUrl", ""),
                    source="The Guardian"
                ) for item in response.json().get("response", {}).get("results", [])
            ]
        except Exception as e:
            st.error(f"Guardian API Error: {str(e)}")
            return []

class ContentScorer:
    @staticmethod
    def score_article(article: Article, focus_area: str) -> Dict[str, float]:
        prompt = f"""Analyze this article for academic relevance:
        Title: {article.title}
        Description: {article.description}
        Source: {article.source}

        Provide scores (0-1) for:
        1. Relevance to {focus_area} - key_score
        2. Source credibility - credibility_score
        3. Engagement potential - engagement_score

        Return ONLY a JSON object with these three scores.
        Example: {{"key_score": 0.85, "credibility_score": 0.92, "engagement_score": 0.78}}
        """
        
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {st.secrets['DEEPSEEK_API_KEY']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                },
                timeout=20
            )

            if response.status_code != 200:
                return {"key_score": 0, "credibility_score": 0, "engagement_score": 0}

            try:
                response_json = response.json()
                content = json.loads(response_json['choices'][0]['message']['content'])
                return {
                    "key_score": float(content.get("key_score", 0)),
                    "credibility_score": float(content.get("credibility_score", 0)),
                    "engagement_score": float(content.get("engagement_score", 0))
                }
            except:
                return {"key_score": 0, "credibility_score": 0, "engagement_score": 0}
            
        except Exception as e:
            return {"key_score": 0, "credibility_score": 0, "engagement_score": 0}

class ContentGenerator:
    @staticmethod
    def generate_post(article: Article, platform: str) -> str:
        guidelines = {
            "twitter": "280 characters, casual tone, 2-3 hashtags",
            "linkedin": "Professional tone, focus on implications",
            "generic": "300 characters, neutral tone"
        }
        prompt = f"""Create {platform} post:
        Title: {article.title}
        Key Points: {article.description}
        URL: {article.url}
        Style Guidelines: {guidelines.get(platform, guidelines['generic'])}
        """
        
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers={"Authorization": f"Bearer {st.secrets['DEEPSEEK_API_KEY']}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                },
                timeout=15
            )
            return response.json()['choices'][0]['message']['content']
        except:
            return f"Post generation failed for {platform}"

def main():
    if not st.session_state.get("authenticated"):
        password = st.text_input("Enter access password:", type="password")
        if password != st.secrets["APP_PASSWORD"]:
            st.error("Incorrect password")
            st.stop()
        st.session_state.authenticated = True

    st.title("Academic Content Generator")
    
    with st.form("search_form"):
        focus = st.text_input("Research focus area:", "AI in Higher Education")
        query = st.text_input("Search keywords:", "machine learning education")
        if st.form_submit_button("Search Articles"):
            with st.spinner("Fetching articles..."):
                news_articles = NewsAPIClient.fetch_articles(query)
                guardian_articles = GuardianAPIClient.fetch_articles(query)
                all_articles = news_articles + guardian_articles
                
                scorer = ContentScorer()
                for article in all_articles:
                    article.scores = scorer.score_article(article, focus)
                
                st.session_state.articles = sorted(
                    all_articles,
                    key=lambda x: (
                        x.scores.get('key_score', 0) * 0.5 +
                        x.scores.get('credibility_score', 0) * 0.3 +
                        x.scores.get('engagement_score', 0) * 0.2
                    ),
                    reverse=True
                )[:POSTS_TO_SHOW]

    if "articles" in st.session_state:
        st.subheader(f"Top {POSTS_TO_SHOW} Articles")
        selected_posts = []
        
        for idx, article in enumerate(st.session_state.articles):
            with st.expander(f"{idx+1}. {article.title}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Source:** {article.source}")
                    st.write(f"**Relevance:** {article.scores.get('key_score', 0):.2f}")
                    st.write(f"**Credibility:** {article.scores.get('credibility_score', 0):.2f}")
                    st.write(f"**Engagement:** {article.scores.get('engagement_score', 0):.2f}")
                    st.write(f"[Read Article]({article.url})")
                
                with col2:
                    uploaded_image = st.file_uploader(
                        "Upload image for post",
                        type=["jpg", "png", "gif"],
                        key=f"image_{idx}",
                        help=f"Max size: {MAX_IMAGE_SIZE_MB}MB"
                    )
                    if uploaded_image:
                        if uploaded_image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                            st.error(f"Image too large! Max {MAX_IMAGE_SIZE_MB}MB")
                        elif uploaded_image.type not in ALLOWED_IMAGE_TYPES:
                            st.error("Unsupported image format")
                        else:
                            st.image(uploaded_image, use_container_width=True)
                
                platforms = st.multiselect(
                    "Select platforms for this article:",
                    ["Twitter", "LinkedIn", "Generic"],
                    default=["Twitter", "LinkedIn"],
                    key=f"platforms_{idx}"
                )
                
                generated = {}
                if st.button(f"Generate Posts for Article {idx+1}"):
                    generator = ContentGenerator()
                    for platform in platforms:
                        generated[platform] = generator.generate_post(article, platform.lower())
                    st.session_state[f"generated_{idx}"] = generated
                
                if f"generated_{idx}" in st.session_state:
                    st.subheader("Generated Posts")
                    selected = {}
                    for platform, content in st.session_state[f"generated_{idx}"].items():
                        selected[platform] = st.checkbox(
                            f"Select {platform} post",
                            value=True,
                            key=f"select_{platform}_{idx}"
                        )
                        st.text_area(
                            f"{platform} Draft",
                            value=content,
                            height=150,
                            key=f"content_{platform}_{idx}"
                        )
                    
                    selected_posts.append({
                        "title": article.title,
                        "url": article.url,
                        "platforms": {
                            platform: {
                                "content": st.session_state[f"content_{platform}_{idx}"],
                                "selected": selected[platform],
                                "image": uploaded_image.read() if uploaded_image else None
                            }
                            for platform in platforms
                        }
                    })

        if selected_posts:
            st.subheader("Export Selected Posts")
            export_data = []
            
            for post in selected_posts:
                export_data.append(f"# {post['title']}")
                export_data.append(f"URL: {post['url']}")
                for platform, details in post['platforms'].items():
                    if details['selected']:
                        export_data.append(f"\n## {platform} Post")
                        export_data.append(details['content'])
                        if details['image']:
                            img_str = base64.b64encode(details['image']).decode()
                            export_data.append(f"\n![Image](data:image/png;base64,{img_str})")
                export_data.append("\n" + "="*50 + "\n")
            
            st.download_button(
                "Download Selected Posts",
                data="\n".join(export_data),
                file_name="selected_posts.md",
                mime="text/markdown",
                help="Download includes selected posts with images in Markdown format"
            )

if __name__ == "__main__":
    main()
