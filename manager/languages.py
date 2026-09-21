from enum import Enum


class TargetLanguage(str, Enum):
    # Latin Script - Germanic
    english = "english"
    german = "german"
    dutch = "dutch"
    swedish = "swedish"
    danish = "danish"
    norwegian = "norwegian"

    # Latin Script - Romance
    spanish = "spanish"
    portuguese = "portuguese"
    french = "french"
    italian = "italian"
    romanian = "romanian"

    # Latin Script - Slavic
    polish = "polish"
    czech = "czech"
    slovak = "slovak"
    croatian = "croatian"

    # Latin Script - Other
    finnish = "finnish"
    hungarian = "hungarian"
    turkish = "turkish"
    indonesian = "indonesian"
    swahili = "swahili"
    vietnamese = "vietnamese"

    # Cyrillic Script
    russian = "russian"
    ukrainian = "ukrainian"
    bulgarian = "bulgarian"
    serbian = "serbian"
