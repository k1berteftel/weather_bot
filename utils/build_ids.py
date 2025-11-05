import random
import string


def get_random_id() -> str:
    string.ascii_letter = 'abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    simvols = ''
    for i in range(0, 8):
        simvols += str(random.choice(string.ascii_letters))
    return simvols