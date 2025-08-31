import openai

from src.bookings import Bookings

PROMPT = """
Extract ALL the bookings of the athletics track from the image.
If the image does not contain information about athletics track bookings, return `{"bookings": []}`
Make sure to get the year right, it may appear at the top of the image.
ONLY EXTRACT ATHLETICS TRACK BOOKINGS, if the image relates to some other type of bookings, return `{"bookings": []}`
"""


client = openai.Client()


def extract_bookings(img_url: str) -> Bookings | None:
    response = client.responses.parse(
        model="gpt-4o",
        input=[
            {"role": "system", "content": PROMPT},
            {  # type: ignore
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": img_url},
                ],
            },
        ],
        text_format=Bookings,
    )
    return response.output_parsed
