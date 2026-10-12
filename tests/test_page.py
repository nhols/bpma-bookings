from bpma.page import find_sheets

SITE = "https://images.squarespace-cdn.com/content/v1/64e49558c4c146501db389b9"
SHEET = f"{SITE}/9e68c66a-0a09-4ba7-a8f4-73400fc050d6/9+Athletics+Track+Bookings+-+June+2026.jpg"
LOGO = f"{SITE}/11111111-2222-3333-4444-555555555555/Enable+Logo.png"
HTML = f"""
<img data-src="{SHEET}" data-image="{SHEET}" src="{SHEET}" srcset="{SHEET}?format=100w 100w, {SHEET}?format=300w 300w">
<img src="{LOGO}">
"""


def test_finds_each_sheet_once_and_ignores_other_images() -> None:
    [ref] = find_sheets(HTML)
    assert ref.asset_id == "9e68c66a-0a09-4ba7-a8f4-73400fc050d6"
    assert ref.url == SHEET
    assert ref.filename == "9 Athletics Track Bookings - June 2026.jpg"


def test_a_page_without_sheets_finds_nothing() -> None:
    assert find_sheets(f'<img src="{LOGO}">') == []
