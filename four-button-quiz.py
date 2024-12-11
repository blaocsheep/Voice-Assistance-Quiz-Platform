#four button quiz
import RPi.GPIO as GPIO
import time
import socket
import json

# Use BCM pin numbering
GPIO.setmode(GPIO.BCM)

# Define the GPIO pins for the buttons
button1_pin = 17  # GPIO 17 (A)
button2_pin = 27  # GPIO 27 (B)
button3_pin = 22  # GPIO 22 (C)
button4_pin = 5   # GPIO 5  (D)

# Set up each button pin as an input
GPIO.setup(button1_pin, GPIO.IN)
GPIO.setup(button2_pin, GPIO.IN)
GPIO.setup(button3_pin, GPIO.IN)
GPIO.setup(button4_pin, GPIO.IN)

# Server connection setup
SERVER_IP = '192.168.1.100'  # Change to your server IP
SERVER_PORT = 12345  # Change to your server port

# File to log quiz interaction
LOG_FILE = "quiz_log.txt"

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

# Define what happens when each button is pressed
def button_callback(channel):
    global current_answer
    if channel == button1_pin:
        current_answer = 'A'
    elif channel == button2_pin:
        current_answer = 'B'
    elif channel == button3_pin:
        current_answer = 'C'
    elif channel == button4_pin:
        current_answer = 'D'

# Set up event detection on each button
GPIO.add_event_detect(button1_pin, GPIO.RISING, callback=button_callback, bouncetime=200)
GPIO.add_event_detect(button2_pin, GPIO.RISING, callback=button_callback, bouncetime=200)
GPIO.add_event_detect(button3_pin, GPIO.RISING, callback=button_callback, bouncetime=200)
GPIO.add_event_detect(button4_pin, GPIO.RISING, callback=button_callback, bouncetime=200)

# Main function for the quiz interaction
def quiz_interaction():
    global current_answer
    current_answer = None
    sock = connect_to_server()
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

                # Wait for a button press to get the answer
                while current_answer is None:
                    time.sleep(0.1)  # Short delay to avoid busy waiting

                # Construct the answer submission payload
                payload = {
                    "answer": {
                        "questionId": question_id,
                        "selectedOptionId": current_answer
                    }
                }
                payload_str = json.dumps(payload)

                # Send the answer to the server
                sock.sendall(payload_str.encode())
                response_code = int(sock.recv(1024).decode())  # Expecting HTTP-like status code

                # Log the response
                if response_code == 201:
                    log_file.write("Answer submitted successfully!\n")
                elif response_code == 500:
                    log_file.write("Server error occurred. Try again.\n")
                else:
                    log_file.write(f"Unexpected response code: {response_code}\n")

                # Reset the answer after processing
                current_answer = None

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
