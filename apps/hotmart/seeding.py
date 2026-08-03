"""Pure Hotmart -> wizard seed mapping (see openspec design:
ai-landing-from-hotmart-product, "Fixed 3 questions, server-allowlisted"
and the seed-mapping decision). No I/O, no AI call — this module only
turns a `HotmartProduct`/`HotmartOffer` pair plus the seller's 3 fixed
answers into the `description`/`answers` shape
`WizardAIService.stream_generate_document` already accepts unchanged.

Hotmart's real API supplies very little (name, status, and per-offer
price/description that is often blank) — every blank/missing field is
OMITTED here rather than replaced with placeholder text, so the AI is
never handed a fabricated fact to build on (see prompts.py's "never invent
facts" rule).
"""

from __future__ import annotations

from .client import HotmartOffer, HotmartProduct


def build_generation_seed(
    product: HotmartProduct,
    offer: HotmartOffer | None,
    answers: dict,
) -> tuple[str, dict]:
    """Returns (description, seed_answers) for `stream_generate_document`.

    `answers` is passed through unchanged — it is already the fixed
    3-question dict (`audience`, `promise`, `offer_details`) validated by
    `LandingGenerateRequestSerializer` before this function ever runs.
    """
    sentences = [f'Landing de venta para el producto de Hotmart "{product.name}".']

    if offer is not None and offer.price:
        price_sentence = f"Precio: {offer.price}"
        if offer.currency:
            price_sentence += f" {offer.currency}"
        sentences.append(price_sentence + ".")

    if offer is not None and offer.description and offer.description.strip():
        sentences.append(offer.description.strip())

    description = " ".join(sentences)
    return description, dict(answers)
