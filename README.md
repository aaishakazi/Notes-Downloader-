# 📚 Manipal D2L Notes Downloader

Automatically downloads all unit PDFs for every course in a semester from the Manipal University Jaipur online learning portal (learning.onlinemanipal.com).

---

## ✨ What It Does

- Logs into your Manipal D2L account (Microsoft SSO + Authenticator)
- Fetches all your enrolled courses for a semester
- Downloads all unit PDFs for each course
- Saves them neatly organized:

```
Downloads/
└── BCA Sem-4 Notes/
    ├── Python Programming/
    │   ├── Unit 1 - Introduction to Python.pdf
    │   ├── Unit 2 - Python Basics.pdf
    │   └── ...
    ├── Introduction to Network Security/
    │   ├── Unit 1.pdf
    │   ├── Unit 2.pdf
    │   └── ...
    └── ...
```

- Saves your login session so you only approve MFA **once every few days**
- Downloads 2 courses at a time for speed

---

## 🛠️ Requirements

- Python 3.9+
- Node.js (any recent version)
- A Manipal University Jaipur online student account

---

## 🚀 Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/manipal-notes-downloader.git
cd manipal-notes-downloader
```

### 2. Install Python dependencies

```bash
pip install playwright python-dotenv
playwright install chromium
```

### 3. Create your `.env` file

Create a file named `.env` in the project folder and add your credentials:

```env
UNI_EMAIL=yourrollnumber@mujonline.edu.in
UNI_PASSWORD=yourpassword
```


### 4. Configure your semester

Open `main.py` and update the `SAVE_DIR` variable to match your semester:

```python
SAVE_DIR = Path.home() / "Downloads" / "BCA Sem-4 Notes"
```

Change `Sem-4` to whatever semester you're in or Write it in SEM_TAB variable



---

## ▶️ Running It

```bash
python main.py
```

### First run

The browser will open and automatically fill in your email and password. When the **Microsoft Authenticator** prompt appears on your phone, approve it. After that, the script saves your session and runs fully automatically.

### All future runs

No login needed — the saved session is reused automatically. You'll only need to approve MFA again if the session expires (usually every few days).

---

## 📁 Output

PDFs are saved to your `Downloads` folder under a folder named after your semester, organized by course. Files are named like:

- `Unit 1 - Introduction to Python.pdf`
- `Unit 3 - Assemblers.pdf`
- `Unit 1.pdf` *(when no description is available)*

---

## ⚙️ Configuration Options

All config is at the top of `main.py`:

| Variable | What it does |
|---|---|
| `SAVE_DIR` | Where notes are saved |
| `SESSION_FILE` | Where login session is stored (`session.json`) |
| `LAB_KEYWORDS` | Course name keywords to skip (e.g. `"lab"`, `"practical"`) |

---

## ❓ Troubleshooting

**Session expired / login fails**
Delete `session.json` and run again. You'll be prompted to approve MFA once more.

**Some PDFs are missing**
Re-run the script — it skips already-downloaded files and only downloads what's missing. Corrupt files (under 50KB) are automatically deleted and re-downloaded.

**Browser crashes / memory errors**
The semaphore is set to download 2 courses at a time. If you have a low-RAM machine, open `main.py` and change:
```python
semaphore = asyncio.Semaphore(2)
# change 2 to 1 for sequential downloading
semaphore = asyncio.Semaphore(1)
```

**`playwright install` not found**
Make sure you installed playwright in the right environment:
```bash
pip install playwright
python -m playwright install chromium
```

---

## 🔒 Privacy & Security

- Your credentials are stored only in your local `.env` file
- The session cookie is stored in `session.json` locally
- Nothing is sent anywhere except to the Manipal D2L portal
- The `.gitignore` ensures `.env` and `session.json` are never committed

---


## 🎓 Who Is This For?

Students at **Manipal University Jaipur** (Online/Distance) enrolled through the Centre for Distance and Online Education, using the D2L Brightspace LMS at [learning.onlinemanipal.com](https://learning.onlinemanipal.com).

May also work for other Manipal campuses using the same D2L portal — update `BASE_URL` in `main.py` if needed.

---

## 📄 License

MIT — free to use, modify, and share.
