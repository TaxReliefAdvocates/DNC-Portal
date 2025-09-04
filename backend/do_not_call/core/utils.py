def normalize_phone_to_e164_digits(value: str) -> str:
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    return digits if len(digits) == 10 else ''


