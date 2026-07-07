import os
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, Error

def main():
    print("==================================================")
    print("    X (Twitter) Bookmarks Link Exporter Script    ")
    print("==================================================")
    
    # Define paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    session_dir = os.path.join(script_dir, ".playwright_session")
    
    # Generate timestamped filename for results
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_filename = f"x_bookmarks_{timestamp}.txt"
    output_path = os.path.join(script_dir, output_filename)
    
    # Make sure session directory exists
    os.makedirs(session_dir, exist_ok=True)
    
    bookmarks = set()
    
    print(f"[*] Session data will be stored in: {session_dir}")
    print(f"[*] Bookmarks will be exported to: {output_path}\n")
    
    with sync_playwright() as p:
        print("[*] Launching browser (Chrome-compatible)...")
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=session_dir,
                headless=False,  # Headful mode is required for manual login
                slow_mo=50,      # Adds brief delays to mimic human behavior
                viewport={'width': 1280, 'height': 800}
            )
        except Exception as e:
            print(f"\n[!] Error launching browser: {e}")
            print("[!] If chromium is not installed, run: playwright install chromium")
            return

        # Playwright persistent contexts open one page by default
        page = context.pages[0] if context.pages else context.new_page()
        
        print("[*] Navigating to bookmarks page...")
        page.goto("https://x.com/i/bookmarks")
        
        # Check login status and wait if necessary
        print("\n[!] IMPORTANT: If you are not logged in, please log in now in the browser window.")
        print("[*] Waiting for bookmarks feed to load...")
        
        logged_in = False
        while not logged_in:
            try:
                # Check current URL
                current_url = page.url
                if "bookmarks" in current_url:
                    # Wait for at least one tweet or empty state indicator to load
                    try:
                        page.wait_for_selector('article[data-testid="tweet"]', timeout=3000)
                        logged_in = True
                        print("\n[+] Successfully authenticated and bookmarks feed detected!")
                        break
                    except Exception:
                        # Page is loaded but maybe no bookmarks are visible yet, or loading
                        pass
                
                # Check if we are stuck on login page
                if "login" in current_url or "flow/signup" in current_url:
                    time.sleep(1)
                else:
                    # Generic sleep while waiting
                    time.sleep(2)
            except Error:
                print("\n[!] Browser was closed or disconnected. Exiting...")
                return
            except KeyboardInterrupt:
                print("\n[!] Script cancelled by user. Exiting...")
                return

        # Start extraction loop
        last_height = page.evaluate("document.body.scrollHeight")
        no_change_count = 0
        max_no_change = 30
        
        print("\n[*] Starting link extraction. Scrolling bookmarks automatically...")
        print("[*] To stop the script and save what has been collected so far, press Ctrl+C in this terminal.")
        
        try:
            while True:
                # Extract visible tweet status URLs
                time_elements = page.query_selector_all('article[data-testid="tweet"] time')
                added_this_scroll = 0
                
                for time_el in time_elements:
                    try:
                        # Find the parent link element for the timestamp
                        href = page.evaluate("(element) => element.closest('a')?.getAttribute('href')", time_el)
                        if href:
                            # Strip query strings and build absolute URL
                            clean_path = href.split('?')[0]
                            full_url = clean_path if clean_path.startswith('http') else f"https://x.com{clean_path}"
                            
                            if full_url not in bookmarks:
                                bookmarks.add(full_url)
                                added_this_scroll += 1
                    except Exception:
                        # DOM element might have changed during scroll, safely skip it
                        continue
                
                if added_this_scroll > 0:
                    print(f"[+] Collected {added_this_scroll} new bookmarks. Total unique bookmarks: {len(bookmarks)}")
                    # Write progress to file dynamically in case of crash/exit
                    with open(output_path, "w", encoding="utf-8") as f:
                        for url in sorted(bookmarks):
                            f.write(url + "\n")
                    no_change_count = 0
                
                # Scroll to the bottom of the page
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # Wait for page to load new content
                page.wait_for_timeout(2000)
                
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    # Check if there is a retry button we can click
                    clicked_retry = page.evaluate("""() => {
                        const buttons = document.querySelectorAll('button, [role="button"]');
                        for (const btn of buttons) {
                            const txt = btn.textContent ? btn.textContent.trim().toLowerCase() : "";
                            if (txt === 'retry' || txt === 'try again' || txt.includes('retry')) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }""")
                    
                    if clicked_retry:
                        print("\n[!] Rate limit or load failure detected. Clicked 'Retry' button in browser.")
                        page.wait_for_timeout(5000)
                        no_change_count = max(0, no_change_count - 2)
                        continue

                    no_change_count += 1
                    print(f"[-] No new content loaded (attempt {no_change_count}/{max_no_change})...")
                    if no_change_count >= max_no_change:
                        print("[+] Reached the end of the bookmarks page.")
                        break
                else:
                    last_height = new_height
                    no_change_count = 0
                    
        except KeyboardInterrupt:
            print("\n[!] Execution interrupted by user. Saving bookmarks collected so far...")
        except Error as e:
            print(f"\n[!] Browser error occurred: {e}. Saving bookmarks collected so far...")
        
        # Save final list
        if bookmarks:
            with open(output_path, "w", encoding="utf-8") as f:
                for url in sorted(bookmarks):
                    f.write(url + "\n")
            print(f"\n[+] Successfully exported {len(bookmarks)} bookmarks!")
            print(f"[+] Saved to: {output_path}")
        else:
            print("\n[-] No bookmarks were extracted.")
            # Remove empty file if created
            if os.path.exists(output_path):
                os.remove(output_path)
                
        print("[*] Closing browser session...")
        try:
            context.close()
        except:
            pass
            
    print("[*] Done!")

if __name__ == "__main__":
    main()
