#single button quiz
import RPi.GPIO as GPIO
import time
import socket
import json
import sounddevice as sd
import numpy as np
import wave
import logging
import queue
import speech_recognition as sr  # For transcribing the audio

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Use BCM pin numbering
GPIO.setmode(GPIO.BCM)

# Define the GPIO pin for the button
button_pin = 17  # GPIO 17

# Set up the button pin as an input
GPIO.setup(button_pin, GPIO.IN)

# Server connection setup
SERVER_IP = '192.168.1.100'  # Change to your server IP
SERVER_PORT = 12345  # Change to your server port

# File to log quiz interaction
LOG_FILE = "quiz_log.txt"

# Audio recording settings
latest_recording = None
is_recording = False
recording_in_progress = False
upload_queue = queue.Queue()

# Function to connect to the server
def connect_to_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, SERVER_PORT))
    return sock

# Function to send a message to the server
def send_message(sock, message):
    sock.sendall(message.encode())
    response = sock.recv(1024).decode()  # Receive response from server
    return response

# Function to record audio dynamically based on button press
def record_audio():
    global is_recording, recording_in_progress, latest_recording
    sample_rate = 44100
    channels = 1
    dtype = np.int16
    frames_per_buffer = 1024  # Define frames per buffer

    frames = []
    start_time = time.time()

    # Record while button is pressed
    while GPIO.input(button_pin) == GPIO.LOW:
        if not is_recording:
            is_recording = True
            recording_in_progress = True
            logging.info("Recording started...")

        # Record audio into buffer
        data = sd.rec(frames_per_buffer, samplerate=sample_rate, channels=channels, dtype=dtype)
        sd.wait()
        frames.append(data)

    if is_recording:
        is_recording = False
        recording_in_progress = False
        logging.info("Recording stopped.")

        # Save the recording
        file_path = f'output_{int(start_time)}.wav'
        save_wave_file(file_path, np.vstack(frames), sample_rate)
        latest_recording = file_path

    return latest_recording

# Helper function to save .wav files
def save_wave_file(file_path, audio_data, sample_rate):
    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())

# Function to transcribe audio to text
def audio_to_text(audio_file):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio = recognizer.record(source)  # Load the audio file
        try:
            text = recognizer.recognize_google(audio).lower()  # Transcribe using Google Speech Recognition
            logging.info(f"Transcription result: {text}")
            return text
        except sr.UnknownValueError:
            logging.error("Audio transcription failed: Could not understand audio.")
            return None
        except sr.RequestError as e:
            logging.error(f"Audio transcription failed: {e}")
            return None

# Main function for the quiz interaction
def quiz_interaction():
    sock = connect_to_server()
    single_press_threshold = 0.3  # Seconds
    long_press_threshold = 1.0  # Seconds

    try:
        with open(LOG_FILE, "a") as log_file:
            quiz_id = send_message(sock, "quiz")
            log_file.write(f"Received quiz ID: {quiz_id}\n")

            while True:
                # Get the question from the server
                question_response = send_message(sock, quiz_id)
                question_data = json.loads(question_response)
                question_id = question_data["questionId"]
                question_text = question_data["questionText"]
                log_file.write(f"Received question: {question_text}\n")

                print(f"Question: {question_text}")

                # Wait for button interaction
                button_pressed_time = None

                while True:
                    if GPIO.input(button_pin) == GPIO.HIGH:
                        if button_pressed_time is None:
                            button_pressed_time = time.time()
                    else:
                        if button_pressed_time is not None:
                            press_duration = time.time() - button_pressed_time

                            if press_duration >= long_press_threshold:
                                # Long press: Record and send answer
                                logging.info("Starting audio recording...")
                                audio_file = record_audio()
                                if audio_file:
                                    answer_text = audio_to_text(audio_file)

                                    if answer_text:
                                        payload = {
                                            "answer": {
                                                "questionId": question_id,
                                                "textAnswer": answer_text
                                            }
                                        }
                                        payload_str = json.dumps(payload)

                                        sock.sendall(payload_str.encode())
                                        response_code = int(sock.recv(1024).decode())  # Expecting HTTP-like status code

                                        # Log the response
                                        if response_code == 201:
                                            log_file.write("Answer submitted successfully!\n")
                                        elif response_code == 500:
                                            log_file.write("Server error occurred. Try again.\n")
                                        else:
                                            log_file.write(f"Unexpected response code: {response_code}\n")

                                break

                            elif press_duration >= single_press_threshold:
                                # Single press: Move to the next question
                                print("Moving to the next question.")
                                break

                            button_pressed_time = None

    finally:
        sock.close()

try:
    # Start the quiz interaction
    quiz_interaction()

except KeyboardInterrupt:
    with open(LOG_FILE, "a") as log_file:
        log_file.write("Program interrupted by user.\n")

finally:
    # Clean up GPIO on exit
    GPIO.cleanup()