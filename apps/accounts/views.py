from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

# ponytail: no new dependency (django-axes) for this — Django's own cache
# framework already does per-IP counting well enough; a 5-minute lockout
# after 5 failures is a brute-force speed bump, not a hard security
# boundary that needs Redis-backed cross-worker consistency.
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 300


class LoginForm(AuthenticationForm):
    """Authentication fields with browser-friendly credential semantics."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "username",
                "autocapitalize": "none",
                "aria-describedby": "loginError",
            }
        )
        self.fields["password"].widget.attrs.update(
            {"autocomplete": "current-password", "aria-describedby": "loginError"}
        )


class SignupForm(UserCreationForm):
    """Signup fields with browser-friendly credential semantics."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "username",
                "autocapitalize": "none",
                "aria-describedby": "signupUsernameError",
            }
        )
        self.fields["password1"].widget.attrs.update(
            {"autocomplete": "new-password", "aria-describedby": "signupPasswordError"}
        )
        self.fields["password2"].widget.attrs.update(
            {"autocomplete": "new-password", "aria-describedby": "signupPasswordConfirmError"}
        )


class LoginView(auth_views.LoginView):
    """Login page. Honors ?next= so activation can bounce through login.

    ponytail: Django's auth views already do everything; we only point them
    at our templates and a safe default redirect. Per-IP attempt throttling
    added on top since every other public-facing endpoint in this project
    is already rate-limited and login wasn't.
    """

    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def _throttle_key(self, request):
        return f"login-attempts:{request.META.get('REMOTE_ADDR', 'unknown')}"

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            attempts = cache.get(self._throttle_key(request), 0)
            if attempts >= LOGIN_ATTEMPT_LIMIT:
                return HttpResponse(
                    "Demasiados intentos. Probá de nuevo en unos minutos.", status=429
                )
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._throttle_key(self.request)
        cache.set(key, cache.get(key, 0) + 1, LOGIN_ATTEMPT_WINDOW_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._throttle_key(self.request))
        return super().form_valid(form)


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("accounts:login")


class SignupView(CreateView):
    """Signup page. Stdlib UserCreationForm (username + password + confirm,
    runs AUTH_PASSWORD_VALIDATORS) — no custom fields needed since the app
    has no email/profile requirements yet. Logs the new user in immediately
    so signup lands them straight in the editor, same as login does.
    """

    form_class = SignupForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("editor:editor")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(str(self.success_url))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
