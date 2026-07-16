import os
import re
import sys
import glob
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright, Error

def get_latest_bookmarks_file():
    """Finds the most recently created bookmarks file in the script directory (prioritizing JSON)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try to find JSON metadata files first
    json_files = glob.glob(os.path.join(script_dir, "x_bookmarks_data_*.json"))
    if json_files:
        json_files.sort(key=os.path.getmtime, reverse=True)
        return json_files[0], "json"
        
    # Fallback to TXT link files
    txt_files = glob.glob(os.path.join(script_dir, "x_bookmarks_*.txt"))
    if txt_files:
        txt_files.sort(key=os.path.getmtime, reverse=True)
        return txt_files[0], "txt"
        
    return None, None

def extract_tweet_id(url):
    """Extracts the status/tweet ID from an X/Twitter URL."""
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else None

def download_file(url, filepath):
    """Downloads a file (image/video) from a URL with chunked reading and automatic range resume on interruption."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://twmate.com/'
    }
    
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        mode = 'wb'
        existing_bytes = 0
        
        # Check if file already exists (partial download from previous attempt in this call)
        if os.path.exists(filepath):
            existing_bytes = os.path.getsize(filepath)
            if existing_bytes > 0:
                mode = 'ab'
                
        req_headers = headers.copy()
        if existing_bytes > 0:
            req_headers['Range'] = f'bytes={existing_bytes}-'
            
        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                status = response.status if hasattr(response, 'status') else response.getcode()
                
                # If range request was ignored, download from scratch
                if existing_bytes > 0 and status != 206:
                    mode = 'wb'
                    existing_bytes = 0
                    
                with open(filepath, mode) as out_file:
                    while True:
                        chunk = response.read(1024 * 1024)  # 1 MB chunk size
                        if not chunk:
                            break
                        out_file.write(chunk)
                        
            # Verify download success and non-zero size
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return True
            else:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception:
                    pass
                return False
                
        except Exception as e:
            print(f"    [-] Chunk download attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                # Cleanup on final failure
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception:
                    pass
                return False

def get_media_from_twmate(tweet_url):
    """Automates twmate.com headlessly to extract direct image and video URLs for a tweet. Bypasses X logins and India geoblocks."""
    with sync_playwright() as p:
        search_completed = False
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://twmate.com/")
            page.wait_for_timeout(3000)
            
            # Dismiss cookie consent dialog if it appears
            try:
                page.click("#disagree-btn", timeout=2000)
            except Exception:
                pass
                
            page.fill('input[name="page"]', tweet_url)
            page.press('input[name="page"]', 'Enter')
            
            # Wait up to 30 seconds for download links to load or an error message to appear
            try:
                page.wait_for_selector("a[href*='/download/'], text=invalid url, text=invalid tweet url", timeout=30000)
            except Exception:
                pass
            
            # Parse Images
            links = page.query_selector_all("a")
            image_urls = []
            for l in links:
                href = l.get_attribute("href") or ""
                text = l.inner_text() or ""
                if "download another" in text.lower():
                    search_completed = True
                if href.startswith("/"):
                    href = "https://twmate.com" + href
                if "/download/" in href:
                    # Match links that have image resolutions or extensions
                    if any(x in text.lower() for x in ["download", "150x150", "x"]) or any(x in href.lower() for x in [".jpg", ".jpeg", ".png"]):
                        if href not in image_urls:
                            image_urls.append(href)
                            
            # Parse Videos by Table resolution grouping
            tables = page.query_selector_all("table")
            best_video_urls = []
            for t in tables:
                rows = t.query_selector_all("tr")
                best_url = None
                best_height = 0
                for r in rows:
                    text = r.inner_text() or ""
                    if "download" in text.lower() and ("mp4" in text.lower() or "video" in text.lower()):
                        link_el = r.query_selector("a[href*='/download/']")
                        if link_el:
                            href = link_el.get_attribute("href")
                            if href.startswith("/"):
                                href = "https://twmate.com" + href
                            
                            # Parse height
                            res_match = re.search(r'(\d+)x(\d+)', text)
                            if res_match:
                                height = int(res_match.group(2))
                            else:
                                p_match = re.search(r'(\d+)p', text)
                                height = int(p_match.group(1)) if p_match else 1
                                
                            if height > best_height:
                                best_height = height
                                best_url = href
                if best_url:
                    best_video_urls.append(best_url)
            
            # Fallback if no table-based videos found: look for any direct /download/ links containing MP4/video keywords
            if not best_video_urls:
                for l in links:
                    href = l.get_attribute("href") or ""
                    text = l.inner_text() or ""
                    if href.startswith("/"):
                        href = "https://twmate.com" + href
                    if "/download/" in href and ("mp4" in text.lower() or "video" in text.lower() or "mp4" in href.lower()):
                        if href not in best_video_urls:
                            best_video_urls.append(href)
                    
            # Double check search completion using text selector if "download another" link not found yet
            if not search_completed:
                content_lower = page.content().lower()
                if "download another" in content_lower:
                    search_completed = True
                elif "invalid url" in content_lower or "invalid tweet url" in content_lower:
                    print("    [-] twmate.com returned: Invalid url (tweet may be private, deleted, or has no media).")
                    search_completed = True
                    
            return image_urls, best_video_urls, search_completed
        except Exception:
            return [], [], False
        finally:
            browser.close()

def process_via_json(json_path, downloads_dir):
    """Downloads media using exported JSON metadata (Bypasses logins and geoblocks)."""
    print(f"[*] Processing in METADATA mode using: {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            bookmarks = json.load(f)
    except Exception as e:
        print(f"[!] Error loading JSON file: {e}")
        return
        
    total_bookmarks = len(bookmarks)
    print(f"[+] Loaded {total_bookmarks} bookmarks from metadata.")
    
    remaining_bookmarks = list(bookmarks)
    success_count = 0
    
    for idx, item in enumerate(bookmarks, 1):
        url = item.get("url")
        tweet_id = item.get("id")
        images = item.get("images", [])
        has_video = item.get("has_video", False)
        
        if not tweet_id:
            continue
            
        existing_media = glob.glob(os.path.join(downloads_dir, f"{tweet_id}_*"))
        if existing_media:
            print(f"[{idx}/{total_bookmarks}] Tweet {tweet_id} already downloaded. Skipping and removing from queue...")
            # Remove from queue
            remaining_bookmarks.remove(item)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(remaining_bookmarks, f, indent=2)
            success_count += 1
            continue
            
        print(f"[{idx}/{total_bookmarks}] Processing tweet {tweet_id}...")
        download_success = True
        media_found = False
        
        # 1. Download Images (Direct from CDN - bypasses login walls and geoblocks!)
        if images:
            print(f"    [+] Found {len(images)} image(s) in metadata. Downloading...")
            media_found = True
            img_idx = 1
            for img_url in images:
                ext_match = re.search(r'format=(\w+)', img_url)
                ext = ext_match.group(1) if ext_match else 'jpg'
                dest_path = os.path.join(downloads_dir, f"{tweet_id}_image_{img_idx}.{ext}")
                if download_file(img_url, dest_path):
                    print(f"    [+] Saved Image: {os.path.basename(dest_path)}")
                    img_idx += 1
                else:
                    download_success = False
                    
        # 2. Download Video (Bypasses logins and geoblocks by using twmate.com)
        if has_video:
            print("    [+] Video/GIF detected. Resolving via twmate.com...")
            media_found = True
            _, video_urls, search_completed = get_media_from_twmate(url)
            if not search_completed:
                print("    [-] twmate.com request timed out or was rate-limited. Retrying in 15 seconds...")
                time.sleep(15.0)
                _, video_urls, search_completed = get_media_from_twmate(url)
                if not search_completed:
                    print("    [-] twmate.com retry failed. Keeping in queue to retry.")
                    download_success = False
            elif video_urls:
                print(f"    [+] Found {len(video_urls)} video(s). Downloading...")
                vid_idx = 1
                for v_url in video_urls:
                    ext_match = re.search(r'\.(\w+)(?:\?|$)', v_url)
                    ext = ext_match.group(1) if ext_match else 'mp4'
                    suffix = f"_{vid_idx}" if len(video_urls) > 1 else ""
                    dest_path = os.path.join(downloads_dir, f"{tweet_id}_video{suffix}.{ext}")
                    if download_file(v_url, dest_path):
                        print(f"    [+] Saved Video: {os.path.basename(dest_path)}")
                        vid_idx += 1
                    else:
                        download_success = False
            else:
                print("    [-] Failed to resolve video URL(s) via twmate.com.")
                download_success = False
                
        # If successfully processed (media downloaded OR verified no media in tweet)
        if download_success:
            if not media_found:
                print("    [-] No media found for this tweet.")
            # Remove from queue file
            remaining_bookmarks.remove(item)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(remaining_bookmarks, f, indent=2)
            success_count += 1
            
        time.sleep(5.0)
            
    print(f"\n[+] Processing finished! Successfully processed {success_count}/{total_bookmarks} bookmarks.")

def process_via_txt(txt_path, downloads_dir):
    """Processes tweet URLs from a text file (Bypasses logins and geoblocks for both images and videos)."""
    print(f"[*] Processing in TEXT mode using: {txt_path}")
    
    with open(txt_path, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
        
    total_urls = len(urls)
    print(f"[+] Loaded {total_urls} URLs to process.")
    
    if total_urls == 0:
        return
        
    remaining_urls = list(urls)
    success_count = 0
    
    for idx, url in enumerate(urls, 1):
        tweet_id = extract_tweet_id(url)
        if not tweet_id:
            continue
            
        existing_media = glob.glob(os.path.join(downloads_dir, f"{tweet_id}_*"))
        if existing_media:
            print(f"[{idx}/{total_urls}] Tweet {tweet_id} already downloaded. Skipping and removing from queue...")
            remaining_urls.remove(url)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(remaining_urls) + '\n')
            success_count += 1
            continue
            
        print(f"[{idx}/{total_urls}] Resolving media for tweet {tweet_id}...")
        
        # Scrape twmate.com for BOTH images and videos
        image_urls, video_urls, search_completed = get_media_from_twmate(url)
        
        if not search_completed:
            print("    [-] twmate.com request timed out or was rate-limited. Retrying in 15 seconds...")
            time.sleep(15.0)
            image_urls, video_urls, search_completed = get_media_from_twmate(url)
            if not search_completed:
                print("    [-] twmate.com retry failed. Keeping in queue to retry.")
                continue
            
        download_success = True
        media_found = False
        
        # 1. Download Images
        if image_urls:
            print(f"    [+] Found {len(image_urls)} image(s) on twmate. Downloading...")
            media_found = True
            img_idx = 1
            for img_url in image_urls:
                ext_match = re.search(r'format=(\w+)', img_url)
                ext = ext_match.group(1) if ext_match else 'jpg'
                dest_path = os.path.join(downloads_dir, f"{tweet_id}_image_{img_idx}.{ext}")
                if download_file(img_url, dest_path):
                    print(f"    [+] Saved Image: {os.path.basename(dest_path)}")
                    img_idx += 1
                else:
                    download_success = False
                    
        # 2. Download Videos
        if video_urls:
            print(f"    [+] Found {len(video_urls)} video(s) on twmate. Downloading...")
            media_found = True
            vid_idx = 1
            for v_url in video_urls:
                ext_match = re.search(r'\.(\w+)(?:\?|$)', v_url)
                ext = ext_match.group(1) if ext_match else 'mp4'
                suffix = f"_{vid_idx}" if len(video_urls) > 1 else ""
                dest_path = os.path.join(downloads_dir, f"{tweet_id}_video{suffix}.{ext}")
                if download_file(v_url, dest_path):
                    print(f"    [+] Saved Video: {os.path.basename(dest_path)}")
                    vid_idx += 1
                else:
                    download_success = False
                    
        # If successfully processed (media downloaded OR verified no media in tweet)
        if download_success:
            if not media_found:
                print("    [-] No media found for this tweet.")
            # Remove from queue file
            remaining_urls.remove(url)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(remaining_urls) + '\n')
            success_count += 1
        else:
            print("    [-] Extraction failed or incomplete. Keeping in queue to retry.")
            
        time.sleep(5.0)
        
    print(f"\n[+] Text Mode finished! Successfully processed {success_count}/{total_urls} bookmarks.")

def main():
    print("==================================================")
    print("      X (Twitter) Bookmarks Media Downloader      ")
    print("==================================================")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    downloads_dir = os.path.join(script_dir, "downloads")
    
    os.makedirs(downloads_dir, exist_ok=True)
    
    # Parse manual file input or auto-detect
    target_file = None
    file_type = None
    
    if len(sys.argv) > 1:
        arg_path = sys.argv[1]
        if os.path.exists(arg_path):
            target_file = arg_path
            file_type = "json" if arg_path.endswith(".json") else "txt"
        else:
            print(f"[!] Error: Specified file '{arg_path}' does not exist.")
            return
    else:
        target_file, file_type = get_latest_bookmarks_file()
        
    if not target_file:
        print("[!] Error: No bookmarks file (.json or .txt) found.")
        print("    Please run the Browser Console Snippet first to export your bookmarks list.")
        return
        
    print(f"[*] Target file: {target_file}")
    print(f"[*] Downloads directory: {downloads_dir}\n")
    
    # Load URLs
    urls = []
    if file_type == "json":
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                urls = [item.get("url") for item in data if item.get("url")]
        except Exception as e:
            print(f"[!] Error loading JSON file: {e}")
            return
    else:
        with open(target_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
            
    if file_type == "json":
        process_via_json(target_file, downloads_dir)
    else:
        process_via_txt(target_file, downloads_dir)
        
    print(f"\n[*] Finished! All media saved to: {downloads_dir}")

if __name__ == "__main__":
    main()
