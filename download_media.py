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
    """Downloads a file (image/video) from a URL and saves it to filepath."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response, open(filepath, 'wb') as out_file:
            out_file.write(response.read())
        return True
    except Exception as e:
        print(f"    [-] Download failed: {e}")
        return False

def get_media_from_twmate(tweet_url):
    """Automates twmate.com headlessly to extract direct image and video URLs for a tweet. Bypasses X logins and India geoblocks."""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://twmate.com/", wait_until="domcontentloaded")
            
            # Dismiss cookie consent dialog if it appears
            try:
                page.wait_for_selector("#disagree-btn", timeout=4000)
                page.click("#disagree-btn")
            except Exception:
                pass
                
            page.wait_for_selector('input[name="page"]', timeout=10000)
            page.fill('input[name="page"]', tweet_url)
            page.click(".btn_submit")
            
            # Wait for either video or photo download links to appear
            try:
                page.wait_for_selector("a[href*='twimg']", timeout=12000)
            except Exception:
                pass
                
            links = page.query_selector_all("a")
            image_urls = []
            video_urls = []
            
            for l in links:
                href = l.get_attribute("href") or ""
                if "pbs.twimg.com/media" in href:
                    orig_src = re.sub(r'name=\w+', 'name=orig', href)
                    if 'name=' not in orig_src:
                        orig_src += '&name=orig' if '?' in orig_src else '?name=orig'
                    if orig_src not in image_urls:
                        image_urls.append(orig_src)
                elif "video.twimg.com" in href:
                    if href not in video_urls:
                        video_urls.append(href)
                        
            # Group videos to find best resolutions
            best_video_urls = []
            if video_urls:
                video_groups = {}
                for v_url in video_urls:
                    base_url = v_url.split('/vid/')[0] if '/vid/' in v_url else v_url
                    if base_url not in video_groups:
                        video_groups[base_url] = []
                    video_groups[base_url].append(v_url)
                
                for base_url, urls in video_groups.items():
                    best_url = None
                    best_res = 0
                    for url in urls:
                        res_match = re.search(r'(\d+)x(\d+)', url)
                        if res_match:
                            res = int(res_match.group(1)) * int(res_match.group(2))
                        else:
                            res = 1
                        if res > best_res:
                            best_res = res
                            best_url = url
                    if not best_url and urls:
                        best_url = urls[0]
                    if best_url:
                        best_video_urls.append(best_url)
                        
            return image_urls, best_video_urls
        except Exception:
            return [], []
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
            _, video_urls = get_media_from_twmate(url)
            if video_urls:
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
            
        time.sleep(1.0)
            
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
        image_urls, video_urls = get_media_from_twmate(url)
        
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
            
        time.sleep(1.0)
        
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
