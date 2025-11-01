import time
import hashlib
import os
from audio.speech_recognition import transcribe_audio
from backend.ai_engine import generate_reply, JarvinConfig
from memory.conversation import get_conversation_history, set_conversation_history, get_user_profile, set_user_profile, clear_conversation

# Jarvin system prompt
JARVIN_SYSTEM_PROMPT = """
You are Jarvin, a friendly and helpful AI assistant. 
Your tone should be warm, encouraging, and positive.
Always be supportive and provide useful guidance.
Keep responses concise but helpful.
"""

# Global variables for preventing duplicates
last_processed_audio = None
is_processing = False
last_processing_time = 0
last_successful_response = None  # Store the last successful response

def get_audio_hash(audio_path):
    """Generate a simple hash to detect duplicate audio processing"""
    if not audio_path or not os.path.exists(audio_path):
        return None
    # Use file size and modification time for more reliable hashing
    try:
        stat = os.stat(audio_path)
        return hashlib.md5(f"{audio_path}_{stat.st_size}_{stat.st_mtime}".encode()).hexdigest()[:16]
    except:
        return hashlib.md5(f"{audio_path}_{time.time()}".encode()).hexdigest()[:16]

def process_audio(audio_path: str, user_context: dict, use_conversation_memory: bool, response_style: str):
    global last_processed_audio, is_processing, last_processing_time, last_successful_response
    
    conversation_history = get_conversation_history()
    
    # Check if audio path is valid
    if not audio_path or not os.path.exists(audio_path):
        return "No audio input detected.", "No reply generated.", conversation_history

    # Prevent duplicate processing with multiple safeguards
    current_audio_hash = get_audio_hash(audio_path)
    
    # Safeguard 1: Check if we're already processing
    if is_processing:
        # If we're already processing, just return the current state
        if conversation_history:
            last_user_msg = conversation_history[-1][1] if conversation_history[-1][0] == "user" else "Processing..."
            last_jarvin_msg = conversation_history[-1][1] if conversation_history[-1][0] == "assistant" else "Processing..."
            return last_user_msg, last_jarvin_msg, conversation_history
        return "Processing...", "Please wait...", conversation_history
    
    # Safeguard 2: Check if this is the same audio file
    if current_audio_hash == last_processed_audio and last_successful_response:
        # Return the last successful response instead of error messages
        last_text, last_reply = last_successful_response
        return last_text, last_reply, conversation_history
    
    # Safeguard 3: Rate limiting - don't process if we just processed something
    current_time = time.time()
    if current_time - last_processing_time < 2.0 and last_successful_response:  # 2 second cooldown
        # Return last successful response during cooldown
        last_text, last_reply = last_successful_response
        return last_text, last_reply, conversation_history

    # Set processing flag
    is_processing = True
    last_processed_audio = current_audio_hash
    last_processing_time = current_time

    try:
        # Start timing for performance monitoring
        start_time = time.time()
        
        # Transcribe audio
        text = transcribe_audio(audio_path).strip()
        if not text:
            return "(empty transcription)", "No reply generated.", conversation_history
        
        # Check if this is a duplicate of the last user message (content-based)
        if (conversation_history and 
            conversation_history[-1][0] == "user" and 
            conversation_history[-1][1] == text and
            len(conversation_history) > 1):  # Make sure we have at least one assistant response
            # Return the previous assistant response
            prev_assistant_msg = conversation_history[-2][1] if conversation_history[-2][0] == "assistant" else "I already responded to that!"
            return text, prev_assistant_msg, conversation_history
        
        transcription_time = time.time()
        print(f"Transcription time: {transcription_time - start_time:.2f}s")

        cfg_ai = JarvinConfig()
        
        # Build context
        context_text = ""
        if user_context:
            context_text = (
                f"User Name: {user_context.get('name', 'Unknown')}\n"
                f"Goal: {user_context.get('goal', 'None')}\n"
                f"Mood: {user_context.get('mood', 'Neutral')}\n\n"
            )
        
        # Add response style to prompt
        style_prompt = ""
        if response_style == "concise":
            style_prompt = "Keep your response very brief and to the point."
        elif response_style == "detailed":
            style_prompt = "Provide a more detailed and comprehensive response."
        elif response_style == "encouraging":
            style_prompt = "Be extra encouraging and motivational in your response."

        # Build conversation context
        conversation_context = ""
        if use_conversation_memory and conversation_history:
            # Include last 3 exchanges for context
            recent_history = conversation_history[-6:]  # Last 3 back-and-forths
            conversation_context = "Recent conversation:\n"
            for role, message in recent_history:
                conversation_context += f"{role}: {message}\n"
            conversation_context += "\n"

        # Build final prompt
        prompt = f"""{JARVIN_SYSTEM_PROMPT}
{style_prompt}

{context_text}
{conversation_context}
Current user message: {text}

Please respond helpfully:"""
        
        llm_start_time = time.time()
        reply = generate_reply(prompt, cfg=cfg_ai)
        llm_time = time.time()
        print(f"LLM response time: {llm_time - llm_start_time:.2f}s")
        
        # Update conversation history
        conversation_history.append(("user", text))
        conversation_history.append(("assistant", reply))
        set_conversation_history(conversation_history)
        
        # Store the successful response for future duplicates
        last_successful_response = (text, reply)
        
        total_time = time.time() - start_time
        print(f"Total processing time: {total_time:.2f}s")
        
        return text, reply, conversation_history
        
    except Exception as e:
        print(f"Error processing audio: {e}")
        return f"Error: {str(e)}", "Sorry, there was an error processing your request.", conversation_history
    finally:
        # Always reset processing flag
        is_processing = False

def save_user_profile(name, goal, mood, communication_style, response_length):
    """Save user profile to memory"""
    profile = {
        "name": name,
        "goal": goal, 
        "mood": mood,
        "communication_style": communication_style,
        "response_length": response_length
    }
    set_user_profile(profile)
    return profile

def clear_conversation_history():
    """Clear the conversation history"""
    global last_successful_response, last_processed_audio
    clear_conversation()
    last_successful_response = None
    last_processed_audio = None
    return get_conversation_history()

def update_history_display(history):
    """Format conversation history for display"""
    if not history:
        return "No conversation history yet."
    
    formatted = ""
    for i, (role, message) in enumerate(history, 1):
        speaker = "You" if role == "user" else "Jarvin"
        formatted += f"{i}. {speaker}: {message}\n\n"
    return formatted

def get_save_confirmation():
    """Get confirmation message for saved profile"""
    profile = get_user_profile()
    return f"✅ Profile saved! Jarvin will remember: {profile.get('name', 'Unknown')} - {profile.get('goal', 'No goal set')}"