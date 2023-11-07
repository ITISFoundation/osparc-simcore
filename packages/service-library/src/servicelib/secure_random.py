import secrets


def secure_randint(start: int, end: int) -> int:
    """Generate a random integer between start (inclusive) and end (exclusive)."""
    if not isinstance(start, int) or not isinstance(end, int):
        msg = f"{start=} and {end=} must be integers"
        raise TypeError(msg)
    if start >= end:
        msg = f"{start=} must be less than {end=}"
        raise ValueError(msg)

    # Calculate the range of possible values
    num_values = end - start

    # Determine the number of bits required to represent num_values
    num_bits = num_values.bit_length()

    # Generate random bits until a value within the range is obtained
    while True:
        random_bits = int.from_bytes(
            secrets.token_bytes((num_bits + 7) // 8), byteorder="big"
        )
        random_value = random_bits % num_values
        if random_value < num_values:
            return start + random_value
