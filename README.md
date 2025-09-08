# Extract BPMA bookings
Use an LLM to extract track bookings for BPMA (Battersea Park Millennium Arena) fromm an image published on the website and push to events to a google calendar

## How it works
1. **Scrape website** - Find athletics track booking images on the BPMA website
2. **Check for new content** - Download image and compare hash with S3 to avoid duplicates
3. **Extract bookings** - Use Gemini AI to extract structured booking data from the image
4. **Increment bookings** - Compare new bookings with existing events in Google Calendar to decide which events to delete and which to insert. 
5. **Convert to events** - Transform bookings into Google Calendar event format
6. **Push to calendar** - Create calendar events using Google Calendar API
7. **Deploy & schedule** - Run as AWS Lambda function for automated processing

### Incrementality
A new bookings image is assumed to be a complete replacement for any bookings in the months it covers. For example, if an image contains bookings for January and February:
- any existing events in the calendar for January and February that do not appear in the new bookings will be deleted
- any new events that do not appear in the calendar will be inserted
- identical events will be left unchanged
- any events in other months (e.g. March) will be unaffected.

This logic is based on the `min` and `max` dates found in the extracted bookings. For example, if the extracted bookings contain dates `2023-01-15`, `2023-01-20`, and `2023-02-10`, the system will consider the date range to be from `2023-01-01` to `2023-03-01`. All existing calendar events within this range are subject to incrementality checks and could be deleted.

## Setup

#### Configure python project
```bash
uv sync
```

#### Configure env
`.env`
```
OPENAI_API_KEY="..."
GEMINI_API_KEY="..."
CALENDAR_ID="..."
GOOGLE_SERVICE_ACCOUNT_JSON="..."
S3_BUCKET_NAME="..."
```

## Run locally
Run the app
```bash
make run
```
Run LLM evals
```bash
make eval
```

## Deployment
#### Push variables in `.env` to AWS SSM
```bash
make push-ssm
```
Build image, push to ECR and update lambda
```bash
make deploy
```
