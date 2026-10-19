import json
from pathlib import Path
import sys
import threading
import unittest
import tempfile
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class LocalServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_youtube_hosts_only(self):
        self.assertTrue(app.validate_url('https://youtu.be/example'))
        for url in ['https://youtube.com.evil.test/a', 'file:///etc/passwd',
                    'https://user@youtube.com/a', 'https://example.com']:
            self.assertFalse(app.validate_url(url))

    def test_library_hides_unmerged_video(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('video.f298.mp4', 'video.temp.mp4', 'video.mp4'):
                (root / name).touch()
            with patch.object(app, 'DOWNLOADS', root):
                self.assertEqual([p.name for p in app.completed_videos()], ['video.mp4'])

    def test_interface_and_state(self):
        with urlopen(self.url) as response:
            self.assertIn('Videoların'.encode(), response.read())
        with urlopen(self.url + '/api/state') as response:
            self.assertEqual(json.load(response)['token'], app.TOKEN)

    def test_post_requires_token(self):
        with self.assertRaises(HTTPError) as result:
            urlopen(Request(self.url + '/api/download', data=b'{}'))
        self.assertEqual(result.exception.code, 403)

    def test_rejects_invalid_url(self):
        request = Request(self.url + '/api/download',
                          data=json.dumps({'urls': ['https://evil.test']}).encode(),
                          headers={'X-App-Token': app.TOKEN})
        with self.assertRaises(HTTPError) as result:
            urlopen(request)
        self.assertEqual(result.exception.code, 400)

    def test_no_project_file_download(self):
        with self.assertRaises(HTTPError) as result:
            urlopen(self.url + '/downloads/..%2Fapp.py')
        self.assertEqual(result.exception.code, 404)

    def test_rejects_other_host(self):
        with self.assertRaises(HTTPError) as result:
            urlopen(Request(self.url + '/api/state', headers={'Host': 'evil.test'}))
        self.assertEqual(result.exception.code, 403)

    def test_delete_video(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / 'Türkçe video.mp4'
            video.write_bytes(b'video')
            with patch.object(app, 'DOWNLOADS', Path(folder)):
                request = Request(self.url + '/api/delete',
                                  data=json.dumps({'name': video.name}).encode(),
                                  headers={'X-App-Token': app.TOKEN})
                with urlopen(request) as response:
                    self.assertTrue(json.load(response)['ok'])
                self.assertFalse(video.exists())

    def test_delete_rejects_unsafe_files_and_missing_token(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('keep.mp4', 'video.f298.mp4', 'notes.txt'):
                (root / name).write_bytes(b'keep')
            (root / 'link.mp4').symlink_to(root / 'keep.mp4')
            with patch.object(app, 'DOWNLOADS', root):
                cases = [('keep.mp4', None, 403),
                         ('../keep.mp4', app.TOKEN, 400),
                         ('..\\keep.mp4', app.TOKEN, 400),
                         ('video.f298.mp4', app.TOKEN, 404),
                         ('notes.txt', app.TOKEN, 404),
                         ('link.mp4', app.TOKEN, 404),
                         ('missing.mp4', app.TOKEN, 404)]
                for name, token, status in cases:
                    with self.subTest(name=name):
                        request = Request(self.url + '/api/delete',
                                          data=json.dumps({'name': name}).encode(),
                                          headers={'X-App-Token': token} if token else {})
                        with self.assertRaises(HTTPError) as result:
                            urlopen(request)
                        self.assertEqual(result.exception.code, status)
                self.assertTrue((root / 'keep.mp4').exists())
                self.assertTrue((root / 'video.f298.mp4').exists())
                self.assertTrue((root / 'notes.txt').exists())


if __name__ == '__main__':
    unittest.main()
