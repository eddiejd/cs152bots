from unidecode import unidecode

def clean_message(msg):
    lowered = msg.lower()
    unidecoded  = unidecode(lowered)
    return unidecoded