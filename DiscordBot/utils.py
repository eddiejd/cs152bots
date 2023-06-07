from unidecode import unidecode

OBFUSCATION_MAP = {
    'a': ['ª', '∀', '⟑', 'α', '@'],
    'b': ['฿', 'В', 'ь', 'β'],
    'c': ['©', '∁', '⊂', '☪', '¢'],
    'd': ['∂', '⫒', 'ძ'],
    'e': ['ℇ', '℮', '∃', '∈', '∑', '⋿', '€', 'ϱ'],
    'f': ['⨍', '⨗', '⫭', '៛', 'ϝ', '𐅿'],
    'g': ['₲', 'ց', 'Ԍ'],
    'h': ['ℏ', '⫲', '⫳', '₶'],
    'i': ['ℹ︎', '⫯', 'ι', 'ї'],
    'j': ['⌡', 'ϳ', 'ј'],
    'k': ['₭', 'κ', 'Ϗ'],
    'l': ['∟', '₤', 'լ'],
    'm': ['≞', '⋔', '⨇', '⩋', '⫙', '₥'],
    'n': ['∏', '∩', 'η'],
    'o': ['º', '⦿', '☉', 'ο', 'օ'],
    'p': ['℗', '♇', '₱', 'ρ', 'բ'],
    'q': ['ԛ', 'զ', 'գ', '৭', 'ҩ'],
    'r': ['®', 'Я', 'Ւ', '𐅾'],
    's': ['∫', '$', 'ѕ'],
    't': ['⊺', '⟙', '✝', '♱', '♰', 'τ', 'է'],
    'u': ['µ', '∪', '∐', '⨃'],
    'v': ['∨', '√', '⩔'],
    'w': ['⨈', '⩊', '⫝', '₩', 'ω'],
    'x': ['×', '⨯', '☓', '✗'],
    'y': ['¥', '⑂', 'Ⴤ', 'ӱ'],
    'z': ['Ꙁ', 'Ⴠ', 'Հ'],
}

def our_decode(msg):
    constructed_msg = ""
    obfuscated_dict = {}

    for key, values in OBFUSCATION_MAP.items():
        for value in values:
            obfuscated_dict[value] = key
    for character in msg:
        if character in obfuscated_dict:
            constructed_msg += obfuscated_dict[character]
        else:
            constructed_msg += character
    return constructed_msg
        


def clean_message(msg):
    lowered = msg.lower()
    our_decoded = our_decode(lowered)#.encode()
    unidecoded  = unidecode(our_decoded)
    return unidecoded