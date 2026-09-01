# CIAC Live Calendar — Trumbull Boys Soccer Freshman

This project turns the CIAC/FPSports team schedule into a subscribable `.ics`
calendar and refreshes it every 4 hours using GitHub Actions.

CIAC source:
https://ciac.fpsports.org/DashboardTeamSchedule.aspx?SportGenderListID=7&Status=0&SchoolID=159&TeamLevelID=1

## One-time setup

1. Create a new **public** GitHub repository.
2. Upload all files/folders from this project to the repository, preserving
   `.github/workflows/update-calendar.yml`.
3. Open the repository's **Settings → Pages**.
4. Under **Build and deployment**, choose **GitHub Actions**.
5. Open the **Actions** tab, select **Update CIAC calendar**, and click
   **Run workflow** once.
6. When it finishes, GitHub Pages will publish the `docs` folder.

Your feed URL will normally be:

`https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY-NAME/calendar.ics`

## Google Calendar

On calendar.google.com:
**Other calendars → + → From URL**, paste the `.ics` URL, then choose
**Add calendar**.

Google controls how often subscribed calendars refresh; the GitHub copy itself
is rebuilt every 4 hours.

## Notes

- Events use America/New_York.
- Each soccer game is given a 2-hour duration.
- Location and transportation information from CIAC are included.
- If CIAC changes its HTML structure, the workflow may need a parser update.
