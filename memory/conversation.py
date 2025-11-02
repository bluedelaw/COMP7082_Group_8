# memory/conversation.py
# Global memory management
conversation_history = []
user_profile = {}
last_processed_audio = None

def get_conversation_history():
    return conversation_history

def set_conversation_history(history):
    global conversation_history
    conversation_history = history

def get_user_profile():
    return user_profile

def set_user_profile(profile):
    global user_profile
    user_profile.update(profile)

def clear_conversation():
    global conversation_history, last_processed_audio
    conversation_history = []
    last_processed_audio = None
