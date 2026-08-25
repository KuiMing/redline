from server import main
from server.card_presentation import (
    ACTION_CSV_PATH,
    CARD_PRESENTATION_CATALOG,
    SUPPORT_CSV_PATH,
    load_card_presentation_catalog,
)


def test_card_presentation_catalog_loads_canonical_card_rows():
    catalog = load_card_presentation_catalog()

    assert len(catalog) == 55
    assert catalog["合作談判"] == {
        "name": "合作談判",
        "color": "藍",
        "kind": "指揮",
        "strength": "乙級",
        "cost_text": "資金2+宣傳2",
        "effect_text": "選擇任1位玩家，您與該玩家各抽1張牌。您獲得2點宣傳。",
        "resource_text": "宣傳1",
        "position_text": "隨機購買區",
        "meaning_text": "有建設性的合作提議",
        "count_text": "5",
    }
    assert catalog["紅軍奧援"]["count_text"] == "1"
    assert catalog["紅軍奧援"]["resource_text"] == "提供1資金+1宣傳；打出後依陣營放入對應棄牌堆"


def test_support_card_presentation_preserves_printed_variants():
    for name in (
        "英美奧援",
        "東洋奧援",
        "南洋奧援",
        "印度奧援",
        "天方奧援",
        "歐洲奧援",
        "北國奧援",
        "臺灣奧援",
    ):
        card = CARD_PRESENTATION_CATALOG[name]
        assert card["count_text"] == "8"
        assert len(card["support_variants"]) == 2
        assert sum(int(variant["copies"]) for variant in card["support_variants"]) == 8


def test_main_keeps_card_presentation_compatibility_exports():
    assert main.ACTION_CSV_PATH == ACTION_CSV_PATH
    assert main.SUPPORT_CSV_PATH == SUPPORT_CSV_PATH
    assert main.CARD_PRESENTATION_CATALOG is CARD_PRESENTATION_CATALOG
    assert main._load_card_presentation_catalog() == CARD_PRESENTATION_CATALOG
    assert main.card_presentation() == {"cards": CARD_PRESENTATION_CATALOG}
