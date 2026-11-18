"""Tolerant matching of spoken Polish phrases to stored names and addresses.

Spoken input differs from stored data in case, diacritics and inflection
("do Roberta", "na Żołnierską 47 w Szczecinie"). These helpers let the application
resolve such phrases itself, so the LLM only has to pass on what the user said.
"""

import re
import unicodedata


def tokens(text: str) -> list[str]:
    """Lower-case ASCII words and numbers: 'Żołnierską 47' -> ['zolnierska', '47']."""
    text = unicodedata.normalize("NFKD", text.casefold().replace("ł", "l"))
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.findall(r"[a-z]+|[0-9]+[a-z]*", text)


def word_matches(term: str, word: str) -> bool:
    if term[0].isdigit():
        return term == word                      # numbers only as a whole (47 ≠ 147)
    if term in word:
        return True                              # typed fragment, e.g. "niers"
    # Polish inflection changes the ending: "roberta", "anny", "jana", "szczecinie",
    # "zolnierskiej" match the base form if the stem agrees and the ending is short.
    if len(word) < 3:
        return False
    stem = max(3, len(word) - (2 if len(word) >= 5 else 1))
    return len(term) >= stem and term[:stem] == word[:stem] and len(term) - len(word) <= 4


def all_terms_match(terms: list[str], words: list[str]) -> bool:
    return bool(terms) and all(any(word_matches(term, word) for word in words) for term in terms)
