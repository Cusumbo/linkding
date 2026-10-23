from bs4 import BeautifulSoup
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from bookmarks.tests.helpers import BookmarkFactoryMixin


class BookmarkFavoriteActionTestCase(TestCase, BookmarkFactoryMixin):
    def setUp(self):
        self.client.force_login(self.get_or_create_test_user())
        self.action_url = reverse("linkding:bookmarks.index.action")
        self.list_url = reverse("linkding:bookmarks.index")

    def assert_favorite_control(self, response, bookmark, favorite):
        soup = BeautifulSoup(response.content, "html.parser")
        template = soup.select_one(
            'turbo-stream[target="bookmark-list-container"] template'
        )
        if template:
            soup = BeautifulSoup(template.decode_contents(), "html.parser")
        item = soup.select_one(f'li[data-bookmark-id="{bookmark.id}"]')
        self.assertIsNotNone(item)
        button = item.select_one('button[name="toggle_favorite"]')
        self.assertEqual(button["aria-label"], "Favorite")
        self.assertEqual(button["aria-pressed"], str(favorite).lower())
        self.assertEqual(
            button.get_text(strip=True), "Unfavorite" if favorite else "Favorite"
        )
        self.assertEqual(button["value"], str(bookmark.id))
        self.assertEqual(bool(item.select_one(".title .label")), favorite)

    def test_owner_toggle_redirect_and_reload_preserve_state(self):
        bookmark = self.setup_bookmark(unread=True, shared=True)
        original_modified = bookmark.date_modified
        self.assert_favorite_control(self.client.get(self.list_url), bookmark, False)
        for favorite in (True, False):
            with self.subTest(favorite=favorite):
                response = self.client.post(
                    self.action_url + "?q=example", {"toggle_favorite": bookmark.id}
                )
                self.assertRedirects(response, self.list_url + "?q=example")
                bookmark.refresh_from_db()
                self.assertEqual(bookmark.favorite, favorite)
                self.assertTrue(bookmark.unread)
                self.assertTrue(bookmark.shared)
                self.assertFalse(bookmark.is_archived)
                self.assertEqual(bookmark.date_modified, original_modified)
                self.assert_favorite_control(
                    self.client.get(self.list_url), bookmark, favorite
                )

    def test_toggle_turbo_updates_all_list_types(self):
        user = self.get_or_create_test_user()
        user.profile.enable_sharing = True
        user.profile.save()
        for view in ("index", "archived", "shared"):
            bookmark = self.setup_bookmark(is_archived=view == "archived", shared=True)
            for favorite in (True, False):
                with self.subTest(view=view, favorite=favorite):
                    response = self.client.post(
                        reverse(f"linkding:bookmarks.{view}.action"),
                        {"toggle_favorite": bookmark.id},
                        HTTP_ACCEPT="text/vnd.turbo-stream.html",
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(
                        "text/vnd.turbo-stream.html", response["Content-Type"]
                    )
                    self.assertContains(response, 'target="bookmark-list-container"')
                    self.assert_favorite_control(response, bookmark, favorite)
                    bookmark.refresh_from_db()
                    self.assertEqual(bookmark.favorite, favorite)

    def test_other_user_cannot_toggle_even_public_shared_bookmark(self):
        owner = self.setup_user(enable_sharing=True, enable_public_sharing=True)
        bookmark = self.setup_bookmark(user=owner, shared=True)
        for view in ("index", "archived", "shared"):
            for favorite in (False, True):
                with self.subTest(view=view, favorite=favorite):
                    bookmark.favorite = favorite
                    bookmark.save()
                    response = self.client.post(
                        reverse(f"linkding:bookmarks.{view}.action"),
                        {"toggle_favorite": bookmark.id},
                    )
                    self.assertEqual(response.status_code, 404)
                    bookmark.refresh_from_db()
                    self.assertEqual(bookmark.favorite, favorite)
        response = self.client.get(reverse("linkding:bookmarks.shared"))
        self.assertContains(response, bookmark.title)
        self.assertNotContains(response, 'name="toggle_favorite"')

    def test_missing_bookmark_returns_404(self):
        response = self.client.post(self.action_url, {"toggle_favorite": 999999})
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_toggle(self):
        bookmark = self.setup_bookmark()
        self.client.logout()
        response = self.client.post(self.action_url, {"toggle_favorite": bookmark.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{settings.LOGIN_URL}?next={self.action_url}")
        bookmark.refresh_from_db()
        self.assertFalse(bookmark.favorite)

    def test_get_does_not_toggle(self):
        bookmark = self.setup_bookmark()
        self.client.get(self.action_url, {"toggle_favorite": bookmark.id})
        bookmark.refresh_from_db()
        self.assertFalse(bookmark.favorite)

    def test_turbo_toggle_respects_favorite_filter(self):
        bookmark = self.setup_bookmark(favorite=True)
        response = self.client.post(
            self.action_url + "?favorite=true",
            {"toggle_favorite": bookmark.id},
            HTTP_ACCEPT="text/vnd.turbo-stream.html",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'data-bookmark-id="{bookmark.id}"')
        bookmark.refresh_from_db()
        self.assertFalse(bookmark.favorite)
