from rest_framework.pagination import CursorPagination, PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class FeedPagination(CursorPagination):
    """Cursor pagination for the social feed, which is append-heavy.

    Offset pagination would shift items under the reader every time somebody
    posts, causing duplicates and skips while scrolling.
    """

    page_size = 20
    max_page_size = 50
    page_size_query_param = "page_size"
    ordering = "-created_at"
