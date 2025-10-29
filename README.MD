
# Country Data & GDP Summary Service

## Overview

This project is a **FastAPI-based service** designed to fetch, store, and visualize global country data — including GDP, population, and currency exchange rates.  
It connects to external APIs, persists records in a local database via SQLAlchemy, and generates image summaries of key economic data.

The app supports data refresh operations, country-specific queries, and automatic image generation of top-performing countries by GDP.

---

##  Core Features

Fetches and aggregates live data on countries, population, and currencies.
`/countries/refresh` endpoint updates or adds new countries intelligently (no duplication).
Uses SQLite (or any SQLAlchemy-compatible DB) for persistence.
Generates visual summary images (top 5 GDP countries, etc.).
Tracks last refresh time.
Asynchronous implementation for non-blocking I/O operations.
-  Integrated rate limiting to prevent abuse.
Fully typed Python 3.10+ code with Pydantic models.

---

## Project Structure

```
hng13_3/
├── main.py
├── database.py
├── models.py
├── schemas.py
├── utils/
│   ├── api_client.py
│   ├── image_utils.py
│   └── helpers.py
├── requirements.txt
└── README.md
```

---

## Tech Stack

| Component | Technology |
|------------|-------------|
| **Backend** | FastAPI |
| **Database** | SQLAlchemy ORM + SQLite |
| **HTTP Client** | `httpx` (async) |
| **Data Models** | Pydantic |
| **Visualization** | Pillow / Matplotlib |
| **Rate Limiting** | slowapi |
| **Runtime** | Python 3.10+ |

---

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/hng13_3.git
   cd hng13_3
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate      # macOS/Linux
   venv\Scripts\activate       # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file:
   ```env
   DATABASE_URL=sqlite:///./countries.db
   EXTERNAL_API_KEY=your_api_key_here
   DEBUG=True
   ```

5. **Initialize the database**
   ```bash
   python
   >>> from database import Base, engine
   >>> Base.metadata.create_all(bind=engine)
   >>> exit()
   ```

---

## Running the Application

```bash
uvicorn main:app --reload
```
Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Key Endpoints

### `POST /countries/refresh`
Fetches and updates all country data.

### `GET /countries`
Lists all countries.

### `GET /countries/{name}`
Returns details for a specific country.

### `GET /summary/image`
Returns generated GDP summary image.

---

## Image Generation Logic

Triggered automatically after each `/countries/refresh` call.  
The generated image shows the top 5 countries by GDP.

---

## Rate Limiting

`/countries/refresh` → 8 requests per minute.

---

## Testing

```bash
pytest --maxfail=1 --disable-warnings -q
```

---

## Troubleshooting

| Problem | Possible Fix |
|----------|---------------|
| Database locked | Use single-threaded worker |
| API timeout | Retry later |
| Image not generated | Ensure Pillow installed |

---

## Contribution

1. Fork the repo  
2. Create a branch  
3. Commit, push, and open a PR

---

## License

MIT License © 2025 — James Kehinde

---

## Contact

- Author: **James Kehinde**
- Email: contact@yourdomain.com
- GitHub: [https://github.com/yourusername](https://github.com/yourusername)
