import streamlit as st
import requests
import json
import logging
import random
import re
import time
import os
from pathlib import Path
from typing import List, Dict
from urllib.parse import urlparse
from dotenv import load_dotenv

# We assume you have the same constants, data structures, 
# and function definitions as before. For brevity, we'll show 
# only partial code below. Make sure to include everything 
# (scrape_content_from_api, get_fallback_data, rate_content, etc.)

# Example from your code, slightly truncated:
NEWS_API_URL = "https://newsapi.org/v2/everything"
USE_RANDOM_VARIATION = False
CREDIBLE_SOURCES = [
    'nih.gov', 'bmj.com', 'jamanetwork.com',
    'sportsscience.org', 'springer.com', 'bbc.com',
    'bbc.co.uk', 'theguardian.com', 'newscientist.com'
]
KEYWORD_WEIGHTS = {
    'sports science': 12,
    'health analytics': 15,
    'statistical modeling': 10,
    'peer-reviewed': 20,
    'clinical trial': 18
}
MAX_PAGES = 2
API_CALL_INTERVAL = 2

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
SOCIAL_MEDIA_CREDS = {
    'linkedin': os.getenv("LINKEDIN_TOKEN"),
    'bluesky': os.getenv("BLUESKY_TOKEN"),
    'twitter': os.getenv("TWITTER_TOKEN")
}

# For demonstration, we'll reduce logging to warnings to avoid clutter
logging.basicConfig(level=logging.WARNING)

############################
# PASSWORD PROTECTION LOGIC
############################

def check_password():
    """
    Checks if the user-entered password matches the APP_PASSWORD
    from st.secrets. Returns True if correct, else False.
    """
    # If you stored your password under [general] in secrets.toml,
    # access it like this:
    correct_pw = st.secrets["general"]["APP_PASSWORD"]

    # We'll store a boolean in session_state to remember if user is logged in
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # The user types a password into the sidebar
    entered_pw = st.sidebar.text_input("Enter App Password:", type="password")
    if st.sidebar.button("Submit Password"):
        if entered_pw == correct_pw:
            st.session_state["password_correct"] = True
        else:
            st.error("Incorrect password.")

    return st.session_state["password_correct"]

############################
# YOUR EXISTING HELPER FUNCTIONS
############################

def get_domain(url: str) -> str:
    # ... as before
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return ''
        domain = result.netloc.lower().replace('www.', '').split(':')[0]
        return domain if '.' in domain else ''
    except (AttributeError, ValueError):
        return ''

def get_fallback_data() -> List[Dict[str, str]]:
    # ... as before
    return [{
        'title': 'Fallback Article',
        'description': 'Example fallback content.',
        'url': 'https://example.com',
        'source_domain': 'example.com'
    }]

def scrape_content_from_api(include_only_credible: bool = False) -> List[Dict[str, str]]:
    """
    Simplified example of your scraping code with pagination.
    Insert your real logic here.
    """
    # ... or the version from your code with pagination
    articles = []
    # For brevity, just return the fallback or do a small test
    # real code would do requests.get(...) etc.
    return get_fallback_data()

def rate_content(items: List[Dict[str, str]]) -> List[Dict[str, float]]:
    """
    Scores content. Insert your real logic here.
    """
    rated = []
    for item in items:
        score = 0
        text = (item['title'] + " " + item['description']).lower()
        for kw, wt in KEYWORD_WEIGHTS.items():
            pattern = rf"\b{re.escape(kw.lower())}\b"
            if re.search(pattern, text):
                score += wt
        # Domain credibility check
        if item['source_domain'] in CREDIBLE_SOURCES:
            score += 30
        # Optional random variation
        if USE_RANDOM_VARIATION:
            score += random.randint(-5, 10)
        final_score = max(0, min(100, round(score, 1)))
        rated.append({**item, 'score': final_score})
    return rated

def generate_social_posts(content_item: Dict[str, str], platform: str) -> Dict[str, str]:
    """
    Dummy post generation. Insert your real logic.
    """
    # This is very simplified:
    text = f"{content_item['title']}\nURL: {content_item['url']}"
    # Optionally add hashtags, check length, etc.
    return {"platform": platform, "content": text, "image": "img/default.png"}

def post_to_platform(post_text: str, platform: str, credentials: str) -> bool:
    st.write(f"**Simulated posting to {platform.upper()}:**\n{post_text}")
    # Real logic would do an API call using credentials
    return True

############################
# STREAMLIT APP LOGIC
############################

def main():
    st.title("Password-Protected Streamlit App")

    # 1. Check password first
    if not check_password():
        st.warning("Please enter the correct password in the sidebar.")
        st.stop()  # This prevents the rest of the app from rendering

    st.success("Access granted!")

    # 2. Once password is correct, user can run the pipeline
    st.write("Click the button below to scrape & rate articles, then generate top posts.")
    
    if st.button("Run Pipeline"):
        # a) Scrape
        articles = scrape_content_from_api(include_only_credible=False)
        st.write(f"Fetched {len(articles)} articles.")

        # b) Rate
        rated = rate_content(articles)
        st.write("**Rated Articles**:")
        st.json(rated)

        # c) Sort & pick top 3
        top_items = sorted(rated, key=lambda x: x['score'], reverse=True)[:3]

        # d) Generate posts
        platforms = ["linkedin", "bluesky", "twitter"]
        all_posts = []
        for item in top_items:
            for p in platforms:
                post_info = generate_social_posts(item, p)
                all_posts.append({**post_info, "score": item["score"]})

        # e) Display posts
        st.subheader("Generated Posts")
        for idx, post in enumerate(all_posts, 1):
            st.markdown(f"**Post {idx} - {post['platform'].upper()} (score: {post['score']})**")
            st.write(post['content'])
            st.image(post['image'])

        # f) Prompt user to confirm and simulate posting
        if st.button("Approve & Simulate Posting"):
            for post in all_posts:
                creds = SOCIAL_MEDIA_CREDS.get(post["platform"], "")
                post_to_platform(post_text=post["content"], platform=post["platform"], credentials=creds)
            st.success("All posts simulated!")

if __name__ == "__main__":
    main()
