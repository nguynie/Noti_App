import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.notifier import TelegramNotifier
from src.scraper import FacebookPost, FacebookScraper
from src.storage import Storage


class TestFacebookScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = FacebookScraper()

    def test_clean_url_strips_tracking_params(self):
        raw = "https://www.facebook.com/page/posts/12345?fbclid=IwAR123&__cft__[0]=AZX&__tn__=%2CO%2CP-R&ref=nf"
        cleaned = self.scraper.clean_url(raw)
        self.assertEqual(cleaned, "https://www.facebook.com/page/posts/12345")

    def test_clean_url_preserves_permalink_php_params(self):
        raw = "https://www.facebook.com/permalink.php?story_fbid=pfbid123&id=61581806486294&fbclid=IwAR999"
        cleaned = self.scraper.clean_url(raw)
        self.assertIn("story_fbid=pfbid123", cleaned)
        self.assertIn("id=61581806486294", cleaned)
        self.assertNotIn("fbclid", cleaned)

    def test_clean_url_preserves_photo_and_video_params(self):
        raw = "https://www.facebook.com/photo.php?fbid=987654&set=a.123&mibextid=ZbWKwL"
        cleaned = self.scraper.clean_url(raw)
        self.assertIn("fbid=987654", cleaned)
        self.assertIn("set=a.123", cleaned)
        self.assertNotIn("mibextid", cleaned)

    def test_clean_url_empty_and_escaped(self):
        self.assertEqual(self.scraper.clean_url(""), "")
        escaped = r"https:\/\/www.facebook.com\/page\/posts\/123"
        cleaned = self.scraper.clean_url(escaped)
        self.assertEqual(cleaned, "https://www.facebook.com/page/posts/123")

    def test_extract_page_identifier(self):
        url1 = "https://www.facebook.com/DoanKhoaLienChiHoi.CNTT.KHTN"
        self.assertEqual(
            self.scraper._extract_page_identifier(url1),
            "DoanKhoaLienChiHoi.CNTT.KHTN",
        )

        url2 = "https://www.facebook.com/profile.php?id=61581806486294"
        self.assertEqual(
            self.scraper._extract_page_identifier(url2),
            "61581806486294",
        )

    def test_parse_timeline_feed_no_duplicates_or_highlights(self):
        feed_data = {
            "timeline_list_feed_units": {
                "edges": [
                    {
                        "node": {
                            "__typename": "Story",
                            "post_id": "1115478661008316",
                            "creation_time": 1790946057,
                            "permalink_url": "https://www.facebook.com/page/posts/pfbid02Uw",
                            "comet_sections": {
                                "content": {
                                    "story": {
                                        "message": {"text": "Hello world!"}
                                    }
                                }
                            },
                        }
                    }
                ]
            },
            # Pinned highlight unit that should be ignored by timeline parser
            "highlight_units_section": {
                "units": {
                    "edges": [
                        {
                            "node": {
                                "__typename": "HighlightPostUnit",
                                "id": "856589636897221",
                            }
                        }
                    ]
                }
            },
        }

        posts_by_id = {}
        self.scraper._parse_timeline_feed(
            feed_data, posts_by_id, "https://www.facebook.com/page", "page"
        )
        self.assertEqual(len(posts_by_id), 1)
        self.assertIn("1115478661008316", posts_by_id)
        self.assertNotIn("856589636897221", posts_by_id)
        post = posts_by_id["1115478661008316"]
        self.assertEqual(post.creation_time, 1790946057)
        self.assertEqual(post.message, "Hello world!")


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_posts.db"
        self.storage = Storage(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_seen_exact_id(self):
        self.assertFalse(self.storage.is_seen(1, "1001"))
        self.storage.mark_seen(
            source_id=1,
            post_id="1001",
            post_url="https://facebook.com/posts/1001",
            notified=True,
        )
        self.assertTrue(self.storage.is_seen(1, "1001"))
        # Different source should not match
        self.assertFalse(self.storage.is_seen(2, "1001"))

    def test_is_seen_matching_url(self):
        self.storage.mark_seen(
            source_id=1,
            post_id="1001",
            post_url="https://facebook.com/posts/pfbidXYZ",
            notified=True,
        )
        # Querying with different ID but same URL should be recognized as seen
        self.assertTrue(
            self.storage.is_seen(
                source_id=1,
                post_id="pfbidXYZ",
                post_url="https://facebook.com/posts/pfbidXYZ",
            )
        )

    def test_is_seen_cross_format_embedded_id(self):
        self.storage.mark_seen(
            source_id=1,
            post_id="123456789",
            post_url="https://facebook.com/permalink.php?story_fbid=123456789&id=99",
            notified=True,
        )
        # Query with post_url containing stored ID
        self.assertTrue(
            self.storage.is_seen(
                source_id=1,
                post_id="different_id",
                post_url="https://facebook.com/permalink.php?story_fbid=123456789&id=99",
            )
        )

    def test_atomic_json_sync(self):
        self.storage.mark_seen(
            source_id=1,
            post_id="2002",
            post_url="https://facebook.com/posts/2002",
            creation_time=1700000000,
            message_snippet="Test post snippet",
            notified=True,
        )
        json_file = self.storage.json_path
        self.assertTrue(json_file.is_file())
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("1:2002", data)
        self.assertEqual(data["1:2002"]["creation_time"], 1700000000)
        self.assertTrue(data["1:2002"]["notified"])


class TestTelegramNotifier(unittest.TestCase):
    def test_category_hashtag_formatting(self):
        notifier = TelegramNotifier("fake_token", "123456")
        with patch.object(notifier, "send_message", return_value=(True, None)) as mock_send:
            notifier.notify_post(
                source_name="Ban Tình Nguyện",
                category="student union club",
                post_url="https://facebook.com/post/1",
                message="Sample announcement",
            )
            mock_send.assert_called_once()
            sent_text = mock_send.call_args[0][0]
            # Must format as valid hashtag with underscore
            self.assertIn("#student_union_club", sent_text)
            self.assertNotIn("#student union club", sent_text)

    def test_html_parse_error_fallback(self):
        notifier = TelegramNotifier("fake_token", "123456")
        # First call fails with entity error, second call succeeds with plain text
        first_resp = MagicMock()
        first_resp.status_code = 400
        first_resp.json.return_value = {
            "ok": False,
            "description": "Bad Request: can't parse entities in message text",
        }

        second_resp = MagicMock()
        second_resp.status_code = 200
        second_resp.json.return_value = {"ok": True}

        with patch("requests.post", side_effect=[first_resp, second_resp]) as mock_post:
            success, err = notifier.send_message("<b>Invalid HTML <<>>", parse_mode="HTML")
            self.assertTrue(success)
            self.assertIsNone(err)
            self.assertEqual(mock_post.call_count, 2)
            # Second call should have stripped HTML
            second_call_payload = mock_post.call_args_list[1][1]["json"]
            self.assertNotIn("<b>", second_call_payload["text"])
            self.assertNotIn("parse_mode", second_call_payload)


class TestNotifierService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.db_path = self.base_path / "service_test.db"

        from src.config import Config, SourceItem
        from src.service import NotifierService

        self.config = Config(base_dir=self.base_path)
        self.config.db_file = self.db_path
        self.config.auto_baseline_first_run = True

        self.service = NotifierService(self.config)
        self.test_source = SourceItem(
            id=101,
            name="Test Page",
            url="https://facebook.com/testpage",
            category="faculty",
            enabled=True,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_failed_notification_is_not_marked_seen(self):
        post = FacebookPost(
            post_id="post_999",
            url="https://facebook.com/testpage/posts/999",
            creation_time=1700000000,
            message="Test message",
        )
        self.service.scraper.scrape_page = MagicMock(return_value=[post])
        self.service.notifier.bot_token = "valid_bot_token"
        self.service.notifier.chat_id = "123456"
        # Simulate Telegram network failure
        self.service.notifier.notify_post = MagicMock(
            return_value=(False, "Connection timeout")
        )

        new_count = self.service.scan_source(self.test_source, force_notify=True)
        self.assertEqual(new_count, 0)
        # Crucial: Must NOT be marked as seen, so it can be retried!
        self.assertFalse(self.service.storage.is_seen(101, "post_999"))

    def test_successful_notification_marks_seen(self):
        post = FacebookPost(
            post_id="post_888",
            url="https://facebook.com/testpage/posts/888",
            creation_time=1700000000,
            message="Test message",
        )
        self.service.scraper.scrape_page = MagicMock(return_value=[post])
        self.service.notifier.bot_token = "valid_bot_token"
        self.service.notifier.chat_id = "123456"
        self.service.notifier.notify_post = MagicMock(return_value=(True, None))

        new_count = self.service.scan_source(self.test_source, force_notify=True)
        self.assertEqual(new_count, 1)
        self.assertTrue(self.service.storage.is_seen(101, "post_888"))

    def test_baseline_records_without_notifying(self):
        post = FacebookPost(
            post_id="post_777",
            url="https://facebook.com/testpage/posts/777",
            creation_time=1700000000,
            message="Initial post",
        )
        self.service.scraper.scrape_page = MagicMock(return_value=[post])
        self.service.notifier.notify_post = MagicMock()

        new_count = self.service.scan_source(self.test_source, force_baseline=True)
        self.assertEqual(new_count, 0)
        self.service.notifier.notify_post.assert_not_called()
        self.assertTrue(self.service.storage.is_seen(101, "post_777"))


if __name__ == "__main__":
    unittest.main()

