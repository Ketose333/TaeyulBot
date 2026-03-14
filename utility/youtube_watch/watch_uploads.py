#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# --- Configuration ---
WORKSPACE = Path('/home/user/.openclaw/workspace')
ENV_PATH = WORKSPACE / '.env'
RESULT_JSON_PATH = WORKSPACE / 'memory/.youtube_watch_run_result.json'
LAST_RESULT_PATH = WORKSPACE / 'memory/.youtube_watch_last_result.json'

TARGETS = [
    ('UCxamIHVFYaGAhdl-A4jWVew', WORKSPACE/'memory/youtube-watch-august_30.json', '1471931748194455807'),
    ('UCArLZtok93cO5R9RI4_Y5Jw', WORKSPACE/'memory/youtube-watch-enhypenofficial.json', '1471931748194455807'),
    ('UCmnuDfK6fqL2hIWKjAmXJ-Q', WORKSPACE/'memory/youtube-watch-idntt.json', '1471931748194455807'),
    ('UCGgNIN5XPeOwUBOfhRTRq3A', WORKSPACE/'memory/youtube-watch-midi_bunny.json', '1471931748194455807'),
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def parse_iso(s):
    if not s:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)

def load_state(path: Path):
    if not path.exists():
        return {'last_checked_at': '1970-01-01T00:00:00+00:00', 'seen_ids': []}
    try:
        content = path.read_text(encoding='utf-8')
        if not content.strip():
            return {'last_checked_at': '1970-01-01T00:00:00+00:00', 'seen_ids': []}
        d = json.loads(content)
        return d if isinstance(d, dict) else {'last_checked_at': '1970-01-01T00:00:00+00:00', 'seen_ids': []}
    except Exception:
        return {'last_checked_at': '1970-01-01T00:00:00+00:00', 'seen_ids': []}

