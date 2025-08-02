import os
import feedparser
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
from pathlib import Path
import datetime
import re

# --- SETTINGS ---
# RSS links for the YouTube channels.
# To find the channel ID, go to the channel's main page on YouTube. The URL will contain "/channel/UC...". That UC... string is the ID.
# Format: https://www.youtube.com/feeds/videos.xml?channel_id=UC-MOi2r4sS_3m_i-D0_M_GA
CHANNELS = {
    "Selcoin": "https://www.youtube.com/feeds/videos.xml?channel_id=UC-MOi2r4sS_3m_i-D0_M_GA",
    "Bora Özkent Official": "https://www.youtube.com/feeds/videos.xml?channel_id=UCy1a2LL6B32Qp5T2D5p11gg"
}

# File to store the IDs of videos that have already been processed.
PROCESSED_VIDEOS_FILE = Path("processed_videos.txt")

# Directory where the generated summaries will be saved.
SUMMARIES_DIR = Path("summaries")

# Get the Gemini API Key from GitHub Secrets.
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please add it to your repository's GitHub Secrets.")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- FUNCTIONS ---

def get_processed_videos():
    """Reads the IDs of already processed videos from the state file."""
    if not PROCESSED_VIDEOS_FILE.is_file():
        return set()
    with open(PROCESSED_VIDEOS_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_processed_video(video_id):
    """Appends the ID of a newly processed video to the state file."""
    with open(PROCESSED_VIDEOS_FILE, "a") as f:
        f.write(f"{video_id}\n")

def get_transcript(video_id):
    """Fetches the transcript for a given video ID."""
    try:
        # We specify 'tr' to prioritize getting the Turkish transcript.
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['tr'])
        return " ".join([item['text'] for item in transcript_list])
    except Exception as e:
        print(f"Error: Could not retrieve transcript for video ID {video_id}. Reason: {e}")
        return None

def summarize_text(transcript, title):
    """Summarizes the given text using the Gemini API."""
    
    # We create the prompt as a standard multi-line string, without the 'f' prefix.
    # We use placeholders like {title} and {transcript}.
    prompt_template = """
    Aşağıdaki metin, "{title}" başlıklı bir YouTube videosunun transkriptidir.
    Bu metni, ana fikirleri ve önemli noktaları içerecek şekilde, profesyonel bir dille ve madde madde olacak şekilde Türkçe olarak özetle.
    Özetin başına videonun ana temasını anlatan kısa bir paragraf ekle.

    METİN:
    {transcript}
    """
    
    # We use the .format() method to safely insert our variables into the placeholders.
    # This bypasses the editor's f-string highlighting bug.
    final_prompt = prompt_template.format(title=title, transcript=transcript)
    
    try:
        response = model.generate_content(final_prompt)
        return response.text
    except Exception as e:
        print(f"Error: Could not summarize with Gemini API. Reason: {e}")
        return None

def sanitize_filename(name):
    """Removes characters that are invalid for file names."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

# --- MAIN PROCESS ---

def main():
    print("Starting process...")
    SUMMARIES_DIR.mkdir(exist_ok=True)
    processed_videos = get_processed_videos()
    new_videos_found = False

    for channel_name, rss_url in CHANNELS.items():
        print(f"\nChecking channel: {channel_name}")
        feed = feedparser.parse(rss_url)
