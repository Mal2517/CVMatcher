# CV ATS Matcher

Log in, paste a job ad (or link), upload a CV (PDF, DOCX, photo), get an ATS match estimate, missing keywords and fixes.
Accounts and credits live in Supabase (free). Payments via Paynow EcoCash.

## 1. Supabase (5 min)
1. Create a free project at supabase.com.
2. SQL Editor > New query > paste `supabase_schema.sql` > Run.
3. Project Settings > API: copy the Project URL, the `anon` key and the `service_role` key.
4. Authentication > Providers > Email is on by default. For quick testing you can turn off "Confirm email".
5. After deploying, set Authentication > URL Configuration > Site URL to your Render URL.

## 2. Run locally (optional)
    cp .env.example .env   # fill in, then: export $(grep -v '^#' .env | xargs)
    pip install -r requirements.txt
    uvicorn app.main:app --reload

## 3. Deploy free on Render
1. Push this folder to GitHub.
2. Render > New > Web Service > choose the repo (it uses the Dockerfile, which includes OCR).
3. Add env vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `BASE_URL` (your Render URL), `PAYNOW_ID`, `PAYNOW_KEY`.
4. Never commit the service key. It is secret; only the anon key reaches the browser.

## Notes
- Each new account gets 1 free check. Change the `1` in `get_credits` in `supabase_schema.sql` to change that.
- Credits are only changed by the backend through locked-down database functions.
- Free Render sleeps when idle (first load ~30 s).
- Score = keywords 50, experience 25, education 15, format 10. Edit the skills list in `app/scoring.py` for your market.
- It is an estimate, not a guarantee of how a real ATS will rank a CV.
