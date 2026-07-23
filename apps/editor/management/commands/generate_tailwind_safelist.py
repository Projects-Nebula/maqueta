"""Materialize the Tailwind class allowlist into a sentinel file the
Tailwind CLI treats as a content source (see tailwind-input.css's @source
directive) — see REFACTOR.md Section 1.2/3.3 for why this is necessary
(AI-chosen class names never appear in any file Tailwind could otherwise
scan)."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_assistant.tailwind_classes import iter_all_allowed_classes

SAFELIST_PATH = Path(settings.BASE_DIR) / "static" / "editor" / ".tailwind-safelist.txt"


class Command(BaseCommand):
    help = "Write every allowed Tailwind class to the safelist file consumed by the CSS build."

    def handle(self, *args, **options):
        classes = sorted(iter_all_allowed_classes())
        SAFELIST_PATH.write_text("\n".join(classes) + "\n")
        self.stdout.write(self.style.SUCCESS(f"wrote {len(classes)} classes to {SAFELIST_PATH}"))
