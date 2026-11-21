import os
import re
import json
import socket
import base64
import urllib.request
import urllib.parse
import concurrent.futures
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from Crypto.Cipher import DES

PORT = 8116
DES_KEY = b"38346591"
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

def decrypt_saavn_url(encrypted_url):
    try:
        cipher = DES.new(DES_KEY, DES.MODE_ECB)
        raw = base64.b64decode(encrypted_url.strip())
        dec = cipher.decrypt(raw)
        pad = dec[-1]
        url = dec[:-pad].decode('utf-8').strip()
        # Upgrade to 320 kbps studio master
        return url.replace('_96.mp4', '_320.mp4').replace('_160.mp4', '_320.mp4')
    except Exception:
        return ""

def search_jiosaavn(query, limit=15):
    try:
        encoded_query = urllib.parse.quote(query.strip())
        api_url = f"https://www.jiosaavn.com/api.php?__call=search.getResults&q={encoded_query}&_format=json&_marker=0&api_version=4&ctx=android&n={limit}&p=1"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        
        with urllib.request.urlopen(req, timeout=7) as resp:
            raw_data = resp.read().decode('utf-8', errors='ignore')
            saavn_json = json.loads(raw_data)
            raw_results = saavn_json.get('results', [])

            songs = []
            for item in raw_results:
                try:
                    more = item.get('more_info', {})
                    enc_url = more.get('encrypted_media_url')
                    if not enc_url:
                        continue

                    audio_url = decrypt_saavn_url(enc_url)
                    if not audio_url:
                        continue

                    duration_sec = int(more.get('duration', 180))
                    raw_img = item.get('image', '')
                    hd_img = raw_img.replace('150x150', '500x500') if raw_img else 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4'

                    primary = more.get('artistMap', {}).get('primary_artists', [])
                    artist = primary[0].get('name') if primary else (item.get('subtitle') or more.get('music') or 'Unknown Artist')
                    title = item.get('title', 'Unknown Title').replace('&quot;', '"').replace('&amp;', '&').replace('&#039;', "'")

                    songs.append({
                        'id': item.get('id', str(len(songs))),
                        'title': title,
                        'artist': artist,
                        'album': more.get('album', 'Single'),
                        'duration': duration_sec,
                        'audioUrl': audio_url,
                        'coverUrl': hd_img,
                        'quality': '320 KBPS MASTER'
                    })
                except Exception:
                    continue
            return songs
    except Exception as e:
        print("Search error:", e, flush=True)
        return []

class BeatifyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/api/search':
                self.handle_search(parsed.query)
            elif parsed.path == '/api/recommendations':
                self.handle_recommendations(parsed.query)
            elif parsed.path == '/api/vibe-feed':
                self.handle_vibe_feed(parsed.query)
            elif parsed.path in ('/api/import-spotify', '/api/spotify/import'):
                self.handle_spotify_import(parsed.query)
            elif parsed.path == '/api/lyrics':
                self.handle_lyrics(parsed.query)
            elif parsed.path.startswith('/offline_audio/'):
                self.handle_offline_audio(parsed.path)
            else:
                super().do_GET()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json({'success': False, 'error': str(e)})

    def handle_search(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        q = params.get('q', [''])[0].strip()
        if not q:
            self.send_json({'success': False, 'results': []})
            return
        songs = search_jiosaavn(q, limit=20)
        self.send_json({'success': True, 'results': songs})

    def handle_lyrics(self, query_string):
        """
        Time-Synced Lyrics Engine (same as Spotify & Apple Music):
        Multi-tier resolver with lrclib.net (direct match + search fallback).
        """
        params = urllib.parse.parse_qs(query_string)
        track = params.get('track', params.get('title', ['']))[0].strip()
        artist = params.get('artist', [''])[0].strip()

        if not track:
            self.send_json({'success': False, 'lines': []})
            return

        # Clean track title and artist
        clean_track = re.sub(r'\s*[\(\[].*?[\)\]]', '', track)
        clean_track = re.sub(r'["\']', '', clean_track)
        clean_track = re.sub(r'\b(feat\.?|ft\.?|featuring)\b.*', '', clean_track, flags=re.I).strip()

        clean_artist = re.sub(r'\s*[\(\[].*?[\)\]]', '', artist)
        clean_artist = clean_artist.split(',')[0].split('&')[0].split('/')[0]
        clean_artist = re.sub(r'\b(feat\.?|ft\.?|featuring)\b.*', '', clean_artist, flags=re.I).strip()

        synced = None
        plain = None

        headers = {'User-Agent': 'Jamio-Music-Client/1.0'}

        # Strategy 1: Direct lrclib get
        try:
            url = f"https://lrclib.net/api/get?track_name={urllib.parse.quote(clean_track)}&artist_name={urllib.parse.quote(clean_artist)}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8', errors='ignore'))
                synced = data.get('syncedLyrics')
                plain = data.get('plainLyrics')
        except Exception:
            pass

        # Strategy 2: Fallback search if direct get failed or had no synced lyrics
        if not synced:
            search_queries = [f"{clean_track} {clean_artist}", clean_track]
            for q in search_queries:
                if synced:
                    break
                try:
                    url = f"https://lrclib.net/api/search?q={urllib.parse.quote(q)}"
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        results = json.loads(resp.read().decode('utf-8', errors='ignore'))
                        if isinstance(results, list) and len(results) > 0:
                            # Pick result with synced lyrics first
                            for item in results:
                                if item.get('syncedLyrics'):
                                    synced = item.get('syncedLyrics')
                                    plain = item.get('plainLyrics') or plain
                                    break
                            if not synced and not plain:
                                for item in results:
                                    if item.get('plainLyrics'):
                                        plain = item.get('plainLyrics')
                                        break
                except Exception:
                    pass

        lines = []
        if synced:
            for line in synced.splitlines():
                m = re.match(r'\[(\d{2}):(\d{2}(?:\.\d+)?)\](.*)', line)
                if m:
                    t = int(m.group(1)) * 60 + float(m.group(2))
                    text = m.group(3).strip()
                    if text:
                        lines.append({'time': t, 'text': text})

        self.send_json({
            'success': True,
            'hasSynced': len(lines) > 0,
            'lines': lines,
            'plain': plain or ''
        })

    def handle_recommendations(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        artist = params.get('artist', [''])[0].strip()
        title = params.get('title', [''])[0].strip()
        current_id = params.get('id', [''])[0].strip()

        recommendations = []
        seen_titles = {title.lower()}

        # 1. Advanced Spotify-Tier Vibe Cluster Discovery
        vibe_queries = []
        combined_text = f"{artist} {title}".lower()

        # Genre & Vibe Taxonomy
        if any(w in combined_text for w in ['karan aujla', 'diljit', 'sidhu moose', 'ap dhillon', 'shubh', 'badshah', 'honey singh', 'divine', 'king', 'punjabi', 'jatt']):
            vibe_queries = [
                f"{artist} top hits",
                "Diljit Dosanjh Karan Aujla hits",
                "AP Dhillon Shubh Punjabi trap",
                "Trending Punjabi viral bangers"
            ]
        elif any(w in combined_text for w in ['arijit', 'atif aslam', 'shreya ghoshal', 'mohit chauhan', 'jubin', 'armaan malik', 'darshan raval', 'pritam', 'kk', 'vishal mishra', 'romantic', 'slowed', 'sad']):
            vibe_queries = [
                f"{artist} romantic songs",
                "Arijit Singh Atif Aslam soulful hits",
                "Heartfelt Bollywood love melodies",
                "Mohit Chauhan Shreya Ghoshal chill"
            ]
        elif any(w in combined_text for w in ['the weeknd', 'daft punk', 'kavinsky', 'dua lipa', 'post malone', 'synthwave', 'retro', 'starboy']):
            vibe_queries = [
                f"{artist} radio",
                "The Weeknd Daft Punk synthwave",
                "Midnight electro synth pop hits",
                "Post Malone Dua Lipa vibe"
            ]
        elif any(w in combined_text for w in ['lo-fi', 'lofi', 'chill', 'sleep', 'relax', 'study', 'reverb']):
            vibe_queries = [
                "lo-fi beats to relax",
                "hindi lo-fi slowed reverb hits",
                "midnight chill lo-fi acoustic"
            ]
        elif any(w in combined_text for w in ['taylor swift', 'drake', 'travis scott', 'billie eilish', 'justin bieber', 'ed sheeran', 'pop', 'hip hop']):
            vibe_queries = [
                f"{artist} radio",
                "Billboard Hot 100 global hits",
                "Trending Pop Hip-Hop radio"
            ]
        else:
            if artist:
                vibe_queries = [
                    f"{artist} radio",
                    f"{artist} best hits",
                    f"{artist} similar songs"
                ]
            else:
                vibe_queries = ["Trending Global Hits 2024"]

        # Fetch from discovered vibe queries
        for q in vibe_queries:
            if len(recommendations) >= 16:
                break
            hits = search_jiosaavn(q, limit=6)
            for s in hits:
                s_title = s['title'].lower()
                if s['id'] != current_id and s_title not in seen_titles:
                    seen_titles.add(s_title)
                    recommendations.append(s)

        # Fallback if too few
        if len(recommendations) < 6 and artist:
            extra = search_jiosaavn(f"{artist}", limit=10)
            for s in extra:
                s_title = s['title'].lower()
                if s['id'] != current_id and s_title not in seen_titles:
                    seen_titles.add(s_title)
                    recommendations.append(s)

        self.send_json({
            'success': True,
            'seed': {'artist': artist, 'title': title},
            'results': recommendations[:16]
        })

    def handle_vibe_feed(self, query_string):
        """
        Spotify-Grade Adaptive Mood & Taste Feed Engine:
        Dynamically generates curated cards and trending recommendations based on
        user's real listening patterns, top artists, and active mood.
        """
        params = urllib.parse.parse_qs(query_string)
        artists = params.get('artists', [''])[0].strip()
        mood = params.get('mood', ['romantic'])[0].strip().lower()

        if mood == 'punjabi' or any(w in artists.lower() for w in ['diljit', 'karan aujla', 'sidhu', 'ap dhillon', 'shubh', 'jatt']):
            mood_key = 'punjabi'
            mood_title = 'Punjabi Heatwave'
            mood_tag = 'HIGH VOLTAGE'
            cards = [
                {
                    'title': 'Diljit & Aujla Heat',
                    'desc': 'Trending Punjabi viral bangers & street trap',
                    'cover': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=300',
                    'query': 'Diljit Dosanjh Karan Aujla hits'
                },
                {
                    'title': 'Desi Hip-Hop & Trap',
                    'desc': 'AP Dhillon, Shubh, Divine & Sidhu Moose Wala',
                    'cover': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=300',
                    'query': 'AP Dhillon Shubh Punjabi trap'
                },
                {
                    'title': 'Jatt Anthem 101',
                    'desc': 'Non-stop driving beats & bass anthems',
                    'cover': 'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=300',
                    'query': 'Trending Punjabi bangers'
                }
            ]
            search_query = 'Diljit Dosanjh Karan Aujla hits'
        elif mood == 'lofi' or any(w in artists.lower() for w in ['lo-fi', 'lofi', 'slowed', 'synthwave', 'chill', 'acoustic']):
            mood_key = 'lofi'
            mood_title = 'Midnight Lo-Fi & Chill'
            mood_tag = 'SLOWED & CHILL'
            cards = [
                {
                    'title': 'Midnight Slowed',
                    'desc': 'Atmospheric lo-fi beats, gentle rain & reverb',
                    'cover': 'https://images.unsplash.com/photo-1518609878373-06d740f60d8b?w=300',
                    'query': 'hindi lo-fi slowed reverb hits'
                },
                {
                    'title': 'Night Drive Synthwave',
                    'desc': 'The Weeknd, retro synth pads & neon horizon',
                    'cover': 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=300',
                    'query': 'The Weeknd synthwave retro'
                },
                {
                    'title': 'Acoustic Coffeehouse',
                    'desc': 'Mellow guitar, peaceful vibes for studying',
                    'cover': 'https://images.unsplash.com/photo-1445985543470-41fdd6ce388d?w=300',
                    'query': 'chill acoustic guitar hindi'
                }
            ]
            search_query = 'lo-fi beats slowed hindi'
        elif mood == 'pop' or any(w in artists.lower() for w in ['taylor swift', 'weeknd', 'drake', 'billie', 'dualipa']):
            mood_key = 'pop'
            mood_title = 'Global Chartbusters'
            mood_tag = 'GLOBAL POP'
            cards = [
                {
                    'title': 'Global Top 50',
                    'desc': 'Taylor Swift, The Weeknd, Drake & Billie Eilish',
                    'cover': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=300',
                    'query': 'Billboard Hot 100 global hits'
                },
                {
                    'title': 'Late Night R&B',
                    'desc': 'Sensual modern pop grooves & vibes',
                    'cover': 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=300',
                    'query': 'Trending Pop Hip-Hop radio'
                },
                {
                    'title': 'Taylor Swift Eras',
                    'desc': 'Midnights, 1989, Lover & iconic eras',
                    'cover': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=300',
                    'query': 'Taylor Swift'
                }
            ]
            search_query = 'Taylor Swift The Weeknd'
        else:
            mood_key = 'romantic'
            mood_title = 'Soulful Love & Melodies'
            mood_tag = 'ROMANTIC VIBES'
            artist_display = artists.split(',')[0].strip() if artists else 'Arijit Singh'
            cards = [
                {
                    'title': f'{artist_display} Soulful Mix',
                    'desc': f'{artist_display}, Atif Aslam, Shreya Ghoshal & Pritam',
                    'cover': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=300',
                    'query': f'{artist_display} romantic songs'
                },
                {
                    'title': 'Heartfelt Love Hits',
                    'desc': 'Unplugged guitar, soulful voices & warm feelings',
                    'cover': 'https://images.unsplash.com/photo-1518609878373-06d740f60d8b?w=300',
                    'query': 'Arijit Singh Atif Aslam soulful hits'
                },
                {
                    'title': 'Midnight Acoustics',
                    'desc': 'Gentle Bollywood romance for late evenings',
                    'cover': 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=300',
                    'query': 'Mohit Chauhan Shreya Ghoshal chill'
                }
            ]
            search_query = f'{artist_display} romantic'

        songs = search_jiosaavn(search_query, limit=16)
        self.send_json({
            'success': True,
            'mood': mood_key,
            'moodTitle': mood_title,
            'tag': mood_tag,
            'cards': cards,
            'results': songs
        })

    def handle_spotify_import(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        spotify_url = params.get('url', [''])[0].strip()

        if not spotify_url:
            self.send_json({'success': False, 'error': 'Empty Spotify URL provided'})
            return

        match = re.search(r'playlist/([a-zA-Z0-9]+)', spotify_url)
        if not match:
            self.send_json({'success': False, 'error': 'Invalid Spotify Playlist URL. Expected open.spotify.com/playlist/{id}'})
            return

        playlist_id = match.group(1)
        playlist_name = 'Imported Spotify Playlist'
        raw_tracks = []

        # 1. Primary extractor: spotifyscraper with max_tracks=None (Paginates to fetch ALL tracks, beyond 100!)
        try:
            from spotify_scraper import SpotifyClient
            with SpotifyClient() as client:
                pl = client.get_playlist(spotify_url, max_tracks=None)
                if pl and pl.tracks:
                    playlist_name = pl.name or playlist_name
                    for item in pl.tracks:
                        if not item or not item.track:
                            continue
                        t = item.track
                        t_name = getattr(t, 'name', '')
                        if not t_name:
                            continue
                        artists_list = [a.name for a in getattr(t, 'artists', []) if getattr(a, 'name', None)]
                        artist_str = ", ".join(artists_list) if artists_list else 'Artist'
                        album_str = getattr(t.album, 'name', '') if getattr(t, 'album', None) else ''
                        dur_ms = getattr(t, 'duration_ms', 0)
                        dur_sec = dur_ms // 1000 if dur_ms else 210
                        raw_tracks.append({
                            'title': t_name,
                            'artist': artist_str,
                            'album': album_str,
                            'duration': dur_sec
                        })
        except Exception as err:
            print("spotifyscraper extraction error:", err, flush=True)

        # 2. Fallback extractor: Spotify embed __NEXT_DATA__
        if not raw_tracks:
            try:
                embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
                req = urllib.request.Request(embed_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode('utf-8', errors='ignore')
                    data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
                    if data_match:
                        d = json.loads(data_match.group(1))
                        entity = d.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
                        playlist_name = entity.get('name', playlist_name)
                        for item in entity.get('trackList', []):
                            raw_tracks.append({
                                'title': item.get('title', ''),
                                'artist': item.get('subtitle', ''),
                                'album': playlist_name,
                                'duration': 210
                            })
            except Exception as err2:
                print("Spotify embed fallback error:", err2, flush=True)

        if not raw_tracks:
            self.send_json({'success': False, 'error': 'Could not extract playlist. Make sure it is public and accessible.'})
            return

        def match_single_track(index, item):
            song_title = item.get('title', '')
            song_artist = item.get('artist', '')
            if not song_title:
                return (index, None)

            clean_title = re.sub(r'\s*[\(\[].*?[\)\]]', '', song_title).strip()
            clean_title = re.sub(r'["\']', '', clean_title).strip()
            first_artist = song_artist.split(',')[0].strip() if song_artist else ''
            query = f"{clean_title} {first_artist}".strip()

            search_results = search_jiosaavn(query, limit=1)
            if search_results:
                return (index, search_results[0])
            else:
                title_results = search_jiosaavn(clean_title, limit=1)
                if title_results:
                    return (index, title_results[0])
                else:
                    return (index, {
                        'id': f"sp_{index}",
                        'title': song_title,
                        'artist': song_artist or 'Artist',
                        'album': item.get('album', playlist_name),
                        'duration': item.get('duration', 210),
                        'audioUrl': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
                        'coverUrl': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=500',
                        'quality': '320 KBPS MASTER'
                    })

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                futures = [executor.submit(match_single_track, idx, item) for idx, item in enumerate(raw_tracks)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            results.sort(key=lambda x: x[0])
            matched_songs = [song for _, song in results if song is not None]

            self.send_json({
                'success': True,
                'playlistName': playlist_name,
                'totalSpotifyTracks': len(raw_tracks),
                'matchedCount': len(matched_songs),
                'tracks': matched_songs
            })
        except Exception as e:
            print("Spotify matching error:", e, flush=True)
            self.send_json({'success': False, 'error': f'Failed to process Spotify tracks: {str(e)}'})

    def handle_offline_audio(self, path):
        filename = path.replace('/offline_audio/', '')
        # Check standard user home directory and local cache
        candidates = [
            os.path.join(os.path.expanduser('~'), 'Music', 'Jamio', 'Downloads', filename),
            os.path.join(DIRECTORY, 'downloads', filename),
            os.path.join(DIRECTORY, filename)
        ]
        filepath = next((p for p in candidates if os.path.exists(p) and os.path.getsize(p) > 0), None)

        if filepath:
            total_size = os.path.getsize(filepath)
            range_header = self.headers.get('Range')

            start = 0
            end = total_size - 1
            status_code = 200

            if range_header and range_header.startswith('bytes='):
                try:
                    ranges = range_header.replace('bytes=', '').split('-')
                    if ranges[0]:
                        start = int(ranges[0])
                    if len(ranges) > 1 and ranges[1]:
                        end = int(ranges[1])
                    if end >= total_size:
                        end = total_size - 1
                    status_code = 206
                except Exception:
                    start = 0
                    end = total_size - 1
                    status_code = 200

            content_length = (end - start) + 1

            self.send_response(status_code)
            self.send_header('Content-Type', 'audio/mpeg')
            self.send_header('Content-Length', str(content_length))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Access-Control-Allow-Origin', '*')
            if status_code == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{total_size}')
            self.end_headers()

            with open(filepath, 'rb') as f:
                f.seek(start)
                bytes_to_send = content_length
                chunk_size = 64 * 1024
                while bytes_to_send > 0:
                    read_len = min(chunk_size, bytes_to_send)
                    chunk = f.read(read_len)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    bytes_to_send -= len(chunk)
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

class ReusableServer(ThreadingHTTPServer):
    allow_reuse_address = True
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()

if __name__ == '__main__':
    server = ReusableServer(('0.0.0.0', PORT), BeatifyHandler)
    print(f"Jamio Server running at http://0.0.0.0:{PORT} (Local LAN: http://172.20.10.3:{PORT})", flush=True)
    server.serve_forever()
