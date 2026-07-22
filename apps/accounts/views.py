from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


class LoginView(auth_views.LoginView):
    """Login page. Honors ?next= so activation can bounce through login.

    ponytail: Django's auth views already do everything; we only point them
    at our templates and a safe default redirect.
    """

    template_name = "registration/login.html"
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("accounts:login")
