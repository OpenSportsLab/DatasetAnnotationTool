def ms_to_time(ms):
    seconds = ms // 1000
    return f"{seconds // 60:02}:{seconds % 60:02}"
