"""RED tests for apps/hotmart/seeding.py (see spec's "Seed Mapping From
Product + Offer" requirement: build wizard seed data from thin Hotmart
product/offer facts without inventing anything the source data lacks)."""

from apps.hotmart.client import HotmartOffer, HotmartProduct
from apps.hotmart.seeding import build_generation_seed


def _product(**overrides):
    defaults = dict(
        id="prod-1",
        ucode="ucode-1",
        name="Curso de Marketing Digital",
        is_active=True,
        checkout_url="",
    )
    defaults.update(overrides)
    return HotmartProduct(**defaults)


def _offer(**overrides):
    defaults = dict(id="offer-1", price="97.00", currency="USD", description="")
    defaults.update(overrides)
    return HotmartOffer(**defaults)


def _answers(**overrides):
    defaults = {"audience": "emprendedores", "promise": "duplicar sus ventas", "offer_details": ""}
    defaults.update(overrides)
    return defaults


class TestBuildGenerationSeed:
    def test_includes_product_name(self):
        description, _ = build_generation_seed(_product(), _offer(), _answers())

        assert "Curso de Marketing Digital" in description

    def test_includes_offer_price_and_currency_when_present(self):
        description, _ = build_generation_seed(
            _product(), _offer(price="97.00", currency="USD"), _answers()
        )

        assert "97.00" in description
        assert "USD" in description

    def test_omits_price_when_blank_rather_than_inventing_one(self):
        description, _ = build_generation_seed(_product(), _offer(price=""), _answers())

        assert "Precio" not in description

    def test_includes_offer_description_when_non_blank(self):
        description, _ = build_generation_seed(
            _product(), _offer(description="Acceso de por vida"), _answers()
        )

        assert "Acceso de por vida" in description

    def test_omits_offer_description_when_blank(self):
        with_description, _ = build_generation_seed(
            _product(), _offer(price="", description="Acceso de por vida"), _answers()
        )
        without_description, _ = build_generation_seed(
            _product(), _offer(price="", description=""), _answers()
        )

        # No fabricated placeholder text stands in for the missing description.
        assert "Acceso de por vida" in with_description
        assert without_description == with_description.replace(" Acceso de por vida", "")

    def test_handles_no_offer_at_all(self):
        description, _ = build_generation_seed(_product(), None, _answers())

        assert "Curso de Marketing Digital" in description

    def test_answers_are_passed_through(self):
        answers = _answers(audience="dueños de pymes", promise="ahorrar tiempo")

        _, seed_answers = build_generation_seed(_product(), _offer(), answers)

        assert seed_answers["audience"] == "dueños de pymes"
        assert seed_answers["promise"] == "ahorrar tiempo"

    def test_never_invents_facts_not_supplied(self):
        description, _ = build_generation_seed(
            _product(), _offer(price="", currency="", description=""), _answers()
        )

        assert "gratis" not in description.lower()
        assert "descuento" not in description.lower()
