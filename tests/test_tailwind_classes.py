from apps.ai_assistant.sanitize import SanitizationError
from apps.ai_assistant.tailwind_classes import (
    check_class_list,
    is_allowed_tailwind_class,
    iter_all_allowed_classes,
)


def test_allows_representative_classes_from_each_family():
    for token in [
        "flex",
        "p-4",
        "m-2",
        "gap-4",
        "w-1/2",
        "h-full",
        "min-w-0",
        "text-lg",
        "font-bold",
        "leading-normal",
        "tracking-wide",
        "rounded-lg",
        "shadow-md",
        "opacity-50",
        "blur-sm",
        "grid-cols-3",
        "col-span-2",
        "order-1",
        "aspect-square",
        "bg-blue-500",
        "text-white",
        "border-red-600",
        "relative",
        "top-0",
        "z-10",
        "cursor-pointer",
        "transition",
        "duration-300",
    ]:
        assert is_allowed_tailwind_class(token), token


def test_rejects_made_up_or_out_of_scale_classes():
    for token in ["bg-hackery", "p-999", "w-[100vw]", "made-up-utility", ""]:
        assert not is_allowed_tailwind_class(token), token


def test_allows_max_width_named_scale_but_not_on_plain_width():
    for token in ["max-w-4xl", "max-w-prose", "max-w-screen", "max-w-none", "max-w-4"]:
        assert is_allowed_tailwind_class(token), token
    assert not is_allowed_tailwind_class("w-4xl")


def test_allows_one_responsive_and_one_state_prefix_combined():
    assert is_allowed_tailwind_class("md:flex-row")
    assert is_allowed_tailwind_class("hover:bg-blue-600")
    assert is_allowed_tailwind_class("md:hover:bg-blue-600")


def test_rejects_two_prefixes_of_the_same_kind():
    assert not is_allowed_tailwind_class("sm:md:flex")
    assert not is_allowed_tailwind_class("hover:focus:bg-blue-600")


def test_css_variable_bridge_allows_known_variables_only():
    assert is_allowed_tailwind_class("bg-[var(--color-primary)]")
    assert not is_allowed_tailwind_class("bg-[var(--totally-made-up)]")
    assert not is_allowed_tailwind_class("bg-[url(evil)]")
    assert not is_allowed_tailwind_class("bg-[#ff0000]")


def test_check_class_list_accepts_valid_list():
    check_class_list(["flex", "p-4", "bg-blue-500"])


def test_check_class_list_rejects_disallowed_entry():
    try:
        check_class_list(["flex", "bg-hackery"])
        raise AssertionError("expected SanitizationError")
    except SanitizationError:
        pass


def test_check_class_list_enforces_max_classes():
    try:
        check_class_list([f"p-{i % 2}" for i in range(25)])
        raise AssertionError("expected SanitizationError")
    except SanitizationError:
        pass


def test_iter_all_allowed_classes_matches_validator():
    # Spot-check: every generated class must itself pass the validator
    # (they're derived from the same tables, so this should always hold).
    generated = list(iter_all_allowed_classes())
    assert len(generated) > 1000
    for token in generated[::500]:
        assert is_allowed_tailwind_class(token), token