def save_state(path: Path, last_checked_at, seen_ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    clean_seen = [str(x) for x in seen_ids if x]
    data = {
        'last_checked_at': last_checked_at,
        'seen_ids': clean_seen[:50]
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')

def http_request(url, params=None, headers=None, method='GET', data=None, timeout=20):
    if params:
        url = url + '?' + urllib.parse.urlencode(params)
    
    req = urllib.request.Request(url, method=method)
    base_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    if headers:
        base_headers.update(headers)
        
    for k, v in base_headers.items():
        req.add_header(k, v)
        
    if data is not None:
        if isinstance(data, dict):
            req.data = urllib.parse.urlencode(data).encode()
        elif isinstance(data, str):
            req.data = data.encode()
        else:
            req.data = data

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        # Pass through 4xx/5xx to handle in caller (fallback trigger)
        raise e

def get_oauth_token(client_id, client_secret, refresh_token):
    resp_body = http_request(
        'https://oauth2.googleapis.com/token',
        method='POST',
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    return json.loads(resp_body)['access_token']

def fetch_api_videos(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    results = {}
    
    for cid, _, _ in TARGETS:
        try:
            ch_resp = http_request(
                'https://www.googleapis.com/youtube/v3/channels',
                params={'part': 'contentDetails', 'id': cid},
                headers=headers
            )
            ch_data = json.loads(ch_resp)
            items = ch_data.get('items', [])
            if not items:
                results[cid] = []
                continue
                
            uploads_id = items[0]['contentDetails']['relatedPlaylists']['uploads']
            
            pl_resp = http_request(
                'https://www.googleapis.com/youtube/v3/playlistItems',
                params={
                    'part': 'snippet,contentDetails',
                    'playlistId': uploads_id,
                    'maxResults': 10
                },
                headers=headers
            )
            pl_data = json.loads(pl_resp)
            
            videos = []
            for item in pl_data.get('items', []):
                snippet = item.get('snippet', {})
                content = item.get('contentDetails', {})
                
                vid = content.get('videoId') or snippet.get('resourceId', {}).get('videoId')
                pub = snippet.get('publishedAt')
                
                if vid and pub:
                    videos.append({'id': vid, 'publishedAt': pub})
            
            results[cid] = videos
            
        except Exception as e:
            # If one fails, propagate to fallback
            raise e
            
    return results

def fetch_rss_videos():
    results = {}
    ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
    
    for cid, _, _ in TARGETS:
        url = f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}'
        try:
            xml_data = http_request(url)
            root = ET.fromstring(xml_data)
            
            videos = []
            for entry in root.findall('atom:entry', ns):
                vid = entry.findtext('yt:videoId', default='', namespaces=ns)
                pub = entry.findtext('atom:published', default='', namespaces=ns)
                
                if vid and pub:
                    videos.append({'id': vid, 'publishedAt': pub})
            
            results[cid] = videos
            
        except Exception:
            # RSS failure -> empty list for this channel
            results[cid] = []
            
    return results

def main():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip("'").strip('"')

    mode = 'api'
    error_summary = None
    videos_map = {}

    try:
        if not all(k in env for k in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN']):
            raise ValueError("Missing OAuth credentials")
            
        token = get_oauth_token(env['GOOGLE_CLIENT_ID'], env['GOOGLE_CLIENT_SECRET'], env['GOOGLE_REFRESH_TOKEN'])
        videos_map = fetch_api_videos(token)
        
    except Exception as e:
        mode = 'rss'
        error_summary = str(e)
        try:
            videos_map = fetch_rss_videos()
        except Exception as rss_e:
            print(f"Error: All methods failed. API: {error_summary}, RSS: {rss_e}")
            return

    messages_to_send = []
    log_results = []
    now_str = now_iso()
    
    for cid, state_path, notify_ch in TARGETS:
        state = load_state(state_path)
        last_checked_dt = parse_iso(state.get('last_checked_at'))
        seen_ids = state.get('seen_ids', [])
        
        fetched_videos = videos_map.get(cid, [])
        fetched_videos.sort(key=lambda x: parse_iso(x['publishedAt']))
        
        new_candidates = []
        for v in fetched_videos:
            vid = v['id']
            v_dt = parse_iso(v['publishedAt'])
            if vid not in seen_ids and v_dt > last_checked_dt:
                new_candidates.append(vid)
        
        if new_candidates:
            # Take up to 3 latest
            picks = new_candidates[-3:]
            lines = ["이 영상 한번 볼래?"]
            for pid in picks:
                lines.append(f"https://www.youtube.com/watch?v={pid}")
            
            msg_text = "\n".join(lines)
            messages_to_send.append({
                'channel': f'channel:{notify_ch}',
                'message': msg_text
            })
            log_results.append({'channel': cid, 'new': picks})
        else:
            log_results.append({'channel': cid, 'new': []})

        # Update state
        all_seen = list(seen_ids)
        fetched_ids = [v['id'] for v in fetched_videos]
        for vid in fetched_ids:
            if vid not in seen_ids:
                all_seen.append(vid)
        
        save_state(state_path, now_str, all_seen[-50:])

    # Community task
    try:
        import subprocess
        cmd = [sys.executable, str(WORKSPACE / 'utility/youtube_watch/watch.py'), '--task', 'idntt-community']
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env={**os.environ, 'PYTHONPATH': '.'})
        comm_out = proc.stdout.strip()
        if comm_out and comm_out != 'NO_REPLY':
            lines = comm_out.splitlines()
            if len(lines) >= 2:
                messages_to_send.append({
                    'channel': 'channel:1471931748194455807',
                    'message': comm_out
                })
    except Exception:
        pass

    # Save results
    run_result = {
        'checked_at': now_str,
        'mode': mode,
        'error': error_summary,
        'results': log_results
    }
    RESULT_JSON_PATH.write_text(json.dumps(run_result, indent=2, ensure_ascii=False), encoding='utf-8')
    LAST_RESULT_PATH.write_text(json.dumps(run_result, indent=2, ensure_ascii=False), encoding='utf-8')
    
    # Output JSON for tool call
    print(json.dumps(messages_to_send))

if __name__ == '__main__':
    main()
