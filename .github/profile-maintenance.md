# Profile maintenance

Keep this file named `profile-maintenance.md`: GitHub gives `.github/README.md`
priority over the root README, including on the public profile.

`Latest articles` fetches <https://jc.id.lv/feed.xml> daily at 06:23 UTC and
can also be started with **Actions → Latest articles → Run workflow** after
the workflow is merged into `main`.

The updater uses Python's standard library, keeps the five latest unique posts
ordered by publication date, and changes only the `BLOG-POST-LIST` block.
It commits only when the list changes. A network error, malformed or empty feed,
or invalid README markers fails the run and leaves the existing list intact.
Pull requests run the offline tests with read-only permissions; only scheduled
and manual runs on `main` can push an update. No personal access token is needed.

Local commands:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/update_articles.py --dry-run
python3 scripts/update_articles.py
```

GitHub may delay scheduled runs and disables schedules in public repositories
after 60 days without repository activity. If that happens, re-enable the
workflow in Actions. See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
