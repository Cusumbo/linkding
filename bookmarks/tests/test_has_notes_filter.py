"""Contract for the derived has_notes filter; it does not add bookmark state."""

from urllib.parse import urlencode

from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bookmarks.forms import BookmarkSearchForm
from bookmarks.models import BookmarkSearch
from bookmarks.tests.helpers import (
    BookmarkFactoryMixin,
    BookmarkListTestMixin,
    LinkdingApiTestCase,
)


class HasNotesApiTestCase(LinkdingApiTestCase, BookmarkFactoryMixin):
    def setUp(self):
        self.authenticate()
        self.empty = self.setup_bookmark(notes="")
        self.content = self.setup_bookmark(notes="Personal notes")
        self.markdown = self.setup_bookmark(notes="# Heading\n\n- A note")
        # This filter tests the stored string, not rendered or stripped Markdown.
        self.whitespace = self.setup_bookmark(notes=" \t\n")
        self.all_bookmarks = [
            self.empty,
            self.content,
            self.markdown,
            self.whitespace,
        ]

    def assertResults(self, params, expected, endpoint="linkding:bookmark-list"):
        response = self.get(reverse(endpoint) + "?" + urlencode(params))
        self.assertEqual(response.data["count"], len(expected))
        self.assertCountEqual(
            [item["id"] for item in response.data["results"]],
            [bookmark.id for bookmark in expected],
        )

    def test_absent_parameter_keeps_all_notes_states(self):
        self.assertResults({}, self.all_bookmarks)

    def test_true_returns_nonempty_notes(self):
        self.assertResults(
            {"has_notes": "true"}, [self.content, self.markdown, self.whitespace]
        )

    def test_false_returns_only_empty_notes(self):
        self.assertResults({"has_notes": "false"}, [self.empty])

    def test_boolean_aliases_follow_existing_filter_conventions(self):
        for value, expected in [
            ("yes", [self.content, self.markdown, self.whitespace]),
            ("no", [self.empty]),
        ]:
            with self.subTest(value=value):
                self.assertResults({"has_notes": value}, expected)

    def test_unrecognized_or_empty_values_disable_filter(self):
        for value in ["invalid", "off", "", "TRUE", "FALSE", "1", "0"]:
            with self.subTest(value=value):
                self.assertResults({"has_notes": value}, self.all_bookmarks)

    def test_filter_does_not_expose_other_users_or_archived_bookmarks(self):
        other_user = self.setup_user(enable_sharing=True, enable_public_sharing=True)
        for notes in ["", "Private note"]:
            self.setup_bookmark(user=other_user, notes=notes)
            self.setup_bookmark(user=other_user, notes=notes, shared=True)
            self.setup_bookmark(notes=notes, is_archived=True)
        for value, expected in [
            ("true", [self.content, self.markdown, self.whitespace]),
            ("false", [self.empty]),
        ]:
            with self.subTest(value=value):
                self.assertResults({"has_notes": value}, expected)

    def test_combines_with_search_and_shared_filter(self):
        empty = self.setup_bookmark(title="needle", notes="", shared=True)
        content = self.setup_bookmark(title="needle", notes="A note", shared=True)
        self.setup_bookmark(title="needle", notes="", shared=False)
        self.setup_bookmark(title="needle", notes="A note", shared=False)
        self.setup_bookmark(title="different", notes="", shared=True)
        self.setup_bookmark(title="different", notes="A note", shared=True)
        for value, expected in [("true", content), ("false", empty)]:
            with self.subTest(value=value):
                self.assertResults(
                    {"q": "needle", "shared": "true", "has_notes": value},
                    [expected],
                )

    def test_invalid_value_preserves_other_filters(self):
        bookmark = self.setup_bookmark(title="needle", notes="A note", shared=True)
        self.setup_bookmark(title="needle", notes="", shared=False)
        self.assertResults(
            {"q": "needle", "shared": "true", "has_notes": "invalid"}, [bookmark]
        )

    def test_archived_endpoint_has_same_contract_and_owner_isolation(self):
        empty = self.setup_bookmark(notes="", is_archived=True)
        content = self.setup_bookmark(notes="A note", is_archived=True)
        other_user = self.setup_user(enable_sharing=True, enable_public_sharing=True)
        for notes in ["", "Someone else's note"]:
            self.setup_bookmark(
                user=other_user, notes=notes, is_archived=True, shared=True
            )
        for params, expected in [
            ({}, [empty, content]),
            ({"has_notes": "true"}, [content]),
            ({"has_notes": "false"}, [empty]),
            ({"has_notes": "invalid"}, [empty, content]),
        ]:
            with self.subTest(params=params):
                self.assertResults(params, expected, "linkding:bookmark-archived")


class HasNotesWebCompatibilityTestCase(
    TestCase, BookmarkFactoryMixin, BookmarkListTestMixin
):
    def test_search_form_preserves_filter_as_hidden_field(self):
        request = RequestFactory().get("/")
        request.user = self.get_or_create_test_user()
        for value in ["true", "false"]:
            with self.subTest(value=value):
                search = BookmarkSearch.from_request(
                    request, QueryDict(urlencode({"q": "needle", "has_notes": value}))
                )
                form = BookmarkSearchForm(search, editable_fields=["q"])
                hidden = {field.name: field.value() for field in form.hidden_fields()}
                self.assertEqual(hidden, {"has_notes": value})

    def test_default_web_list_still_renders_with_all_notes_states(self):
        self.client.force_login(self.get_or_create_test_user())
        bookmarks = [
            self.setup_bookmark(notes=""),
            self.setup_bookmark(notes="A note"),
        ]
        response = self.client.get(reverse("linkding:bookmarks.index"))
        self.assertEqual(response.status_code, 200)
        self.assertVisibleBookmarks(response, bookmarks)
