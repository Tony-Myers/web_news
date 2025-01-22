# File: scrapping_app.py

import streamlit as st
import requests
from typing import List, Dict, Any
from subprocess import run


# --- Utility Functions ---
def scrape_content_from_api(api_url: str, headers: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """
    Queries the external aggregator or API to return data.
    """
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        return response.json().get("items", [])
    else:
        raise ValueError(f"Failed to fetch content: {response.status_code} {response.reason}")


def rate_content(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Applies a scoring algorithm to rate content relevance.
    """
    keywords = ["Bayesian", "sports science", "health analytics", "peer-reviewed"]
    for item in items:
        score = 0
        title = item.get("title", "").lower()
        description = item.get("description", "").lower()
        for keyword in keywords:
            if keyword.lower() in title or keyword.lower() in description:
                score += 10
        item["score"] = score
    return sorted(items, key=lambda x: x.get("score", 0), reverse=True)


def select_top_content(rated_items: List[Dict[str, Any]], n: int = 3) -> List[Dict[str, Any]]:
    """
    Picks the top N items based on score.
    """
    return rated_items[:n]


def generate_social_posts(content_item: Dict[str, Any], platform: str) -> str:
    """
    Returns a text snippet (plus an image placeholder reference) for LinkedIn, BlueSky, or X.
    """
    base_post = f"Check out this fascinating piece: '{content_item['title']}'\nRead more: {content_item['url']}"
    if platform == "LinkedIn":
        return f"{base_post}\n\n[LinkedIn Placeholder Image]"
    elif platform == "BlueSky":
        return f"{base_post}\n\n[BlueSky Placeholder Image]"
    elif platform == "X":
        return f"{base_post}\n\n[X Placeholder Image]"
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def post_to_platform(post_text: str, platform: str, credentials: Dict[str, str]):
    """
    Sends the post to the platform using appropriate APIs.
    """
    if platform == "LinkedIn":
        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {credentials['LinkedIn']}",
            "Content-Type": "application/json"
        }
        payload = {"content": {"description": post_text}}
        response = requests.post(url, headers=headers, json=payload)
        return response.status_code, response.reason

    elif platform == "BlueSky":
        # Use Node.js script to post on BlueSky
        dotenv_content = f"""BLUESKY_USERNAME={credentials['BlueSky_Username']}
BLUESKY_PASSWORD={credentials['BlueSky_Password']}
"""
        with open(".env", "w") as env_file:
            env_file.write(dotenv_content)

        bluesky_script = f"""
import {{ BskyAgent }} from '@atproto/api';
import * as dotenv from 'dotenv';

dotenv.config();

const agent = new BskyAgent({{ service: 'https://bsky.social' }});

async function main() {{
    await agent.login({{ identifier: process.env.BLUESKY_USERNAME, password: process.env.BLUESKY_PASSWORD }});
    await agent.post({{ text: `{post_text}` }});
    console.log("Posted to BlueSky!");
}}

main();
"""
        with open("bluesky_post.js", "w") as js_file:
            js_file.write(bluesky_script)

        # Run Node.js script
        result = run(["node", "bluesky_post.js"])
        return result.returncode, "BlueSky post simulated."

    elif platform == "X":
        url = "https://api.twitter.com/2/tweets"
        headers = {
            "Authorization": f"Bearer {credentials['X_Bearer_Token']}",
            "Content-Type": "application/json"
        }
        payload = {"text": post_text}
        response = requests.post(url, headers=headers, json=payload)
        return response.status_code, response.reason

    else:
        raise ValueError(f"Unsupported platform: {platform}")


def check_password():
    """
    Checks if the user-provided password matches the stored password.
    """
    try:
        # If you stored your password under [general] in secrets.toml, access it like this:
        correct_pw = st.secrets["general"]["APP_PASSWORD"]

        # We'll store a boolean in session_state to remember if the user is logged in
        if "password_correct" not in st.session_state:
            st.session_state["password_correct"] = False

        # Prompt user for password
        entered_pw = st.sidebar.text_input("Enter your password:", type="password")

        if entered_pw == correct_pw:
            st.session_state["password_correct"] = True
            return True
        else:
            st.session_state["password_correct"] = False
            return False
    except KeyError as e:
        st.error("Missing `APP_PASSWORD` in secrets.toml under [general]!")
        st.stop()


# --- Main App ---
def main():
    st.title("Password-Protected Streamlit App")

    # 1. Check password first
    if not check_password():
        st.warning("Please enter the correct password in the sidebar.")
        st.stop()  # This prevents the rest of the app from rendering

    # 2. Input for content scraping
    api_url = st.text_input("Enter API URL for content scraping:", "https://api.example.com/content")
    st.write("Using API URL:", api_url)

    if st.button("Scrape and Generate Posts"):
        try:
            # Scrape content
            headers = {"Authorization": f"Bearer {st.secrets['api_keys']['aggregator_api_key']}"}
            raw_content = scrape_content_from_api(api_url, headers=headers)

            # Rate and select content
            rated_content = rate_content(raw_content)
            top_content = select_top_content(rated_content, n=3)

            # Generate social posts
            platforms = ["LinkedIn", "BlueSky", "X"]
            all_posts = []

            for item in top_content:
                for platform in platforms:
                    post = generate_social_posts(item, platform)
                    all_posts.append({"platform": platform, "content": post})

            # Display posts for user verification
            for idx, post in enumerate(all_posts, 1):
                st.subheader(f"Post {idx}: {post['platform']}")
                st.text_area("Content", post["content"], height=150)

            if st.button("Approve and Post"):
                for post in all_posts:
                    status, message = post_to_platform(post["content"], post["platform"], st.secrets["api_keys"])
                    st.write(f"Posted to {post['platform']}: {status} - {message}")
        except Exception as e:
            st.error(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
