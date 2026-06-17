from enum import Enum

class State(Enum):
    IDLE         = "idle"
    PRODUCT_INFO = "product_info"
    PAYMENT      = "payment"
    DELIVERY     = "delivery"

_states: dict[int, State] = {}

def get_state(chat_id: int) -> State:
    return _states.get(chat_id, State.IDLE)

def set_state(chat_id: int, state: State):
    _states[chat_id] = state

def reset_state(chat_id: int):
    _states[chat_id] = State.IDLE