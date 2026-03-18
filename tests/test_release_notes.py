import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlparse, unquote

import updater


class ReleaseNotesTests(unittest.TestCase):
    def test_open_release_notes_from_news_renders_html_and_opens_browser(self):
        with TemporaryDirectory() as td:
            news_path = Path(td) / 'news.md'
            news_path.write_text("## v0.2.1\n\n- Added feature\n", encoding='utf-8')

            with patch('updater._news_md_path', return_value=news_path), \
                 patch('updater.webbrowser.open') as mock_open:
                ok = updater.open_release_notes_from_news()

            self.assertTrue(ok)
            mock_open.assert_called_once()
            opened_uri = mock_open.call_args[0][0]
            parsed = urlparse(opened_uri)
            html_path = Path(unquote(parsed.path))
            self.assertTrue(html_path.exists())
            html = html_path.read_text(encoding='utf-8')
            self.assertIn("<h2>v0.2.1</h2>", html)
            self.assertIn("<li>Added feature</li>", html)
            html_path.unlink(missing_ok=True)

    def test_open_release_notes_from_news_returns_false_when_news_missing(self):
        with TemporaryDirectory() as td:
            missing = Path(td) / 'missing-news.md'
            with patch('updater._news_md_path', return_value=missing), \
                 patch('updater.webbrowser.open') as mock_open:
                ok = updater.open_release_notes_from_news()

            self.assertFalse(ok)
            mock_open.assert_not_called()


if __name__ == '__main__':
    unittest.main()
