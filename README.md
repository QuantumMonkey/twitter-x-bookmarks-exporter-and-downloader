# X (Twitter) Bookmarks Exporter & Downloader

A lightweight, robust, and login-free command-line tool to extract all bookmarked tweet links from your X (Twitter) account and download all attached media (high-resolution images and videos).

This tool is designed to bypass X's strict login walls, sensitive content locks, and geographic restrictions (such as geoblocks on NSFW content in some regions) by scraping media links through public endpoints.

---

## Features

*   **Zero-Install Link Exporter**: A lightweight JavaScript snippet that you copy-paste into your browser DevTools Console to export your bookmarks list as a structured `.json` metadata file.
*   **100% Login-Free Media Downloader**: The downloader script runs completely headlessly. It does not require you to input your X credentials or cookies.
*   **Bypasses Geoblocks & NSFW Age Gates**: Routes video and image queries through public resolvers headlessly, allowing users in restricted regions to download their media seamlessly.
*   **Supports Multi-Video Posts**: Automatically detects tweets containing multiple videos, selects the highest resolution for each, and saves them sequentially (e.g., `_video_1.mp4`, `_video_2.mp4`).
*   **Original Image Resolution**: Downloads photos at their maximum, uncompressed quality (`name=orig`).
*   **Dynamic Queue Management**: The script automatically removes successfully completed or skipped URLs from your source bookmarks file in real-time, leaving only failed/unprocessed links behind.

---

## How it Works

1.  **Exporting**: You log into X in your standard browser, go to your bookmarks page, and run the console snippet. It scrolls and downloads a `.json` file containing direct image links and video flags.
2.  **Downloading**: You run the Python script. For images, it downloads them directly from Twitter's CDN (which is public). For videos, it queries a public resolver headlessly to extract direct MP4 links, and downloads them.

---

## Installation & Setup

### Prerequisites
*   Python 3.7+ installed.

### Setup Steps
1.  Clone this repository:
    ```bash
    git clone https://github.com/QuantumMonkey/twitter-x-bookmarks-exporter-and-downloader.git
    cd twitter-x-bookmarks-exporter-and-downloader
    ```
2.  Install dependencies:
    ```bash
    py -m pip install -r requirements.txt
    ```
3.  Install Playwright browser binaries:
    ```bash
    py -m playwright install chromium
    ```

---

## Usage Guide

### Step 1: Export Bookmarks List
1.  Log into [x.com](https://x.com) on your browser and navigate to your Bookmarks page.
2.  Open your browser's Developer Tools Console:
    *   **Windows/Linux**: Press `F12` or `Ctrl + Shift + J`.
    *   **Mac**: Press `Cmd + Option + J`.
3.  Copy the entire contents of [console_snippet.js](console_snippet.js).
4.  Paste the code into the Console prompt and press **Enter**.
5.  Wait for the page to finish scrolling. It will automatically download a `.txt` list and a `.json` metadata file (e.g., `x_bookmarks_data_*.json`).
6.  Move the `.json` file into this project folder.

### Step 2: Download Media
Run the media downloader:
```bash
py download_media.py
```
*Note: By default, the script automatically picks the most recently exported `.json` (or `.txt`) file. You can also specify a file manually:*
```bash
py download_media.py x_bookmarks_data_2026-07-06_13-22-49.json
```

All files will be saved in the `downloads/` folder, organized by tweet ID.

---

## Credits & Collaboration

This project was built through a collaborative pair-programming effort:
*   **Conceptualization, Feature Direction, and Testing**: Developed by [QuantumMonkey](https://github.com/QuantumMonkey).
*   **Engineering and Implementation**: Built by **Antigravity**, an agentic AI coding assistant designed by Google DeepMind.

---

## License

This project is open-source and available under the [MIT License](LICENSE).
