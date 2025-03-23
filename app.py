from flask import Flask, render_template, jsonify, Response, request
import requests
import time
import logging
import os
import re

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Stream URLs
STREAM_URLS = {
    'stream1': 'https://hls3.ibb.gov.tr/ls/cam_turistik/b_sarachane.stream/playlist.m3u8',
    'stream2': 'https://hls2.ibb.gov.tr/ls/cam_turistik/b_sarachane.stream/playlist.m3u8',
    'stream3': 'https://hls4.ibb.gov.tr/ls/cam_turistik/b_sarachane.stream/playlist.m3u8'
}

# The URL of the original page
ORIGINAL_URL = "https://istanbuluseyret.ibb.gov.tr/sarachane-yeni/"

# Check stream status
def check_stream_status(stream_url):
    try:
        response = requests.head(stream_url, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_streams')
def check_streams():
    results = {}
    for stream_id, url in STREAM_URLS.items():
        results[stream_id] = check_stream_status(url)
    return jsonify(results)

# Proxy for the bradmax player JS
@app.route('/player_script')
def player_script():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': ORIGINAL_URL
        }
        response = requests.get('https://istanbuluseyret.ibb.gov.tr/wp-content/plugins/bradmax-player/assets/js/default_player.js', headers=headers)
        return Response(response.content, content_type='application/javascript')
    except Exception as e:
        logger.error(f"Error fetching player script: {str(e)}")
        return "console.error('Failed to load player script');", 500

# Proxy for the original page to extract live player instances
@app.route('/stream_page')
def stream_page():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(ORIGINAL_URL, headers=headers)
        content = response.text
        
        # Create individual stream HTML for embedding
        return content
    except Exception as e:
        logger.error(f"Error fetching original page: {str(e)}")
        return "Failed to load stream page", 500

@app.route('/stream/<int:stream_number>')
def stream(stream_number):
    try:
        if stream_number < 1 or stream_number > 3:
            return "Invalid stream number", 404
            
        # Map stream numbers to URLs
        stream_url = STREAM_URLS[f'stream{stream_number}']
        
        # Create a standalone page with just the bradmax player for this stream
        return render_template('stream.html', 
                              stream_number=stream_number,
                              stream_url=stream_url)
    except Exception as e:
        logger.error(f"Error creating stream {stream_number}: {str(e)}")
        return f"Failed to create stream {stream_number}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 