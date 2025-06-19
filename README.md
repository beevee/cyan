# Google Doc Extractor

This small Python app downloads a Google Docs document as plain-text and extracts every line where a pair of square brackets contains only whitespace (e.g. `[   ] Do something`).  The text that follows the closing bracket on each such line is gathered and printed.

## Features
1. Authenticate to your Google account (OAuth 2.0 flow – one-time in browser).
2. Download a Google Docs document by URL.
3. Parse the document and collect matching lines.
4. Display the collected text in your terminal.

## Quick start

### 1. Clone & install
```bash
# inside an activated virtualenv or poetry shell
pip install -r requirements.txt
```

### 2. Create OAuth 2.0 credentials
1. Go to <https://console.cloud.google.com/apis/credentials>.
2. Click **Create Credentials → OAuth client ID → Desktop App**.
3. Download the JSON file and save it as `credentials.json` in the project root.
4. Make sure **Google Drive API** is enabled for your project.

The first run will open a browser window asking you to grant the app read-only access to Google Drive.
A token will be cached in `token.json` so you will not need to re-authenticate on subsequent runs.

### 3. Run the app
```bash
python main.py "https://docs.google.com/document/d/yourDocId/edit"
```

The script prints the list of extracted items.

## Example
```
[ ] Pick up milk
[   ] Finish report
[x] Done task
```
Only the first two lines match the pattern; the output will be:
```
Pick up milk
Finish report
```

---

© 2025 – MIT License 