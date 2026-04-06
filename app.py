from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import dialogflow
import os
from collections import Counter
import uuid
from datetime import datetime  

app = Flask(__name__)

app.secret_key = "secret123"   # required for session

#  safer credentials (fallback to your original values)
ADMIN_ID = os.getenv("ADMIN_ID", "admin@id")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin@pass")

# ---------------- FIREBASE SETUP ----------------
import json

firebase_json = json.loads(os.getenv("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_json)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------------- DIALOGFLOW SETUP ----------------
dialogflow_json = json.loads(os.getenv("DIALOGFLOW_KEY"))

with open("dialogflow_temp.json", "w") as f:
    json.dump(dialogflow_json, f)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "dialogflow_temp.json"

PROJECT_ID = "my-chatbot-rvye"   # 🔴 my dialogflow project ID

def detect_intent(text, session_id):
    try:
        session_client = dialogflow.SessionsClient()
        session = session_client.session_path(PROJECT_ID, session_id)

        text_input = dialogflow.TextInput(
            text=text,
            language_code="en"
        )

        query_input = dialogflow.QueryInput(text=text_input)

        response = session_client.detect_intent(
            request={"session": session, "query_input": query_input}
        )

        return response.query_result.fulfillment_text

    except Exception as e:
        print("Dialogflow ERROR:", e)
        return "Error connecting to AI"

# ---------------- ROUTES ----------------

# Home Page
@app.route('/')
def home():
    return render_template("index.html")

# Chat API
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message")

    #  handle empty input
    if not user_message:
        return jsonify({"reply": "Please enter a message"})

    session_id = str(uuid.uuid4())

    #  safe error handling
    try:
        bot_reply = detect_intent(user_message, session_id)
    except Exception as e:
        print("Chat ERROR:", e)
        bot_reply = "Something went wrong"

    # fallback
    if not bot_reply:
        bot_reply = "Sorry, I didn’t understand. Connecting to agent..."

    #  save with timestamp
    db.collection("chats").add({
        "user": user_message,
        "bot": bot_reply,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    bot_reply = bot_reply.replace("\n", "<br>")
    return jsonify({"reply": bot_reply})

# Admin Dashboard
@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/admin-login')

    chats = db.collection("chats").stream()

    #  sort latest first
    chat_list = sorted(
        [c.to_dict() for c in chats],
        key=lambda x: x.get("time", ""),
        reverse=True
    )

    return render_template("admin.html", chats=chat_list)

# Analytics API
@app.route('/analytics')
def analytics():
    chats = db.collection("chats").stream()
    user_msgs = [c.to_dict()["user"] for c in chats]

    top_queries = Counter(user_msgs).most_common(5)

    return jsonify({
        "total_chats": len(user_msgs),
        "top_queries": top_queries
    })

# Login route
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get("username")
        pwd = request.form.get("password")

        if user == ADMIN_ID and pwd == ADMIN_PASS:
            session['admin'] = True
            return redirect('/admin')
        else:
            return "Invalid credentials"

    return render_template("login.html")

# Clear chat route
@app.route('/clear-chats')
def clear_chats():
    if not session.get('admin'):
        return redirect('/admin-login')

    chats = db.collection("chats").stream()

    for chat in chats:
        db.collection("chats").document(chat.id).delete()

    return redirect('/admin')

# Logout route
@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/')

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)