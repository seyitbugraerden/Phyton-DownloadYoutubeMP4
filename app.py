"""Local YouTube download queue. Run with Python 3.10+."""
import json
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote
import webbrowser

ROOT = Path(__file__).resolve().parent
DOWNLOADS = ROOT / 'downloads'
TOKEN = secrets.token_urlsafe(32)
JOBS = []
LOCK = threading.Lock()
QUEUE = queue.Queue()


def ffmpeg_path():
    system = shutil.which('ffmpeg')
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


def runtime_args():
    if shutil.which('deno'):
        return ['--js-runtimes', 'deno']
    node = shutil.which('node')
    if not node:
        # Finder launches may not inherit nvm's PATH.
        candidates = sorted((Path.home() / '.nvm/versions/node').glob('v*/bin/node'),
                            key=lambda p: tuple(int(n) for n in p.parents[1].name[1:].split('.')),
                            reverse=True)
        node = str(candidates[0]) if candidates else None
    return ['--js-runtimes', f'node:{node}'] if node else []


def validate_url(value):
    parsed = urlparse(value)
    return (parsed.scheme in ('https', 'http') and parsed.hostname in
            ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com')
            and not parsed.username and not parsed.password and parsed.port in (None, 80, 443))


def update(job, **values):
    with LOCK:
        job.update(values)


def completed_videos():
    return [p for p in DOWNLOADS.glob('*.mp4')
            if not re.search(r'\.(?:f\d+|temp)\.mp4$', p.name)
            and not p.is_symlink()]


def worker():
    while True:
        job = QUEUE.get()
        try:
            update(job, status='İndiriliyor', detail='Video bilgisi alınıyor…')
            height = job['quality']
            fmt = (f'bv*[ext=mp4][vcodec^=avc1][height<={height}]+ba[ext=m4a]/'
                   f'b[ext=mp4][height<={height}]')
            command = [sys.executable, '-m', 'yt_dlp', '--no-playlist', '--newline',
                       '--no-colors', '--restrict-filenames', '--max-filesize', '5G',
                       '--socket-timeout', '30', '--retries', '3', '-f', fmt,
                       '--merge-output-format', 'mp4', '--paths', str(DOWNLOADS),
                       '-o', '%(title).150B [%(id)s].%(ext)s',
                       '--ffmpeg-location', ffmpeg_path(), *runtime_args(), '--', job['url']]
            process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True)
            lines = []
            for line in process.stdout:
                line = line.strip()
                if line:
                    lines.append(line)
                    lines = lines[-10:]
                    if '[Merger]' in line:
                        update(job, status='Birleştiriliyor', detail='Ses ve görüntü birleştiriliyor; bitmesini bekle…')
                    else:
                        update(job, detail=line[-600:])
            code = process.wait()
            if code:
                update(job, status='Hata', detail='\n'.join(lines)[-2000:])
            else:
                update(job, status='Tamamlandı', detail='Video indirilenler listesinde hazır.')
        except Exception as exc:
            update(job, status='Hata', detail=str(exc))
        finally:
            QUEUE.task_done()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'static'), **kwargs)

    def allowed(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def respond(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed():
            return self.respond({'error': 'Geçersiz adres.'}, 403)
        path = urlparse(self.path).path
        if path == '/api/state':
            with LOCK:
                jobs = [dict(job) for job in JOBS]
            files = [{'name': p.name, 'size': round(p.stat().st_size / 1048576, 1)}
                     for p in sorted(completed_videos(), key=lambda p: p.stat().st_mtime, reverse=True)]
            return self.respond({'token': TOKEN, 'jobs': jobs, 'files': files,
                                 'ffmpeg': bool(ffmpeg_path()), 'folder': str(DOWNLOADS)})
        if path.startswith('/downloads/'):
            name = unquote(path[len('/downloads/'):])
            if '/' in name or '\\' in name or not name.endswith('.mp4'):
                return self.respond({'error': 'Bulunamadı.'}, 404)
            candidate = DOWNLOADS / name
            if not candidate.is_file() or candidate.is_symlink():
                return self.respond({'error': 'Bulunamadı.'}, 404)
            self.directory = str(DOWNLOADS)
            self.path = self.path[len('/downloads'):]
        elif path not in ('/', '/index.html'):
            return self.respond({'error': 'Bulunamadı.'}, 404)
        return super().do_GET()

    def do_POST(self):
        if not self.allowed() or self.headers.get('X-App-Token') != TOKEN:
            return self.respond({'error': 'İstek reddedildi.'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 16000:
                raise ValueError('İstek çok büyük veya boş.')
            data = json.loads(self.rfile.read(size))
            if self.path == '/api/delete':
                name = data.get('name')
                if (not isinstance(name, str) or not name or '/' in name
                        or '\\' in name or '\x00' in name):
                    raise ValueError('Geçersiz dosya adı.')
                candidate = DOWNLOADS / name
                if candidate not in completed_videos() or not candidate.is_file():
                    return self.respond({'error': 'Video bulunamadı.'}, 404)
                try:
                    candidate.unlink()
                except FileNotFoundError:
                    return self.respond({'error': 'Video bulunamadı.'}, 404)
                except OSError:
                    return self.respond({'error': 'Video silinemedi. Dosya izinlerini kontrol et.'}, 500)
                return self.respond({'ok': True})
            if self.path != '/api/download':
                return self.respond({'error': 'Bulunamadı.'}, 404)
            urls = data.get('urls')
            quality = str(data.get('quality', '720'))
            if quality not in ('360', '480', '720', '1080'):
                raise ValueError('Geçersiz kalite.')
            if not isinstance(urls, list) or not 1 <= len(urls) <= 30:
                raise ValueError('Bir defada 1–30 bağlantı ekleyebilirsin.')
            if any(not isinstance(url, str) or not validate_url(url) for url in urls):
                raise ValueError('Yalnızca geçerli YouTube bağlantıları kabul edilir.')
            if not ffmpeg_path():
                raise ValueError('Önce FFmpeg kurmalısın. README dosyasındaki adımları izle.')
            with LOCK:
                if sum(j['status'] in ('Sırada', 'İndiriliyor', 'Birleştiriliyor') for j in JOBS) + len(urls) > 100:
                    raise ValueError('İndirme sırası dolu; mevcut indirmelerin bitmesini bekle.')
                JOBS[:] = JOBS[-200:]
                for url in urls:
                    job = dict(id=uuid.uuid4().hex, url=url, quality=quality,
                               status='Sırada', detail='Sırasını bekliyor…')
                    JOBS.append(job)
                    QUEUE.put(job)
            self.respond({'ok': True})
        except (ValueError, TypeError, AttributeError) as exc:
            self.respond({'error': str(exc)}, 400)


if __name__ == '__main__':
    DOWNLOADS.mkdir(exist_ok=True)
    threading.Thread(target=worker, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('PORT', '8765'))), Handler)
    address = f'http://127.0.0.1:{server.server_port}'
    print(f'Uygulama: {address}\nVideolar: {DOWNLOADS}\nDurdurmak için Ctrl+C', flush=True)
    webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
