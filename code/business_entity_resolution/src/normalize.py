import re
import unicodedata

def remove_accents(input_str: str) -> str:
    if not isinstance(input_str, str):
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

LEGAL_SUFFIXES = {
    'inc', 'incorporated', 'corp', 'corporation', 'llc', 'ltd', 'limited',
    'pvt', 'private', 'co', 'company', 'gmbh', 'sa', 'sas', 'sarl', 'dba',
    'pvtltd', 'privatelimited', 'sci', 'eurl', 'sprl', 'snc', 'ste', 'societe',
    'enterprises', 'enterprise', 'services', 'service', 'solutions', 'group',
    'industries', 'industry', 'international', 'holdings', 'holding', 'traders',
    'trading', 'agency', 'agencies', 'associates', 'consultants', 'consulting'
}

# Strict legal suffix set (only legal status words, not generic industry words)
STRICT_LEGAL_SUFFIXES = {
    'inc', 'incorporated', 'corp', 'corporation', 'llc', 'ltd', 'limited',
    'pvt', 'private', 'co', 'company', 'gmbh', 'sa', 'sas', 'sarl', 'dba',
    'pvtltd', 'privatelimited', 'sci', 'eurl', 'sprl', 'snc', 'ste', 'societe'
}

ADDR_MAP = {
    'street': 'st', 'saint': 'st', 'str': 'st',
    'road': 'rd',
    'avenue': 'ave', 'av': 'ave',
    'boulevard': 'blvd',
    'drive': 'dr',
    'lane': 'ln',
    'place': 'pl',
    'court': 'ct',
    'floor': 'fl', 'flr': 'fl',
    'apartment': 'apt', 'suite': 'ste', 'unit': 'unit', 'no': 'no', 'number': 'no',
    'highway': 'hwy', 'parkway': 'pkwy', 'square': 'sq',
    # Common US States
    'virginia': 'va', 'texas': 'tx', 'alabama': 'al', 'illinois': 'il', 'new york': 'ny',
    'north carolina': 'nc', 'california': 'ca', 'florida': 'fl', 'georgia': 'ga',
    'ohio': 'oh', 'pennsylvania': 'pa', 'michigan': 'mi', 'washington': 'wa',
    'massachusetts': 'ma', 'arizona': 'az', 'indiana': 'in', 'tennessee': 'tn',
    'missouri': 'mo', 'maryland': 'md', 'wisconsin': 'wi', 'minnesota': 'mn',
    'colorado': 'co', 'alabama': 'al', 'south carolina': 'sc', 'louisiana': 'la',
    'kentucky': 'ky', 'oregon': 'or', 'oklahoma': 'ok', 'connecticut': 'ct',
    'utah': 'ut', 'iowa': 'ia', 'nevada': 'nv', 'arkansas': 'ar', 'mississippi': 'ms',
    'kansas': 'ks', 'new mexico': 'nm', 'nebraska': 'ne', 'idaho': 'id',
    'hawaii': 'hi', 'new hampshire': 'nh', 'maine': 'me', 'rhode island': 'ri',
    'montana': 'mt', 'delaware': 'de', 'south dakota': 'sd', 'north dakota': 'nd',
    'alaska': 'ak', 'vermont': 'vt', 'wyoming': 'wy', 'district of columbia': 'dc',
    # Common Indian States
    'maharashtra': 'mh', 'haryana': 'hr', 'karnataka': 'ka', 'delhi': 'dl',
    'tamil nadu': 'tn', 'uttar pradesh': 'up', 'gujarat': 'gj', 'telangana': 'ts',
    'west bengal': 'wb', 'rajasthan': 'rj', 'kerala': 'kl', 'punjab': 'pb',
    'andhra pradesh': 'ap', 'madhya pradesh': 'mp', 'bihar': 'br', 'odisha': 'or'
}

def clean_name(name: str, strict_legal: bool = False) -> str:
    if not isinstance(name, str):
        return ""
    text = remove_accents(name.lower())
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    tokens = text.split()
    stopwords = STRICT_LEGAL_SUFFIXES if strict_legal else LEGAL_SUFFIXES
    filtered = [t for t in tokens if t not in stopwords]
    return " ".join(filtered) if filtered else text.strip()

def clean_address(addr: str) -> str:
    if not isinstance(addr, str):
        return ""
    text = remove_accents(addr.lower())
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    tokens = [ADDR_MAP.get(t, t) for t in text.split()]
    return " ".join(tokens)

def extract_street_num(addr: str) -> str:
    if not isinstance(addr, str):
        return ""
    match = re.search(r'\b\d+[a-z]?\b', addr)
    return match.group(0) if match else ""

def extract_zip(addr: str, country: str) -> str:
    if not isinstance(addr, str):
        return ""
    if country in ('US', 'France'):
        match = re.search(r'\b\d{5}\b', addr)
        return match.group(0) if match else ""
    elif country == 'India':
        match = re.search(r'\b\d{6}\b', addr)
        return match.group(0) if match else ""
    return ""

def get_name_tokens(name: str):
    cleaned = clean_name(name, strict_legal=True)
    return cleaned.split()

def get_token_sort_key(name: str) -> str:
    tokens = sorted(get_name_tokens(name))
    return " ".join(tokens)
 