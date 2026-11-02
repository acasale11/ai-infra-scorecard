# The dashboard

A private Streamlit app reading the CSVs in this repo. The home page mirrors
the weekly brief's three sections, in the same order, from the same module
(`scripts/brief_data.py`), so the page and the email cannot quote different
numbers for the same week.

Pages: home, Credit, Prices, Claims.

## Running it locally

```
pip install -r requirements.txt
streamlit run dashboard/app.py
```

It opens on http://localhost:8501 and reads the CSVs directly. No database,
no keys, nothing to configure.

## Deploying to Streamlit Community Cloud

The repo is private, so the app must be private too. Community Cloud
supports this on the free tier, and a private app is viewable only by
Google accounts you invite.

1. Go to https://share.streamlit.io and sign in **with GitHub**, using the
   account that owns this repo. Signing in with Google instead will not
   show the repository.

2. Authorise Streamlit for private repositories. On first sign-in GitHub
   shows an OAuth consent screen; it must include private repo access, or
   this repo will not appear in the next step. If it was already authorised
   without that scope, go to
   https://github.com/settings/applications, open Streamlit, and grant
   access to the repository.

3. Click **Create app**, then **Deploy a public app from GitHub** (the
   wording says public, but it refers to where the code lives, not who can
   see the app).

4. Fill in:

   - Repository: `acasale11/ai-infra-scorecard`
   - Branch: `main`
   - Main file path: `dashboard/app.py`

5. Open **Advanced settings** and set Python version to 3.12. Leave the
   secrets box empty; the dashboard reads no keys.

6. Click **Deploy**. The first build installs `requirements.txt` and takes
   a few minutes.

7. **Make it private.** This is the step that matters and it is not the
   default. In the app's menu choose **Settings**, then **Sharing**, and
   set who can view the app to invited viewers only. Add your own Google
   account as a viewer so you can open it when signed in with Google rather
   than GitHub.

8. Copy the app URL, something like
   `https://ai-infra-scorecard.streamlit.app`, and put it in
   `config/dashboard.json`:

   ```json
   { "url": "https://your-app.streamlit.app" }
   ```

   Commit that. Every weekly brief then links to the dashboard at the
   bottom. Until it is set, the brief says the dashboard is not deployed
   rather than printing a dead link.

## What to expect afterwards

The app redeploys automatically on each push to `main`, which includes the
automated Monday commits, so the dashboard is current without anything
further.

Community Cloud sleeps an app that nobody opens for about a week. Opening
it wakes it in under a minute. That is normal and costs nothing.

## Things worth knowing

**The dashboard is read-only.** It does not collect, write or score
anything. Everything it shows was written by a collector and committed.

**It interprets nothing**, for the same reason the brief does not. It shows
levels, moves, states and dates. What they mean is yours to write.

**The signal colours describe the evidence, not the thesis.** Green means a
pillar is collecting and current. Red means this project is not measuring
that pillar yet, which is a fact about the project rather than about AI
infrastructure. The rules are in `config/pillar_signals.json`.

**`requirements.txt` at the repo root exists for Streamlit Cloud**, which
looks there by default. The collectors themselves need nothing outside the
standard library, and that is deliberate. Only the dashboard needs
`streamlit` and `pandas`.
