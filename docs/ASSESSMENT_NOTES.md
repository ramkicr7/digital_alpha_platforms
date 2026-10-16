# RMBI Capital Call Reconciliation — Assessment Notes

## 1. Application Overview

- **App name:** RMBI Capital Call Reconciliation Platform
- **Purpose:** Reconcile bank statement transactions against capital-call line items for different organizations. The application supports CSV imports, transaction matching, review of suggested matches, and approval, rejection, or ignoring of transactions.
- **Architecture:** React frontend, Django REST Framework backend, and PostgreSQL database.

## 2. Prerequisites

- **Python:** Python 3.12 or another version compatible with the project's dependencies. The development environment used Python 3.14.6; verify compatibility when setting up a fresh environment.
- **Node.js:** A version compatible with the installed Vite and React dependencies.
- **PostgreSQL:** PostgreSQL 18 was used for local database setup.
- **Git:** Required to clone the repository.

## 3. Setup from a Fresh Clone

### Backend

1. Clone the repository and navigate to the backend directory.
2. Create and activate a Python virtual environment.
3. Install dependencies from `requirements.txt`.
4. Configure the database connection and environment variables.
5. Run database migrations.
6. Populate the demo data.

Example commands for Windows PowerShell:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py seed_demo
```

Configure the required environment variables according to the project's settings and `.env.example`, if present.

### Frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Configure the frontend API base URL and development proxy according to the existing frontend configuration.

## 4. Environment Variables

- Refer to `.env.example` if provided in the repository.
- Configure the PostgreSQL database name, username, password, host, and port as required by the backend settings.
- Configure Django settings such as the secret key and debug mode as appropriate for the environment.
- Configure the frontend API base URL if required.
- Never commit actual passwords, secret keys, API tokens, or production credentials.

Verify the exact variable names in `backend/config/settings.py` and the frontend API client before setting up a fresh clone.

## 5. Seed Data

- **Command:** `python manage.py seed_demo`
- **Organizations:** Northwind Ventures (`northwind`) and Bluebird Capital (`bluebird`).
- **Capital-call line items:** Seven records in total: six for Northwind Ventures and one for Bluebird Capital.
- **Expected behavior:** Repeated runs should not create duplicate organizations or line items with the same organization and reference.
- **Important limitation:** The current seed implementation uses `get_or_create()`. It does not automatically update existing records when their investor names, amounts, or dates differ from the demo definitions. Verify existing data before relying on it.

## 6. Running the Application

### Backend startup

From the `backend` directory:

```powershell
.\venv\Scripts\Activate.ps1
python manage.py runserver 127.0.0.1:8000
```

### Frontend startup

From the `frontend` directory:

```powershell
npm run dev
```

### Local URLs

- **Frontend:** `http://localhost:5173` (typical Vite development URL).
- **Backend:** `http://127.0.0.1:8000`.
- **API prefix:** `/api/`.

The frontend development proxy should forward `/api` requests to the Django server.

## 7. Running Tests

- **Django system check:** `python manage.py check`
- **Database migrations:** `python manage.py migrate`
- **Automated tests:** `python manage.py test`

A single command for all automated tests has not been verified. The commands above provide basic validation, but they do not guarantee that every reconciliation workflow is tested.

### Tests to verify

- Organization-header validation.
- Organization-specific transaction and line-item retrieval.
- CSV parsing and import validation.
- Duplicate transaction handling.
- Match suggestion and matching decisions.
- Approval and rejection behavior.
- Ignoring transactions.
- Invalid input and error handling.
- Data persistence and organization isolation.

Record actual test results before claiming these tests pass.

## 8. Data Model

The following describes the intended data responsibilities. Confirm the exact model fields and relationships in `backend/reconciliation/models.py`.

- **Organization:** Represents an organization whose transactions and capital-call records must remain isolated.
- **Capital call:** The broader funding request or capital-call concept, if represented as a separate model.
- **Capital-call line item:** An individual investor obligation associated with an organization, identified by a reference and containing investor and called-amount information.
- **Bank transaction:** A transaction imported from a bank statement, including fields such as date, description, amount, type, and bank reference where supported.
- **Match:** A suggested or confirmed relationship between a bank transaction and a capital-call line item, including its review status where supported.

Verify whether Capital Call and Match are separate database models or concepts represented by fields on existing models.

## 9. API Endpoints

The configured URL patterns include the following endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/transactions/` | List transactions for the selected organization. |
| GET | `/api/line-items/` | List capital-call line items for the selected organization. |
| POST | `/api/imports/` | Import a bank statement file. |
| POST | `/api/matches/<id>/approve/` | Approve a suggested match. |
| POST | `/api/matches/<id>/reject/` | Reject a suggested match. |
| POST | `/api/transactions/<id>/ignore/` | Ignore a transaction. |

### Organization header

Organization-specific requests use the `X-Organization` header. For example:

```http
X-Organization: northwind
```

The expected organization identifiers are `northwind` and `bluebird`, provided the database contains those records.

### Error handling

- A missing organization header is expected to produce a client error.
- An unknown organization identifier has returned a `404` response with the message `Organization not found` during development.
- Invalid CSV files and malformed input should be handled with meaningful error responses; verify the exact response formats against the implementation.

## 10. Assumptions and Trade-offs

### Assumptions

- Each organization must access only its own transaction and capital-call data.
- Bank statement transactions and capital-call reference records are distinct datasets.
- A bank transaction may require manual review if its investor, amount, reference, or date is ambiguous.
- An exact amount match alone may not establish that a transaction belongs to a particular capital-call line item.

### Design decisions

- Django provides the backend API and database integration.
- PostgreSQL stores persistent application data.
- React provides the user interface.
- A development proxy allows frontend API calls to reach the Django backend.
- A management command provides repeatable demo-data initialization.

### Known limitations

- The seed command does not update existing records when demo values change.
- The end-to-end frontend workflow and reconciliation behavior must be verified before claiming completion.
- Automated test coverage and the precise matching algorithm need to be confirmed from the current implementation.
- Local development server configuration is intended for development, not production deployment.

### Next steps

1. Verify organization slugs and seed-data contents.
2. Confirm that the transaction and line-item API endpoints return the correct organization-specific data.
3. Test CSV import, validation, and duplicate handling.
4. Verify approval, rejection, and ignore actions.
5. Run automated tests and document their actual results.
6. Confirm that the frontend and backend work together from a fresh clone.
7. Ensure the repository excludes credentials and local dependencies.

## 11. Integrity Statement

Replace this section with an accurate statement describing the assistance used during the assessment and your own implementation work, in accordance with the assessment rules.

