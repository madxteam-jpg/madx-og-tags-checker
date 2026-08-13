import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import pandas as pd

# Page configuration
st.set_page_config(page_title="Multi-URL OG & Twitter Checker", page_icon="🔍", layout="wide")

st.title("🔍 Multi-URL Open Graph & Twitter Card Inspector")
st.write("Inspect, validate, and preview Open Graph and Twitter Card meta tags across multiple URLs.")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("⚙️ Inspector Options")
check_twitter = st.sidebar.checkbox(
    "Include Twitter Card inspection", 
    value=True, 
    help="Uncheck if the target sites do not implement Twitter-specific tags."
)

# Multi-line input widget
urls_input = st.text_area(
    "Enter Web URLs (one per line):",
    placeholder="https://example.com\nhttps://streamlit.io\nhttps://github.com",
    height=150
)


def validate_metadata(og_tags, twitter_tags, include_twitter):
    """Validates presence of required and recommended tags."""
    og_requirements = {
        "og:title": ("Required", "Main title of your page as it should appear in social feeds."),
        "og:type": ("Required", "Type of content (e.g., 'website', 'article')."),
        "og:image": ("Required", "Image URL to represent your content."),
        "og:url": ("Required", "Canonical URL used as the permanent ID for the page."),
        "og:description": ("Recommended", "A concise snippet summarizing the content.")
    }

    og_issues = []
    twitter_issues = []

    # Validate Open Graph
    for tag, (level, desc) in og_requirements.items():
        if tag not in og_tags or not og_tags[tag].strip():
            og_issues.append({"tag": tag, "level": level, "description": desc})

    # Validate Twitter (only if requested)
    if include_twitter:
        twitter_requirements = {
            "twitter:card": ("Required", "Defines the card layout (e.g., 'summary', 'summary_large_image')."),
            "twitter:title": ("Recommended", "Title for X. Falls back to og:title if absent."),
            "twitter:description": ("Recommended", "Description for X. Falls back to og:description if absent."),
            "twitter:image": ("Recommended", "Image for X. Falls back to og:image if absent.")
        }

        fallback_map = {
            "twitter:title": "og:title",
            "twitter:description": "og:description",
            "twitter:image": "og:image"
        }

        for tag, (level, desc) in twitter_requirements.items():
            tag_missing = tag not in twitter_tags or not twitter_tags[tag].strip()
            
            if tag == "twitter:card" and tag_missing:
                twitter_issues.append({"tag": tag, "level": "Required", "description": desc})
            elif tag_missing:
                fallback_tag = fallback_map.get(tag)
                has_fallback = fallback_tag in og_tags and bool(og_tags[fallback_tag].strip())
                
                if not has_fallback:
                    twitter_issues.append({"tag": tag, "level": level, "description": desc})

    return og_issues, twitter_issues


def get_status_badge(issues):
    """Generates a status badge based on issue severity."""
    if not issues:
        return "✅ Complete"
    
    required_missing = any(i["level"] == "Required" for i in issues)
    if required_missing:
        return f"❌ Missing Required ({len(issues)})"
    return f"⚠️ Missing Recommended ({len(issues)})"


