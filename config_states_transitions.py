# config_states_transitions.py

from constants import TIMEOUTS

#########################################################################
# 1. Define States, including timeouts and on_timeout transitions.
#########################################################################

# Available STATES = IDLE, HANDSHAKE_INITIATED, TR_REQ_ON, TRANSFER_READY, BUSY, CARRIER_DETECTED, TRANSFER_COMPLETED
# Unavailable STATES = IDLE_UNAVBL, HO_UNAVBL, ERROR_HANDLING, ERROR_RECOVERY, TIMEOUT

STATES = [
    # Available states
    {'name': 'IDLE', 'on_enter': '_on_enter_idle'},
    {
        'name': 'HANDSHAKE_INITIATED',
        'tags': ['handshake'],
        'timeout': TIMEOUTS.TP1.value,
        'on_timeout': '_handle_timeout',
        'on_enter': '_on_enter_handshake_initiated',
    },
    {
        'name': 'TR_REQ_ON',
        'tags': ['handshake'],
        'on_enter': '_on_enter_tr_req',
    },
    {
        'name': 'TRANSFER_READY',
        'tags': ['handshake', 'active'],
        'timeout': TIMEOUTS.TP2.value,
        'on_timeout': '_handle_timeout',
        'on_enter': '_on_enter_transfer_ready',
    },
    {
        'name': 'BUSY',
        'tags': ['handshake', 'handoff', 'active'],
        'timeout': TIMEOUTS.TP3.value,
        'on_timeout': '_handle_timeout',
        'on_enter': '_on_enter_busy',
    },
    {
        'name': 'CARRIER_DETECTED',
        'tags': ['handshake', 'handoff', 'active'],
        'timeout': TIMEOUTS.TP4.value,
        'on_timeout': '_handle_timeout',
        'on_enter': '_on_enter_carrier_detected',
    },
    {
        'name': 'TRANSFER_COMPLETED',
        'tags': ['handshake'],
        'timeout': TIMEOUTS.TP5.value,
        'on_timeout': '_handle_timeout',
        'on_enter': '_on_enter_transfer_complete',
    },
    # Unavailable states
    {
        'name': 'IDLE_UNAVBL',
        'tags': ['unavbl'],
        'on_enter': '_on_enter_idle_unavbl',
    },
    {
        'name': 'HO_UNAVBL',
        'tags': ['unavbl', 'ho_off'],
        'on_enter': '_on_enter_ho_unavbl',
    },
    {
        'name': 'ERROR_HANDLING',
        'tags': ['active_error'],
        'on_enter': '_on_enter_error_handling',
    },
    {
        'name': 'ERROR_RECOVERY',
        'tags': ['active_error'],
        'on_enter': '_on_enter_error_recovery',
    },
    {'name': 'RESET', 'tags': ['for_sim'], 'on_enter': '_on_enter_reset'},
    {
        'name': 'TIMEOUT',
        'tags': ['active_error'],
        'on_enter': '_on_enter_timeout',
    },
]

########################################################################
# 2. Define Transitions with optional conditions, before, and after callbacks.
#
#    - 'conditions': list of methods returning True/False.
#    - 'before': called immediately before the transition (if conditions pass).
#    - 'after': called immediately after the transition (if conditions pass).
#########################################################################

TRANSITIONS = [
    # IDLE -> HANDSHAKE_INITIATED
    {
        'trigger': 'start_handshake',
        'source': 'IDLE',
        'dest': 'HANDSHAKE_INITIATED',
        'conditions': ['can_start_handshake'],
    },
    # HANDSHAKE_INITIATED -> TR_REQ_ON
    {
        'trigger': 'tr_req_received',
        'source': 'HANDSHAKE_INITIATED',
        'dest': 'TR_REQ_ON',
        'conditions': ['validate_tr_req'],
    },
    # TR_REQ_ON -> TRANSFER_READY
    {
        'trigger': 'ready_for_transfer',
        'source': 'TR_REQ_ON',
        'dest': 'TRANSFER_READY',
        'conditions': ['validate_ready'],
    },
    # TRANSFER_READY -> BUSY
    {
        'trigger': 'busy_on',
        'source': 'TRANSFER_READY',
        'dest': 'BUSY',
        'conditions': ['validate_busy_conditions'],
    },
    # BUSY -> CARRIER_DETECTED
    {
        'trigger': 'carrier_detected_event',
        'source': 'BUSY',
        'dest': 'CARRIER_DETECTED',
        'conditions': ['validate_carrier_detected'],
    },
    # CARRIER_DETECTED -> TRANSFER_COMPLETED
    {
        'trigger': 'transfer_done',
        'source': 'CARRIER_DETECTED',
        'dest': 'TRANSFER_COMPLETED',
        'conditions': ['transfer_complete'],
    },
    # TRANSFER_COMPLETED -> IDLE
    {
        'trigger': 'transfer_completed',
        'source': 'TRANSFER_COMPLETED',
        'dest': 'IDLE',
        'conditions': ['validate_valid_off'],
    },
    # TRANSFER_COMPLETED -> IDLE
    {
        'trigger': 'return_idle',
        'source': ['TRANSFER_COMPLETED'],
        'dest': 'IDLE',
        'conditions': 'can_return_to_idle',
    },
    # ----------------------------------------------------------------
    # UNAVAILABLE TRANSITIONS
    # ----------------------------------------------------------------
    # IDLE, HO_UNAVBL -> IDLE_UNAVBL
    {
        'trigger': 'to_IDLE_UNAVBL',
        'source': ['IDLE', 'HO_UNAVBL', 'ERROR_HANDLING'],
        'dest': 'IDLE_UNAVBL',
        'conditions': 'should_transition_idle_unavbl',
    },
    # ANY STATE -> HO_UNAVBL
    {
        'trigger': 'to_HO_UNAVBL',
        'source': '*',
        'dest': 'HO_UNAVBL',
    },
    # HO_UNAVBL -> IDLE
    {
        'trigger': 'ho_avbl_return_idle',
        'source': 'HO_UNAVBL',
        'dest': 'IDLE',
        'conditions': 'can_auto_recover',
    },
    # IDLE_UNAVBL -> IDLE
    {
        'trigger': 'idle_unavbl_return_idle',
        'source': 'IDLE_UNAVBL',
        'dest': 'IDLE',
        'conditions': 'can_return_to_idle',
    },
    # ANY STATE -> ERROR_HANDLING (analyze error, decide on recovery method)
    {
        'trigger': 'to_ERROR_HANDLING',
        'source': '*',
        'dest': 'ERROR_HANDLING',
        'before': 'before_error_handling',
    },
    # ERROR_HANDLING -> IDLE (auto-recovered)
    {
        'trigger': 'attempt_recovery',
        'source': 'ERROR_HANDLING',
        'dest': 'IDLE',
        'conditions': 'can_auto_recover',
    },
    # ERROR_HANDLING -> ERROR_RECOVERY (manual recover required)
    {
        'trigger': 'to_ERROR_RECOVERY',
        'source': 'ERROR_HANDLING',
        'dest': 'ERROR_RECOVERY',
    },
    {
        'trigger': 'to_TIMEOUT',
        'source': [
            'HANDSHAKE_INITIATED',
            'TRANSFER_READY',
            'BUSY',
            'CARRIER_DETECTED',
            'TRANSFER_COMPLETED',
        ],
        'dest': 'ERROR_RECOVERY',
    },
    {
        'trigger': 'reset',
        'source': '*',
        'dest': 'IDLE',
    },
]
