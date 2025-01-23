# main.py
import os
import json
import time
import base64
import requests
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from io import BytesIO

# Configuration
NEWS_API_URL = "https://newsapi.org/v2/everything"
GUARDIAN_API_URL = "https://content.guardianapis.com/search"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MAX_API_CALLS_PER_DAY = 500
API_CALL_LOG = []
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif"]
MAX_IMAGE_SIZE_MB = 5

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

class SocialMediaManager:
    @staticmethod
    def generate_post(article: Article, platform: str) -> Tuple[str, str]:
        guidelines = {
            "twitter": "280 chars, casual, 2-3 hashtags, include image placeholder [IMAGE]",
            "bluesky": "300 chars, insightful, 1-2 hashtags, include image placeholder [IMAGE]",
            "linkedin": "Professional, focus on implications, include image placeholder [IMAGE]"
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
            post_text = response.json()['choices'][0]['message']['content']
            return post_text, ""
        except:
            return f"Post generation failed", ""

    @staticmethod
    def post_to_twitter(text: str, image: Optional[bytes] = None) -> bool:
        try:
            import tweepy
            
            client = tweepy.Client(
                consumer_key=st.secrets["TWITTER_API_KEY"],
                consumer_secret=st.secrets["TWITTER_API_SECRET"],
                access_token=st.secrets["TWITTER_ACCESS_TOKEN"],
                access_token_secret=st.secrets["TWITTER_ACCESS_SECRET"]
            )
            
            media_ids = []
            if image:
                auth = tweepy.OAuth1UserHandler(
                    st.secrets["TWITTER_API_KEY"],
                    st.secrets["TWITTER_API_SECRET"],
                    st.secrets["TWITTER_ACCESS_TOKEN"],
                    st.secrets["TWITTER_ACCESS_SECRET"]
                )
                api = tweepy.API(auth)
                media = api.media_upload(filename="post_image", file=BytesIO(image))
                media_ids.append(media.media_id)

            client.create_tweet(
                text=text.replace("[IMAGE]", "")[:280],
                media_ids=media_ids if media_ids else None
            )
            return True
        except Exception as e:
            st.error(f"Twitter Error: {str(e)}")
            return False

    @staticmethod
    def post_to_bluesky(text: str, image: Optional[bytes] = None) -> bool:
        try:
            from atproto import Client, models
            client = Client()
            client.login(
                st.secrets["BLUESKY_USERNAME"],
                st.secrets["BLUESKY_PASSWORD"]
            )
            
            embed = None
            if image:
                upload = client.com.atproto.repo.upload_blob(BytesIO(image))
                images = [models.AppBskyEmbedImages.Image(alt="", image=upload.blob)]
                embed = models.AppBskyEmbedImages.Main(images=images)
            
            client.send_post(
                text=text.replace("[IMAGE]", "")[:300],
                embed=embed
            )
            return True
        except Exception as e:
            st.error(f"BlueSky Error: {str(e)}")
            return False

def main():
    if not st.session_state.get("authenticated"):
        password = st.text_input("Enter access password:", type="password")
        if password != st.secrets["APP_PASSWORD"]:
            st.error("Incorrect password")
            st.stop()
        st.session_state.authenticated = True

    st.title("Academic Content Curator")
    
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

    if "articles" in st.session_state:
        st.subheader("Top Articles")
        for idx, article in enumerate(st.session_state.articles):
            with st.expander(f"{idx+1}. {article.title}"):
                st.write(f"**Source:** {article.source}")
                st.write(f"**Relevance:** {article.scores.get('key_score', 0):.2f}")
                st.write(f"**Credibility:** {article.scores.get('credibility_score', 0):.2f}")
                st.write(f"**Engagement:** {article.scores.get('engagement_score', 0):.2f}")
                st.write(f"[Read Article]({article.url})")

        if st.button("Generate Social Posts"):
            smm = SocialMediaManager()
            platform_posts = {}
            for platform in ["twitter", "bluesky", "linkedin"]:
                platform_posts[platform] = [
                    smm.generate_post(article, platform)
                    for article in st.session_state.articles
                ]
            st.session_state.posts = platform_posts
            st.session_state.selected_posts = {}

    if "posts" in st.session_state:
        st.subheader("Social Media Posts")
        edited_posts = []
        uploaded_images = st.session_state.get("uploaded_images", {})
        
        for idx in range(len(st.session_state.articles)):
            st.markdown(f"### Article {idx+1}")
            article_posts = {}
            article_images = {}
            
            for platform in ["twitter", "bluesky", "linkedin"]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    original = st.session_state.posts[platform][idx][0]
                    edited = st.text_area(
                        f"{platform.capitalize()} Draft",
                        value=original,
                        height=150,
                        key=f"{platform}_{idx}"
                    )
                    # Add selection checkbox
                    is_selected = st.checkbox(
                        f"Post to {platform.capitalize()}",
                        value=True,
                        key=f"select_{platform}_{idx}"
                    )
                    st.session_state.selected_posts[f"{platform}_{idx}"] = is_selected
                
                with col2:
                    img_key = f"{platform}_{idx}_image"
                    uploaded_file = st.file_uploader(
                        "Upload Image",
                        type=["jpg", "png", "gif"],
                        key=img_key,
                        help=f"Max size: {MAX_IMAGE_SIZE_MB}MB"
                    )
                    
                    if uploaded_file is not None:
                        if uploaded_file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                            st.error(f"Image too large! Max {MAX_IMAGE_SIZE_MB}MB")
                        elif uploaded_file.type not in ALLOWED_IMAGE_TYPES:
                            st.error("Unsupported image format")
                        else:
                            article_images[platform] = uploaded_file.read()
                            st.image(
                                article_images[platform], 
                                use_container_width=True  # Fixed deprecated parameter
                            )
                    
                    uploaded_images[f"{platform}_{idx}"] = article_images.get(platform, b"")
                
                article_posts[platform] = edited
            
            edited_posts.append(article_posts)
        
        st.session_state.edited_posts = edited_posts
        st.session_state.uploaded_images = uploaded_images
        
        if st.button("Final Approval and Posting"):
            post_enabled = st.toggle("Enable actual social media posting", value=False)
            smm = SocialMediaManager()
            
            success_count = 0
            total_selected = sum(st.session_state.selected_posts.values())
            
            if total_selected > 0:
                progress_bar = st.progress(0)
                current_progress = 0
            
            for idx in range(len(st.session_state.articles)):
                for platform in ["twitter", "bluesky", "linkedin"]:
                    post_key = f"{platform}_{idx}"
                    if st.session_state.selected_posts.get(post_key, False):
                        content = st.session_state.edited_posts[idx][platform]
                        image_data = st.session_state.uploaded_images.get(post_key, b"")
                        
                        if post_enabled:
                            try:
                                if platform == "twitter":
                                    success = smm.post_to_twitter(content, image_data)
                                elif platform == "bluesky":
                                    success = smm.post_to_bluesky(content, image_data)
                                else:
                                    continue
                                
                                if success:
                                    success_count += 1
                                    if total_selected > 0:
                                        current_progress += 1/total_selected
                                        progress_bar.progress(current_progress)
                            except Exception as e:
                                st.error(f"Failed to post to {platform}: {str(e)}")
                        else:
                            st.info(f"Dry Run - {platform.upper()} Post:")
                            st.write(content)
                            if image_data:
                                st.image(image_data, use_container_width=True)
            
            if post_enabled:
                if success_count > 0:
                    st.success(f"Successfully posted {success_count}/{total_selected} selected posts!")
                else:
                    st.warning("No posts were sent. Check your credentials and network connection.")

            # Download all posts regardless of selection
            download_data = []
            for idx, posts in enumerate(st.session_state.edited_posts):
                download_data.append(f"\nArticle {idx+1}")
                for platform, content in posts.items():
                    image_data = st.session_state.uploaded_images.get(f"{platform}_{idx}", b"")
                    download_data.append(f"\n{platform.upper()}:\n{content}")
                    if image_data:
                        img_str = base64.b64encode(image_data).decode()
                        download_data.append(f"\nImage: data:image/png;base64,{img_str[:100]}...")
            
            st.download_button(
                "Download All Posts",
                data="\n".join(download_data),
                file_name="social_posts.txt"
            )

if __name__ == "__main__":
    main()
