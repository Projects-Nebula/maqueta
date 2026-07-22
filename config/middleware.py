"""Small project-level middleware."""

from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """Attach a Content-Security-Policy header when one is configured.

    ponytail: a whole CSP library is overkill for one static header; a
    per-view nonce policy can replace this if inline scripts ever appear.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = getattr(settings, "CSP_HEADER", "")

    def __call__(self, request):
        response = self.get_response(request)
        if self.policy and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self.policy
        return response
