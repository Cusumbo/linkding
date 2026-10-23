from unittest import skip

from django.urls import reverse
from playwright.sync_api import expect

from bookmarks.tests_e2e.helpers import LinkdingE2ETestCase


class BookmarkItemE2ETestCase(LinkdingE2ETestCase):
    def test_toggle_favorite_persists_after_reload(self):
        bookmark = self.setup_bookmark(title="Favorite toggle example", favorite=False)
        page = self.open(reverse("linkding:bookmarks.index"))
        item = page.get_by_role("listitem").filter(
            has=page.get_by_role("link", name=bookmark.title, exact=True)
        )
        control = item.get_by_role("button", name="Favorite", exact=True)
        expect(control).to_be_visible()
        expect(control).to_have_attribute("aria-pressed", "false")
        expect(control).to_have_text("Favorite")

        control.click()
        expect(control).to_have_attribute("aria-pressed", "true")
        expect(control).to_have_text("Unfavorite")
        expect(item.get_by_text("Favorite", exact=True)).to_be_visible()
        self.assertReloads(0)

        page.reload()
        expect(control).to_have_attribute("aria-pressed", "true")
        expect(control).to_have_text("Unfavorite")

        self.resetReloads()
        control.click()
        expect(control).to_have_attribute("aria-pressed", "false")
        expect(control).to_have_text("Favorite")
        expect(item.get_by_text("Unfavorite", exact=True)).to_have_count(0)
        self.assertReloads(0)

        page.reload()
        expect(control).to_have_attribute("aria-pressed", "false")

    @skip("Fails in CI, needs investigation")
    def test_toggle_notes_should_show_hide_notes(self):
        bookmark = self.setup_bookmark(notes="Test notes")

        page = self.open(reverse("linkding:bookmarks.index"))

        notes = self.locate_bookmark(bookmark.title).locator(".notes")
        expect(notes).to_be_hidden()

        toggle_notes = page.locator("li button.toggle-notes")
        toggle_notes.click()
        expect(notes).to_be_visible()

        toggle_notes.click()
        expect(notes).to_be_hidden()
