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
A new bookings image is assumed to be a complete replacement for any bookings in the range of dates the bookings cover

When new bookings are observed, we load calendar events between the min and max dates of the new bookings and take the following actions:
- No action for new bookings that already have a corresponding calendar event
- We create a new calendar event for bookings that do not already have a corresponding calendar event
- We delete calendar events that are not represented in the new bookings

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
