from google.cloud import dialogflow
import pandas as pd
import os
import re

#  Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "dialogflow-key.json"

PROJECT_ID = "my-chatbot-rvye"   # 🔴 my dialogflow project id


# ---------------- CLEAN TEXT ----------------
def clean_text(text):
    text = str(text).strip().lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)  # remove special chars
    return text


# ---------------- SMART SELECTION ----------------
def select_diverse_phrases(questions, max_phrases=10):
    questions = list(set(questions))  # remove duplicates

    if len(questions) <= max_phrases:
        return questions

    # pick evenly spaced phrases for diversity
    step = max(1, len(questions) // max_phrases)
    selected = questions[::step]

    return selected[:max_phrases]


# ---------------- CREATE INTENT ----------------
def create_intent(display_name, training_phrases, message_texts):
    intents_client = dialogflow.IntentsClient()
    parent = dialogflow.AgentsClient().agent_path(PROJECT_ID)

    training_phrases_parts = []
    for phrase in training_phrases:
        part = dialogflow.Intent.TrainingPhrase.Part(text=phrase)
        training_phrases_parts.append(
            dialogflow.Intent.TrainingPhrase(parts=[part])
        )

    message = dialogflow.Intent.Message(
        text=dialogflow.Intent.Message.Text(text=message_texts)
    )

    intent = dialogflow.Intent(
        display_name=display_name,
        training_phrases=training_phrases_parts,
        messages=[message],
    )

    intents_client.create_intent(
        request={"parent": parent, "intent": intent}
    )

    print(f" Created intent: {display_name}")


# ---------------- LOAD DATA ----------------
data = pd.read_csv("data.csv")

#  DEBUG (optional - remove later)
print("Columns:", data.columns)

# ---------------- CLEAN DATA ----------------
data['instruction'] = data['instruction'].apply(clean_text)
data['response'] = data['response'].apply(clean_text)

#  remove empty + duplicates
data = data.dropna()
data = data.drop_duplicates(subset=['instruction'])

#  limit rows for safety (increase later if needed)
#data = data.head(500)


# ---------------- GROUP BY INTENT ----------------
grouped = {}

for _, row in data.iterrows():
    intent_name = str(row[3])   # column D = intent
    question = row['instruction']
    answer = row['response']

    if intent_name not in grouped:
        grouped[intent_name] = {
            "questions": [],
            "answers": []
        }

    grouped[intent_name]["questions"].append(question)
    grouped[intent_name]["answers"].append(answer)


# ---------------- CREATE INTENTS ----------------
for intent_name, content in grouped.items():

    #  SMART PHRASE SELECTION
    questions = select_diverse_phrases(content["questions"], max_phrases=10)

    #  BEST ANSWER (most frequent)
    answer = max(set(content["answers"]), key=content["answers"].count)

    create_intent(
        display_name=intent_name,
        training_phrases=questions,
        message_texts=[answer]
    )