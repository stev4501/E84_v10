from enum import Enum, auto


class LoadPortState(Enum):
    OUT_OF_SERVICE = auto()
    TRANSFER_READY = auto()
    TRANSFER_BLOCKED = auto()
    READY_TO_LOAD = auto()
    READY_TO_UNLOAD = auto()


# ────────────────────────────────────────────────────────────────────────────────
class E87LoadPort:
    """Finite-state representation of the SEMI E87 Load-Port Transfer State Model"""

    _ALLOWED = {
        # super-state change
        (LoadPortState.OUT_OF_SERVICE, LoadPortState.TRANSFER_READY),
        # core transitions
        (LoadPortState.TRANSFER_READY, LoadPortState.READY_TO_LOAD),
        (LoadPortState.TRANSFER_READY, LoadPortState.READY_TO_UNLOAD),
        (LoadPortState.READY_TO_LOAD, LoadPortState.TRANSFER_BLOCKED),
        (LoadPortState.READY_TO_UNLOAD, LoadPortState.TRANSFER_BLOCKED),
        (LoadPortState.TRANSFER_BLOCKED, LoadPortState.READY_TO_LOAD),
        (LoadPortState.TRANSFER_BLOCKED, LoadPortState.READY_TO_UNLOAD),
        (LoadPortState.TRANSFER_BLOCKED, LoadPortState.TRANSFER_READY),
    }

    def __init__(self) -> None:
        self.state: LoadPortState = LoadPortState.OUT_OF_SERVICE

    # ── service helpers ────────────────────────────────────────────────────────
    def can_transition(self, new_state: LoadPortState) -> bool:
        return (self.state, new_state) in self._ALLOWED

    def transition(self, new_state: LoadPortState) -> None:
        if not self.can_transition(new_state):
            raise ValueError(
                f'Illegal LPTS transition: {self.state.name} → {new_state.name}'
            )
        self.state = new_state

    # convenience wrappers
    def set_in_service(self):
        self.transition(LoadPortState.TRANSFER_READY)

    def request_load(self):
        self.transition(LoadPortState.READY_TO_LOAD)

    def request_unload(self):
        self.transition(LoadPortState.READY_TO_UNLOAD)

    def block_transfer(self):
        if self.state in (LoadPortState.READY_TO_LOAD, LoadPortState.READY_TO_UNLOAD):
            self.transition(LoadPortState.TRANSFER_BLOCKED)

    def unblock_after_load(self):
        self.transition(LoadPortState.TRANSFER_BLOCKED)  # clamp/unclamp ends
        # port now empty → ready for another load
        self.transition(LoadPortState.READY_TO_LOAD)

    # Add additional wrappers as your equipment’s workflow requires.
