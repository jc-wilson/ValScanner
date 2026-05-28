def normalize_puuid(value):
    return str(value or "").strip()


def extract_live_match_participants(player_info):
    if not isinstance(player_info, dict):
        return []

    participants = []
    seen = set()
    for player in player_info.get("Players") or []:
        if not isinstance(player, dict):
            continue
        puuid = normalize_puuid(player.get("Subject"))
        if not puuid or puuid in seen:
            continue
        participants.append(puuid)
        seen.add(puuid)
    return participants


def get_user_history(co_play_history, self_puuid):
    if not isinstance(co_play_history, dict):
        co_play_history = {}

    by_user = co_play_history.setdefault("by_user", {})
    user_puuid = normalize_puuid(self_puuid)
    if not user_puuid:
        return None

    user_history = by_user.setdefault(user_puuid, {})
    if not isinstance(user_history.get("matches"), dict):
        user_history["matches"] = {}
    if not isinstance(user_history.get("counts"), dict):
        user_history["counts"] = {}
    return user_history


def get_all_account_counts(co_play_history):
    if not isinstance(co_play_history, dict):
        return {}

    by_user = co_play_history.get("by_user")
    if not isinstance(by_user, dict):
        return {}

    totals = {}
    for user_history in by_user.values():
        if not isinstance(user_history, dict):
            continue
        counts = user_history.get("counts")
        if not isinstance(counts, dict):
            continue
        for raw_puuid, raw_count in counts.items():
            puuid = normalize_puuid(raw_puuid)
            if not puuid:
                continue
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                continue
            if count > 0:
                totals[puuid] = totals.get(puuid, 0) + count
    return totals


def annotate_frontend_data_with_co_play_counts(frontend_data, co_play_history, self_puuid):
    counts = get_all_account_counts(co_play_history)
    players = frontend_data.values() if isinstance(frontend_data, dict) else frontend_data or []

    for player in players:
        if not isinstance(player, dict):
            continue
        player["co_play_count"] = int(counts.get(normalize_puuid(player.get("puuid")), 0) or 0)


def record_live_match_co_play(co_play_history, self_puuid, match_id, participants):
    user_history = get_user_history(co_play_history, self_puuid)
    normalized_match_id = str(match_id or "").strip()
    if not user_history or not normalized_match_id:
        return False

    unique_participants = []
    seen = set()
    for participant in participants or []:
        puuid = normalize_puuid(participant)
        if not puuid or puuid in seen:
            continue
        unique_participants.append(puuid)
        seen.add(puuid)

    if len(unique_participants) != 10:
        return False
    if normalized_match_id in user_history["matches"]:
        return False

    user_history["matches"][normalized_match_id] = unique_participants
    self_key = normalize_puuid(self_puuid)
    for puuid in unique_participants:
        if puuid == self_key:
            continue
        user_history["counts"][puuid] = int(user_history["counts"].get(puuid, 0) or 0) + 1
    return True


def apply_live_match_co_play_history(frontend_data, co_play_history, self_puuid, match_id, player_info):
    participants = extract_live_match_participants(player_info)
    if len(participants) != 10:
        return False

    annotate_frontend_data_with_co_play_counts(frontend_data, co_play_history, self_puuid)
    return record_live_match_co_play(co_play_history, self_puuid, match_id, participants)
