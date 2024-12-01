import os
import logging
from flask import Flask, render_template, request, redirect, url_for, session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import requests

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Secret key for session
app.secret_key = os.urandom(24)

# Google OAuth2 Configuration
GOOGLE_CLIENT_SECRETS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']

if not os.path.exists(GOOGLE_CLIENT_SECRETS_FILE):
    logger.error(f"Client secrets file not found at {GOOGLE_CLIENT_SECRETS_FILE}")
    raise FileNotFoundError(f"Client secrets file not found at {GOOGLE_CLIENT_SECRETS_FILE}")

@app.route('/')
def index():
    """Homepage - shows login option or redirects to albums if authenticated."""
    try:
        if 'credentials' in session:
            return redirect(url_for('list_albums'))
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return f"An error occurred: {e}", 500

@app.route('/login')
def login():
    """Initiates Google OAuth2 flow."""
    try:
        flow = Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=url_for('oauth2callback', _external=True)
        )
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        authorization_url, state = flow.authorization_url(access_type='offline', prompt='consent')
        session['state'] = state
        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"Error in login route: {e}")
        return f"An error occurred: {e}", 500

@app.route('/oauth2callback')
def oauth2callback():
    """Handles OAuth2 callback and saves credentials in session."""
    try:
        if 'state' not in session or request.args.get('state') != session['state']:
            return 'Invalid state parameter', 401

        flow = Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=session['state']
        )
        flow.redirect_uri = url_for('oauth2callback', _external=True)
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        return redirect(url_for('list_albums'))
    except Exception as e:
        logger.error(f"Error in oauth2callback route: {e}")
        return f"An error occurred: {e}", 500

@app.route('/list_albums')
def list_albums():
    """Fetches and displays user's Google Photos albums."""
    try:
        if 'credentials' not in session:
            return redirect(url_for('login'))

        # Reconstruct credentials
        credentials = Credentials(
            token=session['credentials']['token'],
            refresh_token=session['credentials']['refresh_token'],
            token_uri=session['credentials']['token_uri'],
            client_id=session['credentials']['client_id'],
            client_secret=session['credentials']['client_secret'],
            scopes=session['credentials']['scopes']
        )

        # Fetch albums using the Photos API
        headers = {'Authorization': f'Bearer {credentials.token}'}
        response = requests.get('https://photoslibrary.googleapis.com/v1/albums', headers=headers)
        
        if response.status_code == 200:
            albums = response.json().get('albums', [])
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            albums = []

        return render_template('albums.html', albums=albums)
    except Exception as e:
        logger.error(f"Error in list_albums route: {e}")
        return f"An error occurred: {e}", 500

@app.route('/list_photos')
def list_photos():
    """Fetches and displays photos from a specific album."""
    try:
        if 'credentials' not in session:
            return redirect(url_for('login'))

        album_id = request.args.get('albumId')
        album_name = request.args.get('albumName')
        if not album_id:
            return "Album ID is required.", 400

        # Reconstruct credentials
        credentials = Credentials(
            token=session['credentials']['token'],
            refresh_token=session['credentials']['refresh_token'],
            token_uri=session['credentials']['token_uri'],
            client_id=session['credentials']['client_id'],
            client_secret=session['credentials']['client_secret'],
            scopes=session['credentials']['scopes']
        )

        # Fetch photos using the Photos API
        headers = {'Authorization': f'Bearer {credentials.token}'}
        response = requests.post(
            'https://photoslibrary.googleapis.com/v1/mediaItems:search',
            headers=headers,
            json={'albumId': album_id}
        )

        if response.status_code == 200:
            photos = response.json().get('mediaItems', [])
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            photos = []

        return render_template('photos.html', photos=photos, albumName=album_name, albumId=album_id)
    except Exception as e:
        logger.error(f"Error in list_photos route: {e}")
        return f"An error occurred: {e}", 500


@app.route('/photo_details')
def photo_details():
    """Fetches and displays details of a specific photo."""
    try:
        if 'credentials' not in session:
            return redirect(url_for('login'))

        # Get photoId, albumId, and albumName from query parameters
        photo_id = request.args.get('photoId')
        album_id = request.args.get('albumId')
        album_name = request.args.get('albumName')

        if not photo_id:
            return "Photo ID is required.", 400

        # Reconstruct credentials
        credentials = Credentials(
            token=session['credentials']['token'],
            refresh_token=session['credentials']['refresh_token'],
            token_uri=session['credentials']['token_uri'],
            client_id=session['credentials']['client_id'],
            client_secret=session['credentials']['client_secret'],
            scopes=session['credentials']['scopes']
        )

        # Fetch photo details using the Photos API
        headers = {'Authorization': f'Bearer {credentials.token}'}
        response = requests.get(
            f'https://photoslibrary.googleapis.com/v1/mediaItems/{photo_id}',
            headers=headers
        )

        if response.status_code == 200:
            photo = response.json()
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return f"Error fetching photo details: {response.text}", 500

        # Pass photo details, albumId, and albumName to the template
        return render_template(
            'photo_details.html',
            photo=photo,
            albumId=album_id,
            albumName=album_name
        )
    except Exception as e:
        logger.error(f"Error in photo_details route: {e}")
        return f"An error occurred: {e}", 500




@app.route('/logout')
def logout():
    """Clears the session."""
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