if st.button("Inspect All URLs", type="primary"):
    url_list = [line.strip() for line in urls_input.splitlines() if line.strip()]

    if not url_list:
        st.warning("Please enter at least one valid URL.")
    else:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        processed_data = []

        # --- STEP 1: FETCH & PARSE ALL DATA ---
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, raw_url in enumerate(url_list):
            status_text.text(f"Processing URL {idx+1}/{len(url_list)}: {raw_url}")
            progress_bar.progress((idx + 1) / len(url_list))

            url = raw_url if raw_url.startswith(("http://", "https://")) else "https://" + raw_url
            
            result_item = {
                "raw_url": raw_url,
                "url": url,
                "error": None,
                "og_tags": {},
                "twitter_tags": {},
                "og_issues": [],
                "twitter_issues": []
            }

            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                meta_tags = soup.find_all("meta")

                for tag in meta_tags:
                    key = tag.get("property") or tag.get("name") or ""
                    key = key.lower().strip()
                    content = tag.get("content", "").strip()

                    if key.startswith("og:"):
                        result_item["og_tags"][key] = content
                    elif check_twitter and key.startswith("twitter:"):
                        result_item["twitter_tags"][key] = content

                og_issues, twitter_issues = validate_metadata(
                    result_item["og_tags"], 
                    result_item["twitter_tags"], 
                    check_twitter
                )
                
                result_item["og_issues"] = og_issues
                result_item["twitter_issues"] = twitter_issues

            except Exception as e:
                result_item["error"] = str(e)

            processed_data.append(result_item)

        status_text.empty()
        progress_bar.empty()

        # --- STEP 2: SUMMARY TABLE ---
        st.subheader("📊 Summary Results")
        
        summary_rows = []
        for item in processed_data:
            if item["error"]:
                row = {
                    "URL": item["url"],
                    "OG Status": "🚨 Request Failed",
                    "Overall Status": "Failed"
                }
                if check_twitter:
                    row["Twitter Status"] = "🚨 Request Failed"
            else:
                og_badge = get_status_badge(item["og_issues"])
                total_issues = len(item["og_issues"]) + len(item["twitter_issues"])
                
                row = {
                    "URL": item["url"],
                    "OG Status": og_badge,
                    "Total Issues": total_issues
                }
                if check_twitter:
                    row["Twitter Status"] = get_status_badge(item["twitter_issues"])
                
            summary_rows.append(row)

        df_summary = pd.DataFrame(summary_rows)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)

        st.divider()

        # --- STEP 3: DETAILED INSPECTION ACCORDIONS ---
        st.subheader("🔎 Detailed Breakdown")
        for idx, item in enumerate(processed_data, start=1):
            url = item["url"]
            is_expanded = len(processed_data) == 1

            with st.expander(f"🌐 #{idx}: {url}", expanded=is_expanded):
                if item["error"]:
                    st.error(f"Failed to fetch or parse this URL: {item['error']}")
                else:
                    og_tags = item["og_tags"]
                    twitter_tags = item["twitter_tags"]
                    og_issues = item["og_issues"]
                    twitter_issues = item["twitter_issues"]

                    tab_previews, tab_audit, tab_raw = st.tabs(["🖼️ Previews", "⚠️ Audit & Validation", "📋 Raw Tags"])

                    # --- TAB 1: PREVIEWS ---
                    with tab_previews:
                        if check_twitter:
                            col1, col2 = st.columns(2)
                        else:
                            col1 = st.container()

                        with col1:
                            st.subheader("Facebook / Open Graph")
                            with st.container(border=True):
                                og_img = og_tags.get("og:image")
                                if og_img:
                                    st.image(og_img, use_container_width=True)
                                else:
                                    st.info("🖼️ No `og:image` set.")

                                site_name = og_tags.get("og:site_name", urlparse(url).netloc)
                                st.caption(site_name.upper())
                                st.markdown(f"### {og_tags.get('og:title', 'No Title Set')}")
                                st.write(og_tags.get("og:description", "No description set."))

                        if check_twitter:
                            with col2:
                                st.subheader("X / Twitter Card")
                                card_type = twitter_tags.get("twitter:card", "summary (default fallback)")
                                tw_img = twitter_tags.get("twitter:image") or og_tags.get("og:image")
                                tw_title = twitter_tags.get("twitter:title") or og_tags.get("og:title", "No Title Set")
                                tw_desc = twitter_tags.get("twitter:description") or og_tags.get("og:description", "No description set.")

                                with st.container(border=True):
                                    st.caption(f"CARD TYPE: `{card_type}`")
                                    if tw_img:
                                        st.image(tw_img, use_container_width=True)
                                    else:
                                        st.info("🖼️ No image set.")

                                    st.markdown(f"### {tw_title}")
                                    st.write(tw_desc)
                                    st.caption(urlparse(url).netloc)

                    # --- TAB 2: AUDIT & VALIDATION ---
                    with tab_audit:
                        total_issues = len(og_issues) + len(twitter_issues)
                        if total_issues == 0:
                            st.success("🎉 All checked core tags are properly configured!")
                        else:
                            st.info(f"Found {total_issues} metadata warning(s) or missing tag(s).")

                        if check_twitter:
                            val_col1, val_col2 = st.columns(2)
                        else:
                            val_col1 = st.container()

                        with val_col1:
                            st.subheader("Open Graph Audit")
                            if not og_issues:
                                st.success("Open Graph requirements met.")
                            else:
                                for issue in og_issues:
                                    icon = "🔴" if issue["level"] == "Required" else "🟡"
                                    st.warning(f"{icon} **Missing `{issue['tag']}`** ({issue['level']})\n\n_{issue['description']}_")

                        if check_twitter:
                            with val_col2:
                                st.subheader("Twitter Card Audit")
                                if not twitter_issues:
                                    st.success("Twitter Card requirements met.")
                                else:
                                    for issue in twitter_issues:
                                        icon = "🔴" if issue["level"] == "Required" else "🟡"
                                        st.warning(f"{icon} **Missing `{issue['tag']}`** ({issue['level']})\n\n_{issue['description']}_")

                    # --- TAB 3: RAW TAGS ---
                    with tab_raw:
                        if check_twitter:
                            raw_col1, raw_col2 = st.columns(2)
                            with raw_col1:
                                st.subheader("Open Graph Data")
                                st.json(og_tags if og_tags else {"info": "No og:* tags detected."})
                            with raw_col2:
                                st.subheader("Twitter Card Data")
                                st.json(twitter_tags if twitter_tags else {"info": "No twitter:* tags detected."})
                        else:
                            st.subheader("Open Graph Data")
                            st.json(og_tags if og_tags else {"info": "No og:* tags detected."})
