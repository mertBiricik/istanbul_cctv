from flask import Flask, render_template, jsonify, Response, request, make_response
import requests
import time
import logging
import os
import re
import threading

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Stream URLs for different cameras
STREAM_URLS = {
    'stream1': 'https://hls4.ibb.gov.tr/ls/cam_turistik/b_sarachane.stream/playlist.m3u8',
    'stream2': 'https://hls4.ibb.gov.tr/ls/cam_turistik/beyazit.stream/playlist.m3u8',
    'stream3': 'https://hls4.ibb.gov.tr/ls/cam_turistik/sultanahmet.stream/playlist.m3u8'
}

# Alternative cameras if the primary ones fail
BACKUP_CAMERAS = {
    'sarachane': 'https://hls4.ibb.gov.tr/ls/cam_turistik/b_sarachane.stream/playlist.m3u8',
    'beyazit': 'https://hls4.ibb.gov.tr/ls/cam_turistik/beyazit.stream/playlist.m3u8',
    'sultanahmet': 'https://hls4.ibb.gov.tr/ls/cam_turistik/sultanahmet.stream/playlist.m3u8',
    'galatatower': 'https://hls4.ibb.gov.tr/ls/cam_turistik/galatakulesi.stream/playlist.m3u8',
    'taksim': 'https://hls4.ibb.gov.tr/ls/cam_turistik/taksim.stream/playlist.m3u8',
    'miniaturk': 'https://hls4.ibb.gov.tr/ls/cam_turistik/miniaturk.stream/playlist.m3u8'
}

# Alternative server mirrors
SERVER_MIRRORS = {
    'hls2': 'hls2.ibb.gov.tr',
    'hls3': 'hls3.ibb.gov.tr',
    'hls4': 'hls4.ibb.gov.tr' 
}

# The URL of the original page
ORIGINAL_URL = "https://istanbuluseyret.ibb.gov.tr/sarachane-yeni/"

# Check stream status
def check_stream_status(stream_url):
    try:
        # First do a HEAD request to check basic availability
        head_response = requests.head(stream_url, timeout=5)
        if head_response.status_code != 200:
            logger.info(f"Stream {stream_url} HEAD request failed with status {head_response.status_code}")
            return False
            
        # Then try to download a small part of the stream to verify it's working
        get_response = requests.get(stream_url, timeout=5, stream=True)
        chunk_size = 1024
        
        # Just read a little bit of data to make sure the stream is active
        for chunk in get_response.iter_content(chunk_size=chunk_size):
            if chunk:  # filter out keep-alive chunks
                logger.info(f"Stream {stream_url} is working properly")
                return True
            break  # only need one chunk
            
        logger.warning(f"Stream {stream_url} returned empty content")
        return False
    except requests.exceptions.RequestException as e:
        logger.warning(f"Stream {stream_url} check failed: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_streams')
def check_streams():
    results = {}
    all_working = True
    
    # Check current stream URLs
    for stream_id, url in STREAM_URLS.items():
        status = check_stream_status(url)
        stream_number = stream_id.replace('stream', '')
        results[stream_id] = {
            'status': status,
            'status_text': 'Active' if status else 'Offline',
            'stream_number': stream_number,
            'url': url
        }
        if not status:
            all_working = False
    
    # If any streams are offline, try to update servers
    if not all_working:
        logger.info("Some streams are offline. Checking for alternative servers...")
        servers_updated = update_stream_servers()
        
        if servers_updated:
            # Recheck streams with the new URLs
            for stream_id, url in STREAM_URLS.items():
                status = check_stream_status(url)
                stream_number = stream_id.replace('stream', '')
                results[stream_id] = {
                    'status': status,
                    'status_text': 'Active' if status else 'Offline',
                    'stream_number': stream_number,
                    'url': url,
                    'updated': True
                }
    
    # Add overall status
    results['meta'] = {
        'all_working': all(info['status'] for info in results.values() if isinstance(info, dict) and 'status' in info),
        'check_time': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
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
        
        # Create a standalone page with just the player for this stream
        response = make_response(render_template('stream.html', 
                              stream_number=stream_number,
                              stream_url=stream_url))
        
        # Add headers to discourage caching for live streams
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
    except Exception as e:
        logger.error(f"Error creating stream {stream_number}: {str(e)}")
        return f"Failed to create stream {stream_number}", 500

# Try to find working servers and update stream URLs
def update_stream_servers():
    global STREAM_URLS
    
    working_streams = 0
    
    # Use a list of camera names to try for each stream
    camera_options = {
        'stream1': ['b_sarachane', 'galatakulesi', 'taksim'],
        'stream2': ['beyazit', 'sultanahmet', 'miniaturk'],
        'stream3': ['sultanahmet', 'beyazit', 'galatakulesi']
    }
    
    # For each stream, try to find a working camera
    for stream_id, cameras in camera_options.items():
        # First check if the current URL is working
        if check_stream_status(STREAM_URLS[stream_id]):
            logger.info(f"Current URL for {stream_id} is working: {STREAM_URLS[stream_id]}")
            working_streams += 1
            continue
            
        # If not, try each camera with each server
        found_working = False
        for camera in cameras:
            for server in ['hls4', 'hls3', 'hls2']:
                test_url = f"https://{server}.ibb.gov.tr/ls/cam_turistik/{camera}.stream/playlist.m3u8"
                if check_stream_status(test_url):
                    logger.info(f"Found working camera {camera} on {server} for {stream_id}")
                    STREAM_URLS[stream_id] = test_url
                    working_streams += 1
                    found_working = True
                    break
            
            if found_working:
                break
                
        if not found_working:
            logger.error(f"No working cameras found for {stream_id}!")
    
    return working_streams > 0

# Initial server check at startup
try:
    logger.info("Checking for working stream servers on startup...")
    update_stream_servers()
except Exception as e:
    logger.error(f"Error checking stream servers: {str(e)}")

# Check servers periodically
def schedule_server_check():
    while True:
        try:
            time.sleep(300)  # Check every 5 minutes
            logger.info("Performing scheduled check of stream servers")
            update_stream_servers()
        except Exception as e:
            logger.error(f"Error in scheduled server check: {str(e)}")
            time.sleep(60)  # Wait a bit before retrying after an error

# Start server check in a background thread
threading.Thread(target=schedule_server_check, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 