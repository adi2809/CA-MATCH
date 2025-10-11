# Course Assistant Matching Platform

This repository contains a lightweight full-stack prototype for matching Columbia IEOR applicants to course assistant roles while giving administrators convenient tools to manage offerings.

## Features

### Applicant experience
- Secure registration and UNI-based authentication.
- Profile management with degree, level of study, areas of interest, resume/transcript links, and profile photo URL.
- Drag-friendly interface to capture ordered course preferences across tracks.
- Real-time course catalogue lookup sourced from administrator updates.

### Administrator console
- Intuitive dashboard to add/edit courses, adjust vacancies, and import CSV rosters.
- Launch the matching engine to generate optimal CA placements while respecting preferences and capacity.
- Manual override for assignments and quick email composition to notify students and instructors.
- Assignment table summarizing student and course contact details.

### Matching engine
The FastAPI backend implements a scoring-based assignment engine that:
- Rewards higher-ranked preferences and alignment with declared interest tracks.
- Prioritizes applicants with uploaded resume and transcript links.
- Respects course vacancy limits and avoids duplicate assignments.

## Project structure
```
backend/
  app/
    core/            # security helpers
    routers/         # FastAPI routers for auth, student, admin flows
    services/        # matching engine implementation
    database.py      # SQLAlchemy engine and session helpers
    main.py          # FastAPI app factory
frontend/
  index.html         # Single-page application shell
  styles.css         # Modern responsive styling
  app.js             # Dashboard logic & API integration
```

## Getting started

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The server exposes REST endpoints under `http://localhost:8000/api` and persists data to a local SQLite database (`ca_match.db`).

### Frontend
Serve the static files with any HTTP server (e.g., `python -m http.server` from the `frontend/` folder) and open `http://localhost:8000` or whichever port you use. Update `API_BASE` inside `frontend/app.js` if the backend runs on another host/port.

## Matching algorithm tuning
The current scoring model is intentionally simple to keep the prototype concise. You can improve results by:
- Parsing resume/transcript documents with OCR/LLM pipelines to infer relevant skills.
- Incorporating GPA and grade thresholds per course before scoring.
- Adding instructor feedback loops to weight certain applicants.
- Logging matching outcomes to support fairness audits.

## Testing
For manual smoke tests:
1. Register an administrator and a student through the UI.
2. Populate student profile fields and submit course preferences.
3. Create or import courses as an administrator, update vacancies, and run the matcher.
4. Review the assignments table and compose an email summary.

Automated tests are not yet included; contributions are welcome.
