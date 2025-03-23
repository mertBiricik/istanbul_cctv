# Istanbul CCTV Stream Monitor

This web application reliably streams and monitors live CCTV footage from Istanbul, automatically refreshing streams when they become unavailable.

## Features

- Displays all three Istanbul CCTV streams in a single interface
- Monitors stream health and automatically refreshes disconnected streams
- Provides manual refresh buttons for each stream
- Toggle automatic monitoring on/off
- Uses Shaka Player for reliable HLS stream playback

## Requirements

- Python 3.7+
- Flask
- Requests

## Installation

1. Clone this repository
2. Navigate to the project directory
3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

To start the application in development mode:

```bash
python app.py
```

The application will be available at `http://localhost:5000`.

For production deployment, it's recommended to use Gunicorn:

```bash
gunicorn -w 4 app:app
```

## How It Works

1. The application uses Flask to serve a web page displaying the video streams
2. Shaka Player is used for reliable HLS stream playback
3. The streams are checked periodically (every 30 seconds by default)
4. When a stream goes down, the application automatically attempts to refresh it
5. After 3 failed attempts, a stream is marked as "Inactive" until manually refreshed

## Customization

- Adjust the stream check interval by modifying the `setInterval` value in the JavaScript
- Change the stream URLs in `app.py` if needed
- Customize the appearance by modifying the CSS in `static/css/styles.css` 