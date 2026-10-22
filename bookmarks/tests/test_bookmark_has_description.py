from urllib.parse import urlencode

from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from bookmarks.forms import BookmarkSearchForm
from bookmarks.models import BookmarkSearch
from bookmarks.tests.helpers import (
    BookmarkFactoryMixin,
    BookmarkListTestMixin,
    LinkdingApiTestCase,
)


class HasDescriptionApiTestCase(LinkdingApiTestCase, BookmarkFactoryMixin):
    def setUp(self):
        self.authenticate()
        other_user = self.setup_user(enable_sharing=True, enable_public_sharing=True)
        self.bookmarks = {}
        for archived in (False, True):
            self.bookmarks[archived] = [
                self.setup_bookmark(
                    description=description, title="matching", is_archived=archived
                )
                for description in ("", "A description", " \t\n")
            ]
            for description in ("", "Other description"):
                self.setup_bookmark(
                    user=other_user,
                    description=description,
                    title="matching",
                    is_archived=archived,
                    shared=True,
                )

    def assert_filter_results(self, params, expected_indices):
        for archived, endpoint in (
            (False, "linkding:bookmark-list"),
            (True, "linkding:bookmark-archived"),
        ):
            with self.subTest(archived=archived, params=params):
                response = self.get(reverse(endpoint) + "?" + urlencode(params))
                expected = [self.bookmarks[archived][i].pk for i in expected_indices]
                self.assertCountEqual(
                    [item["id"] for item in response.data["results"]], expected
                )
                self.assertEqual(response.data["count"], len(expected))

    def test_absent_parameter_preserves_results_and_user_archive_isolation(self):
        self.assert_filter_results({}, [0, 1, 2])

    def test_true_and_yes_include_nonempty_and_whitespace_descriptions(self):
        for value in ("true", "yes"):
            self.assert_filter_results({"has_description": value}, [1, 2])

    def test_false_and_no_include_only_empty_descriptions(self):
        for value in ("false", "no"):
            self.assert_filter_results({"has_description": value}, [0])

    def test_empty_invalid_and_uppercase_values_disable_filter(self):
        for value in ("", "invalid", "TRUE", "FALSE", "1", "0", "off"):
            self.assert_filter_results({"has_description": value}, [0, 1, 2])

    def test_description_and_notes_filters_intersect(self):
        for bookmarks in self.bookmarks.values():
            for bookmark, notes in zip(bookmarks, ("A note", "", "A note"), strict=True):
                bookmark.notes = notes
                bookmark.save()
        for description, notes, expected in (
            ("true", "true", [2]),
            ("true", "false", [1]),
            ("false", "true", [0]),
            ("false", "false", []),
        ):
            self.assert_filter_results(
                {"has_description": description, "has_notes": notes}, expected
            )

    def test_filter_combines_with_search(self):
        self.assert_filter_results({"has_description": "true", "q": "matching"}, [1, 2])
        self.assert_filter_results({"has_description": "false", "q": "matching"}, [0])
        self.assert_filter_results({"has_description": "true", "q": "missing"}, [])
        self.assert_filter_results({"has_description": "false", "q": "missing"}, [])


class HasDescriptionSearchTestCase(TestCase, BookmarkFactoryMixin, BookmarkListTestMixin):
    def test_request_filter_survives_query_params_and_hidden_form_fields(self):
        for value in ("true", "false", "yes", "no"):
            with self.subTest(value=value):
                search = BookmarkSearch.from_request(
                    None, QueryDict(f"q=matching&has_description={value}")
                )
                self.assertEqual(
                    search.query_params, {"q": "matching", "has_description": value}
                )
                form = BookmarkSearchForm(search, editable_fields=["q"])
                self.assertEqual(form["has_description"].initial, value)
                self.assertEqual(form.hidden_fields(), [form["has_description"]])

    def test_both_filters_survive_search_form(self):
        params = {"q": "matching", "has_description": "true", "has_notes": "false"}
        search = BookmarkSearch.from_request(None, QueryDict(urlencode(params)))
        self.assertEqual(search.query_params, params)
        form = BookmarkSearchForm(search, editable_fields=["q"])
        self.assertEqual(
            {field.name: field.value() for field in form.hidden_fields()},
            {"has_description": "true", "has_notes": "false"},
        )

    def test_default_web_list_renders_without_filter(self):
        self.client.force_login(self.get_or_create_test_user())
        bookmarks = [
            self.setup_bookmark(description=""),
            self.setup_bookmark(description="A description"),
        ]
        response = self.client.get(reverse("linkding:bookmarks.index"))
        self.assertEqual(response.status_code, 200)
        self.assertVisibleBookmarks(response, bookmarks)

    def test_filtered_web_list_renders(self):
        self.client.force_login(self.get_or_create_test_user())
        empty = self.setup_bookmark(description="")
        described = self.setup_bookmark(description="A description")
        for value, expected in (("true", described), ("false", empty)):
            with self.subTest(value=value):
                response = self.client.get(
                    reverse("linkding:bookmarks.index"), {"has_description": value}
                )
                self.assertEqual(response.status_code, 200)
                self.assertVisibleBookmarks(response, [expected])
