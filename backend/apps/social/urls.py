from django.urls import path

from .views import CommentViewSet, PostViewSet

post_list = PostViewSet.as_view({"get": "list", "post": "create"})
post_detail = PostViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
post_react = PostViewSet.as_view({"post": "react"})

comment_list = CommentViewSet.as_view({"get": "list", "post": "create"})
comment_detail = CommentViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
comment_react = CommentViewSet.as_view({"post": "react"})

urlpatterns = [
    path("competitions/<uuid:competition_pk>/posts", post_list, name="post-list"),
    path(
        "competitions/<uuid:competition_pk>/posts/<uuid:pk>",
        post_detail,
        name="post-detail",
    ),
    path(
        "competitions/<uuid:competition_pk>/posts/<uuid:pk>/react",
        post_react,
        name="post-react",
    ),
    path("posts/<uuid:post_pk>/comments", comment_list, name="comment-list"),
    path("posts/<uuid:post_pk>/comments/<uuid:pk>", comment_detail, name="comment-detail"),
    path(
        "posts/<uuid:post_pk>/comments/<uuid:pk>/react",
        comment_react,
        name="comment-react",
    ),
]
