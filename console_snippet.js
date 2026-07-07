/**
 * X (Twitter) Bookmarks Exporter - Browser Console Snippet
 * 
 * Instructions:
 * 1. Log into x.com (Twitter) and go to your bookmarks page: https://x.com/i/bookmarks
 * 2. Open Developer Tools (Press F12, or Right-Click -> Inspect, then click the "Console" tab).
 * 3. Copy and paste this entire code block into the console, then press Enter.
 * 4. To stop the script early, type `stopExport()` in the console.
 */

(async function() {
    console.log("%c[Twitter Bookmark Exporter] Initializing...", "color: #1da1f2; font-weight: bold; font-size: 14px;");
    
    const bookmarks = new Map();
    let lastHeight = document.body.scrollHeight;
    let noChangeCount = 0;
    let isRunning = true;
    
    // Exposed globally so user can stop it manually
    window.stopExport = function() {
        console.log("%c[Twitter Bookmark Exporter] Stopping execution manually...", "color: #ffcc00; font-weight: bold;");
        isRunning = false;
    };

    function getTweetUrls() {
        const tweets = document.querySelectorAll('article[data-testid="tweet"]');
        let count = 0;
        tweets.forEach(tweet => {
            // Find the <time> element inside the tweet. Its parent <a> points to the status URL.
            const timeEl = tweet.querySelector('time');
            if (timeEl) {
                const a = timeEl.closest('a');
                if (a) {
                    const href = a.getAttribute('href');
                    if (href) {
                        // Normalize URL (strip query parameters and ensure x.com domain)
                        const cleanPath = href.split('?')[0];
                        const fullUrl = cleanPath.startsWith('http') ? cleanPath : `https://x.com${cleanPath}`;
                        if (!bookmarks.has(fullUrl)) {
                            // Extract image URLs
                            const imgs = tweet.querySelectorAll('div[data-testid="tweetPhoto"] img');
                            const imageUrls = [];
                            imgs.forEach(img => {
                                const src = img.getAttribute('src');
                                if (src) {
                                    let origSrc = src.replace(/name=\w+/, 'name=orig');
                                    if (!origSrc.includes('name=')) {
                                        origSrc += origSrc.includes('?') ? '&name=orig' : '?name=orig';
                                    }
                                    imageUrls.push(origSrc);
                                }
                            });

                            // Check if a video/GIF is present
                            const hasVideo = tweet.querySelector('video') !== null || tweet.querySelector('[data-testid="videoPlayer"]') !== null;

                            bookmarks.set(fullUrl, {
                                url: fullUrl,
                                id: cleanPath.split('/').pop(),
                                images: imageUrls,
                                has_video: hasVideo
                            });
                            count++;
                        }
                    }
                }
            }
        });
        return count;
    }

    function downloadFile(content, fileName, contentType) {
        const a = document.createElement("a");
        const file = new Blob([content], { type: contentType });
        a.href = URL.createObjectURL(file);
        a.download = fileName;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    function clickRetryButton() {
        const buttons = document.querySelectorAll('button, [role="button"]');
        for (const btn of buttons) {
            const txt = btn.textContent ? btn.textContent.trim().toLowerCase() : "";
            if (txt === 'retry' || txt === 'try again' || txt.includes('retry')) {
                console.log("%c[Twitter Bookmark Exporter] Rate limit/load error detected. Clicking 'Retry' button...", "color: #e74c3c; font-weight: bold;");
                btn.click();
                return true;
            }
        }
        return false;
    }

    console.log("%c[Twitter Bookmark Exporter] Scrolling and collecting links. Please do not close or switch tab.", "color: #1da1f2;");
    console.log("You can stop the script at any time by typing `stopExport()` and pressing Enter.");

    while (isRunning) {
        const added = getTweetUrls();
        if (added > 0) {
            console.log(`%cCollected ${added} new links. Total unique bookmarks: ${bookmarks.size}`, "color: #2ecc71;");
            noChangeCount = 0; // reset counter since we found new tweets
        }

        // Scroll down
        window.scrollTo(0, document.body.scrollHeight);
        
        // Wait for content to load
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        const newHeight = document.body.scrollHeight;
        if (newHeight === lastHeight) {
            // Check if there is a retry button
            const clicked = clickRetryButton();
            if (clicked) {
                // Wait an extra 5 seconds to let content load after clicking retry
                await new Promise(resolve => setTimeout(resolve, 5000));
                noChangeCount = Math.max(0, noChangeCount - 2); // give it more chances
                continue;
            }

            noChangeCount++;
            console.log(`No new content loaded (attempt ${noChangeCount}/30)...`);
            if (noChangeCount >= 30) {
                console.log("%cReached the end of the bookmarks page or rate limit.", "color: #1da1f2; font-weight: bold;");
                break;
            }
        } else {
            lastHeight = newHeight;
            noChangeCount = 0;
        }
    }

    console.log(`%cFinished! Total bookmarks collected: ${bookmarks.size}`, "color: #1da1f2; font-weight: bold; font-size: 14px;");
    
    if (bookmarks.size > 0) {
        const timestamp = new Date().toISOString().replace(/T/, '_').replace(/\..+/, '').replace(/:/g, '-');
        
        // Save txt file
        const txtContent = Array.from(bookmarks.keys()).join('\n');
        const txtFileName = `x_bookmarks_${timestamp}.txt`;
        downloadFile(txtContent, txtFileName, 'text/plain');
        
        // Save json file
        const jsonContent = JSON.stringify(Array.from(bookmarks.values()), null, 2);
        const jsonFileName = `x_bookmarks_data_${timestamp}.json`;
        downloadFile(jsonContent, jsonFileName, 'application/json');
        
        console.log(`%cDownloaded files:\n1. ${txtFileName}\n2. ${jsonFileName}`, "color: #2ecc71; font-weight: bold;");
    } else {
        console.log("%cNo bookmarks were found. Make sure you are logged in and looking at https://x.com/i/bookmarks", "color: #e74c3c; font-weight: bold;");
    }
})();
