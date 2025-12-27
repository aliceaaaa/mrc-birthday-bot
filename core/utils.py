import re
from calendar import monthrange

def normalize_date_or_none(s: str) -> str | None:
    if not isinstance(s, str):
        return None
      
    m = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\s*", s)
    
    if not m:
        return None
      
    d = int(m.group(1))
    mo = int(m.group(2))
    mo = max(1, min(12, mo))
    maxd = monthrange(2000, mo)[1]
    d = max(1, min(maxd, d))
    
    return f"{d:02d}.{mo:02d}"

def normalize_username_or_none(s: str | None) -> str | None:
    if not s:
        return None
      
    u = s.lstrip("@").strip()
    
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", u):
        return None
      
    return u.lower()
