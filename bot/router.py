from enum import Enum

class State(Enum):
    IDLE            = "idle"
    PRODUCT_INFO    = "product_info"
    PAYMENT         = "payment"
    DELIVERY        = "delivery"
    RATING_SCORE    = "rating_score"
    RATING_FEEDBACK = "rating_feedback"

_states: dict[int, State] = {}
_conv_ids: dict[int, str] = {}
_rating_scores: dict[int, int] = {}

def get_state(chat_id: int) -> State:
    return _states.get(chat_id, State.IDLE)

def set_state(chat_id: int, state: State):
    _states[chat_id] = state

def reset_state(chat_id: int):
    _states[chat_id] = State.IDLE

def get_conv_id(chat_id: int) -> str:
    return _conv_ids.get(chat_id)

def set_conv_id(chat_id: int, conv_id: str):
    _conv_ids[chat_id] = conv_id

def reset_conv_id(chat_id: int):
    _conv_ids.pop(chat_id, None)

def get_rating_score(chat_id: int) -> int:
    return _rating_scores.get(chat_id)

def set_rating_score(chat_id: int, score: int):
    _rating_scores[chat_id] = score

def reset_rating_score(chat_id: int):
    _rating_scores.pop(chat_id, None)