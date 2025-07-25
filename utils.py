# ---------------------------------------------------------------------------
# Board-pin → TCA9535 bit conversion
#   • Board headers label pin-1 at the *top* (DI07 / DO17) and count downward
#   • Driver wants “bit-within-port” 0-7 where 7 is MSB, 0 is LSB
#
# Therefore:  bit = 8 - board_pin
#              pin 1 → 7   pin 2 → 6 … pin 8 → 0
# ---------------------------------------------------------------------------
def pinmap_board_to_bits(board_pin_map: dict[str, int]) -> dict[str, int]:
    """
    Convert a {signal: board_pin} mapping to {signal: bit_number}.

    Parameters
    ----------
    board_pin_map : dict
        Keys are signal names, values are *board pin numbers* (1-8).

    Returns
    -------
    dict
        New dictionary with the same keys but values translated to 0-7
        bit numbers suitable for Contec's DioInpBit / DioOutBit calls.

    Raises
    ------
    ValueError
        If any pin is outside the valid 1-8 range.
    """
    bit_map: dict[str, int] = {}
    for sig, pin in board_pin_map.items():
        if not 1 <= pin <= 8:
            raise ValueError(f'{sig}: board pin {pin} out of range (must be 1-8).')
        bit_map[sig] = 8 - pin  # invert numbering
    return bit_map
