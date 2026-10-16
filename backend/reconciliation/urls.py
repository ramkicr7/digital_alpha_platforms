from django.urls import path

from . import views

urlpatterns = [
    path("transactions/", views.TransactionListView.as_view()),
    path("transactions/<int:pk>/ignore/", views.TransactionIgnoreView.as_view()),
    path("line-items/", views.LineItemListView.as_view()),
    path("matches/<int:pk>/approve/", views.MatchApproveView.as_view()),
    path("matches/<int:pk>/reject/", views.MatchRejectView.as_view()),
    path("imports/", views.ImportView.as_view()),
]