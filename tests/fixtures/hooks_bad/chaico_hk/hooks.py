app_name = "chaico_hk"
doc_events = {"Sales Invoice": {"on_submit": "chaico_hk.events.record"}}
leaderboards = "chaico_hk.leaderboard.get_leaderboards"  # no longer read in v16