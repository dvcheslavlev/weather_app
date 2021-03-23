from django.urls import path
from .import views


urlpatterns = [
    path("", views.IndexView.as_view(), name='index'),
    # path("<int:pk>/", views.ArticleDetailView.as_view(), name='news_article'),
    # path("add_article/", views.AddArticleFormView.as_view(), name='add_article'),
    # path("<int:article_id>/edit/", views.ArticleEditFormView.as_view(), name='edit_article')
]