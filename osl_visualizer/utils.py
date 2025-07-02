def ms_to_time(ms):
    seconds = ms // 1000
    return f"{seconds // 60:02}:{seconds % 60:02}"


def ms_to_hms(ms):
    """Convert milliseconds to HH:MM:SS."""
    total_seconds = int(ms // 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def ms_to_hms_ms(ms):
    """Convert milliseconds to HH:MM:SS:ZZZ format."""
    ms = int(ms)
    total_seconds = ms // 1000
    milliseconds = ms % 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}:{milliseconds:03}"

def hms_ms_to_ms(hms_str):
    """Convert HH:MM:SS:ZZZ string to milliseconds."""
    try:
        parts = hms_str.strip().split(":")
        if len(parts) != 4:
            raise ValueError
        hours, minutes, seconds, ms = map(int, parts)
        total_ms = ((hours * 60 + minutes) * 60 + seconds) * 1000 + ms
        return total_ms
    except Exception:
        raise ValueError("Time must be in HH:MM:SS:ZZZ format.")
