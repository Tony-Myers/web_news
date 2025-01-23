# main.py
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

# Rate limiter decorator and other existing classes remain the same until SocialMediaManager

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
        except Exception as e:
            return f"Post generation failed: {str(e)}", ""

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
            
            # Upload media if image exists
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

            # Create tweet with media
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
            
            # Upload image if present
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

# Updated Streamlit UI Section
def main():
    # Authentication and previous setup remains the same until post editing
    
    # Post Editing & Approval with Image Upload
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
                
                with col2:
                    img_key = f"{platform}_{idx}_image"
                    uploaded_file = st.file_uploader(
                        "Upload Image",
                        type=["jpg", "png", "gif"],
                        key=img_key,
                        help=f"Max size: {MAX_IMAGE_SIZE_MB}MB, Recommended ratio: 16:9"
                    )
                    
                    # Validate image
                    if uploaded_file is not None:
                        if uploaded_file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                            st.error(f"Image too large! Max {MAX_IMAGE_SIZE_MB}MB")
                        elif uploaded_file.type not in ALLOWED_IMAGE_TYPES:
                            st.error("Unsupported image format")
                        else:
                            article_images[platform] = uploaded_file.read()
                            st.image(article_images[platform], use_column_width=True)
                    
                    # Store images in session state
                    uploaded_images[f"{platform}_{idx}"] = article_images.get(platform, b"")
                
                article_posts[platform] = edited
            
            edited_posts.append(article_posts)
        
        st.session_state.edited_posts = edited_posts
        st.session_state.uploaded_images = uploaded_images
        
        # Posting Control
        if st.button("Final Approval"):
            post_enabled = st.toggle("Enable actual posting", False)
            smm = SocialMediaManager()
            
            for idx, posts in enumerate(st.session_state.edited_posts):
                for platform, content in posts.items():
                    image_data = st.session_state.uploaded_images.get(f"{platform}_{idx}", b"")
                    
                    if post_enabled:
                        if platform == "twitter":
                            success = smm.post_to_twitter(content, image_data)
                        elif platform == "bluesky":
                            success = smm.post_to_bluesky(content, image_data)
                        if success:
                            st.success(f"Posted to {platform.upper()}!")
                    else:
                        st.info(f"{platform.upper()} Preview:")
                        st.write(content)
                        if image_data:
                            st.image(image_data, use_column_width=True)
            
            # Download option with images
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
                "Download Posts with Images",
                data="\n".join(download_data),
                file_name="social_posts_with_images.txt"
            )

if __name__ == "__main__":
    main()
