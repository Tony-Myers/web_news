# requirements.txt
streamlit
requests
python-dotenv

# main.py
import os
import json
import requests
import streamlit as st
from typing import List, Dict, Optional

# Configuration
NEWS_API_URL = "https://newsapi.org/v2/everything"
GUARDIAN_API_URL = "https://content.guardianapis.com/search"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Article data structure
class Article:
    def __init__(self, title: str, description: str, url: str, source: str):
        self.title = title
        self.description = description
        self.url = url
        self.source = source
        self.scores: Dict[str, float] = {}

# Authentication
def check_password():
    """Basic password authentication"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        password = st.text_input("Enter password:", type="password")
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
        else:
            st.stop()

# API Clients
class NewsAPIClient:
    @staticmethod
    def fetch_articles(query: str) -> List[Article]:
        params = {
            "apiKey": st.secrets["NEWS_API_KEY"],
            "q": query,
            "pageSize": 50,
            "sortBy": "relevancy"
        }
        response = requests.get(NEWS_API_URL, params=params)
        articles = []
        for item in response.json().get("articles", []):
            articles.append(Article(
                title=item.get("title", ""),
                description=item.get("description", ""),
                url=item.get("url", ""),
                source=item.get("source", {}).get("name", "")
            ))
        return articles

class GuardianAPIClient:
    @staticmethod
    def fetch_articles(query: str) -> List[Article]:
        params = {
            "api-key": st.secrets["GUARDIAN_API_KEY"],
            "q": query,
            "page-size": 50,
            "show-fields": "headline,trailText"
        }
        response = requests.get(GUARDIAN_API_URL, params=params)
        articles = []
        for item in response.json().get("response", {}).get("results", []):
            articles.append(Article(
                title=item.get("fields", {}).get("headline", ""),
                description=item.get("fields", {}).get("trailText", ""),
                url=item.get("webUrl", ""),
                source="The Guardian"
            ))
        return articles

# Content Scoring
class ContentScorer:
    @staticmethod
    def score_article(article: Article, focus_area: str) -> Dict[str, float]:
        """Score article using DeepSeek API"""
        prompt = f"""
        Analyze this article for academic relevance:
        Title: {article.title}
        Description: {article.description}
        Source: {article.source}

        Provide scores (0-1) for:
        1. Relevance to {focus_area}
        2. Source credibility
        3. Engagement potential

        Return ONLY a JSON object with scores and brief explanation.
        """
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {st.secrets['DEEPSEEK_API_KEY']}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
        )
        
        try:
            scores = json.loads(response.json()['choices'][0]['message']['content'])
            return scores
        except:
            return {"relevance": 0, "credibility": 0, "engagement": 0}

# Post Generation
class SocialMediaGenerator:
    @staticmethod
    def generate_post(article: Article, platform: str) -> str:
        """Generate platform-specific post using DeepSeek"""
        prompt = f"""
        Create a {platform} post about this article:
        Title: {article.title}
        Key points: {article.description}
        URL: {article.url}

        Requirements:
        - {SocialMediaGenerator._platform_guidelines(platform)}
        - Sound like a thoughtful academic
        - Include relevant hashtags
        - Keep URL as-is
        """
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {st.secrets['DEEPSEEK_API_KEY']}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }
        )
        
        return response.json()['choices'][0]['message']['content']
    
    @staticmethod
    def _platform_guidelines(platform: str) -> str:
        guidelines = {
            "twitter": "280 characters max, casual tone",
            "bluesky": "300 characters max, concise but insightful",
            "linkedin": "Professional tone, highlight research implications"
        }
        return guidelines.get(platform, "")

# Streamlit UI
def main():
    check_password()
    st.title("Academic Content Aggregator")
    
    # User input
    focus_area = st.text_input("Enter research focus area:", "sport and health research")
    query = st.text_input("Search query:", "AI in higher education")
    
    if st.button("Search Articles"):
        # Fetch articles
        news_articles = NewsAPIClient.fetch_articles(query)
        guardian_articles = GuardianAPIClient.fetch_articles(query)
        all_articles = news_articles + guardian_articles
        
        # Score articles
        scorer = ContentScorer()
        for article in all_articles:
            scores = scorer.score_article(article, focus_area)
            article.scores = scores
        
        # Sort by combined score
        sorted_articles = sorted(all_articles, 
                               key=lambda x: (x.scores.get('relevance', 0) + 
                                             x.scores.get('credibility', 0) + 
                                             x.scores.get('engagement', 0)), 
                               reverse=True)
        
        # Select top 4
        top_articles = sorted_articles[:4]
        st.session_state.top_articles = top_articles
        
        # Display results
        st.subheader("Top Articles")
        for idx, article in enumerate(top_articles, 1):
            with st.expander(f"{idx}. {article.title}"):
                st.write(f"**Source:** {article.source}")
                st.write(f"**Relevance:** {article.scores.get('relevance', 0):.2f}")
                st.write(f"**Credibility:** {article.scores.get('credibility', 0):.2f}")
                st.write(f"**Engagement:** {article.scores.get('engagement', 0):.2f}")
                st.write(f"[Read article]({article.url})")
        
        # Generate posts
        generator = SocialMediaGenerator()
        posts = {}
        for platform in ["twitter", "bluesky", "linkedin"]:
            posts[platform] = [generator.generate_post(article, platform) for article in top_articles]
        
        st.session_state.posts = posts
        st.session_state.show_posts = True
    
    if st.session_state.get('show_posts', False):
        st.subheader("Generated Social Media Posts")
        edited_posts = []
        
        for idx, article in enumerate(st.session_state.top_articles):
            st.markdown(f"### Article {idx+1}: {article.title}")
            
            platform_posts = {}
            for platform in ["twitter", "bluesky", "linkedin"]:
                original_post = st.session_state.posts[platform][idx]
                edited = st.text_area(
                    f"{platform.capitalize()} Post", 
                    value=original_post,
                    height=150,
                    key=f"{platform}_{idx}"
                )
                platform_posts[platform] = edited
            
            edited_posts.append(platform_posts)
        
        st.session_state.edited_posts = edited_posts
        
        if st.button("Approve and Download Posts"):
            # Prepare download data
            download_content = ""
            for idx, posts in enumerate(st.session_state.edited_posts):
                download_content += f"Article {idx+1} Posts:\n"
                for platform, content in posts.items():
                    download_content += f"\n{platform.upper()}:\n{content}\n"
                download_content += "\n" + "-"*50 + "\n"
            
            # Offer download
            st.download_button(
                label="Download Approved Posts",
                data=download_content,
                file_name="social_media_posts.txt",
                mime="text/plain"
            )

if __name__ == "__main__":
    main()
