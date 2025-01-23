# main.py
import os
import json
import time
import requests
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional

# Configuration
NEWS_API_URL = "https://newsapi.org/v2/everything"
GUARDIAN_API_URL = "https://content.guardianapis.com/search"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MAX_API_CALLS_PER_DAY = 500
API_CALL_LOG = []

# Rate limiter decorator
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

# Data classes
class Article:
    def __init__(self, title: str, description: str, url: str, source: str):
        self.title = title
        self.description = description
        self.url = url
        self.source = source
        self.scores: Dict[str, float] = {}

# API Clients
class NewsAPIClient:
    @staticmethod
    @rate_limited(MAX_API_CALLS_PER_DAY)
    def fetch_articles(query: str) -> List[Article]:
        time.sleep(1)
        params = {
            "apiKey": st.secrets["NEWS_API_KEY"],
            "q": query,
            "pageSize": 10,
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
            "page-size": 10,
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

# Content Processing
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

            # Debugging output
            if response.status_code != 200:
                st.error(f"DeepSeek API Error: Status {response.status_code}")
                return {"key_score": 0, "credibility_score": 0, "engagement_score": 0}

            try:
                response_json = response.json()
                content = json.loads(response_json['choices'][0]['message']['content'])
                return {
                    "key_score": float(content.get("key_score", 0)),
                    "credibility_score": float(content.get("credibility_score", 0)),
                    "engagement_score": float(content.get("engagement_score", 0))
                }
            except json.JSONDecodeError:
                st.error("Failed to parse DeepSeek response")
                return {"key_score": 0, "credibility_score": 0, "engagement_score": 0}
            
        except Exception as e:
            st.error(f"DeepSeek API Error: {str(e)}")
            return {"key_score": 0, "credibility_score": 0, "engagement_score": 0}

class SocialMediaManager:
    @staticmethod
    def generate_post(article: Article, platform: str) -> str:
        guidelines = {
            "twitter": "280 chars, casual, 2-3 hashtags",
            "bluesky": "300 chars, insightful, 1-2 hashtags",
            "linkedin": "Professional, focus on implications"
        }
        prompt = f"""Create {platform} post:
        Title: {article.title}
        Points: {article.description}
        URL: {article.url}
        Style: {guidelines.get(platform, '')}
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
        except Exception as e:
            return f"Post generation failed: {str(e)}"

    @staticmethod
    def post_to_twitter(text: str) -> bool:
        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=st.secrets["TWITTER_API_KEY"],
                consumer_secret=st.secrets["TWITTER_API_SECRET"],
                access_token=st.secrets["TWITTER_ACCESS_TOKEN"],
                access_token_secret=st.secrets["TWITTER_ACCESS_SECRET"]
            )
            client.create_tweet(text=text[:280])
            return True
        except Exception as e:
            st.error(f"Twitter Error: {str(e)}")
            return False

    @staticmethod
    def post_to_bluesky(text: str) -> bool:
        try:
            from atproto import Client
            client = Client()
            client.login(
                st.secrets["BLUESKY_USERNAME"],
                st.secrets["BLUESKY_PASSWORD"]
            )
            client.send_post(text[:300])
            return True
        except Exception as e:
            st.error(f"BlueSky Error: {str(e)}")
            return False

# Streamlit UI
def main():
    # Authentication
    if not st.session_state.get("authenticated"):
        password = st.text_input("Enter access password:", type="password")
        if password != st.secrets["APP_PASSWORD"]:
            st.error("Incorrect password")
            st.stop()
        st.session_state.authenticated = True

    st.title("Academic Content Curator")
    
    # Search Interface
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
                )[:4]

    # Results Display
    if "articles" in st.session_state:
        st.subheader("Top Articles")
        posts = {}
        for idx, article in enumerate(st.session_state.articles):
            with st.expander(f"{idx+1}. {article.title}"):
                st.write(f"**Source:** {article.source}")
                st.write(f"**Relevance Score:** {article.scores.get('key_score', 0):.2f}")
                st.write(f"**Credibility Score:** {article.scores.get('credibility_score', 0):.2f}")
                st.write(f"**Engagement Score:** {article.scores.get('engagement_score', 0):.2f}")
                st.write(f"[Read Article]({article.url})")

        # Post Generation
        if st.button("Generate Social Posts"):
            smm = SocialMediaManager()
            platform_posts = {}
            for platform in ["twitter", "bluesky", "linkedin"]:
                platform_posts[platform] = [
                    smm.generate_post(article, platform)
                    for article in st.session_state.articles
                ]
            st.session_state.posts = platform_posts

    # Post Editing & Approval
    if "posts" in st.session_state:
        st.subheader("Social Media Posts")
        edited_posts = []
        
        for idx in range(len(st.session_state.articles)):
            st.markdown(f"### Article {idx+1}")
            article_posts = {}
            for platform in ["twitter", "bluesky", "linkedin"]:
                original = st.session_state.posts[platform][idx]
                edited = st.text_area(
                    f"{platform.capitalize()} Draft",
                    value=original,
                    height=150,
                    key=f"{platform}_{idx}"
                )
                article_posts[platform] = edited
            edited_posts.append(article_posts)
        
        st.session_state.edited_posts = edited_posts
        
        # Posting Control
        if st.button("Final Approval"):
            post_enabled = st.toggle("Enable actual posting", False)
            smm = SocialMediaManager()
            
            for idx, posts in enumerate(st.session_state.edited_posts):
                for platform, content in posts.items():
                    if post_enabled:
                        if platform == "twitter":
                            success = smm.post_to_twitter(content)
                        elif platform == "bluesky":
                            success = smm.post_to_bluesky(content)
                        if success:
                            st.success(f"Posted to {platform.upper()}!")
                    else:
                        st.info(f"{platform.upper()} Preview:\n{content}")
            
            # Download option
            download_data = "\n\n".join(
                f"{platform.upper()}:\n{post}"
                for posts in st.session_state.edited_posts
                for platform, post in posts.items()
            )
            st.download_button(
                "Download Posts",
                data=download_data,
                file_name="social_posts.txt"
            )

if __name__ == "__main__":
    main()
