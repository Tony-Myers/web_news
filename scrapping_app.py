# File: scrapping_app.py
import streamlit as st
import requests
from typing import List, Dict, Any


# --- Utility Functions ---
def fetch_google_results(query: str) -> List[Dict[str, Any]]:
    """
    Fetches results from Google Custom Search API.
    """
    try:
        params = {
            "key": st.secrets["api_keys"]["google_api_key"],
            "cx": st.secrets["api_keys"]["google_cx"],
            "q": query,
        }
        response = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
        response.raise_for_status()
        items = response.json().get("items", [])
        return [{"title": item["title"], "url": item["link"], "description": item.get("snippet", "")} for item in items]
    except Exception as e:
        st.error(f"Error fetching results from Google: {e}")
        return []


def fetch_newsapi_results(query: str) -> List[Dict[str, Any]]:
    """
    Fetches results from NewsAPI.
    """
    try:
        headers = {"Authorization": f"Bearer {st.secrets['api_keys']['newsapi_key']}"}
        params = {"q": query, "language": "en"}
        response = requests.get("https://newsapi.org/v2/everything", headers=headers, params=params)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        return [{"title": article["title"], "url": article["url"], "description": article.get("description", "")} for article in articles]
    except Exception as e:
        st.error(f"Error fetching results from NewsAPI: {e}")
        return []


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
    base_post = f"This is interesting: '{content_item['title']}'\nRead more: {content_item['url']}"
    if platform == "LinkedIn":
        return f"{base_post}\n\n[LinkedIn Placeholder Image]"
    elif platform == "BlueSky":
        return f"{base_post}\n\n[BlueSky Placeholder Image]"
    elif platform == "X":
        return f"{base_post}\n\n[X Placeholder Image]"
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def check_password():
    """
    Checks if the user-provided password matches the stored password.
    """
    try:
        correct_pw = st.secrets["general"]["APP_PASSWORD"]
        if "password_correct" not in st.session_state:
            st.session_state["password_correct"] = False

        entered_pw = st.sidebar.text_input("Enter your password:", type="password")
        if entered_pw == correct_pw:
            st.session_state["password_correct"] = True
            return True
        else:
            st.session_state["password_correct"] = False
            return False
    except KeyError:
        st.error("Missing `APP_PASSWORD` in secrets.toml under [general]!")
        st.stop()


# --- Main App ---
def main():
    st.title("Content Scraper and Poster")

    # 1. Check password first
    if not check_password():
        st.warning("Please enter the correct password in the sidebar.")
        st.stop()

    # 2. Input for content scraping
    query = st.text_input("Enter search query:", "sports analytics")
    st.write("Search Query:", query)

    if st.button("Fetch and Generate Posts"):
        try:
            # Fetch results from Google and NewsAPI
            google_results = fetch_google_results(query)
            newsapi_results = fetch_newsapi_results(query)

            # Combine and rate results
            combined_results = google_results + newsapi_results
            rated_content = rate_content(combined_results)

            # Select top 3 items
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

        except Exception as e:
            st.error(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
