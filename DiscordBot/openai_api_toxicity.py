# This is example code using GPT-4 to do a basic classification of a text string
# It is super basic, your milestone 3 should do better than this
# This is a live API key that should be used only for the CS 152 project
# Please do not check the API key into a public GitHub repo or share it with anybody outside of your group


import os
import openai
import report
from report import Report_Details
# print(openai.Model.list()) # Can used to verify GPT-4 access


ATTRIBUTE_MAPPING = {
    "Spam": [report.SPAM_CHOICE, report.OTHER_CHOICE],
    "Harassment": [report.HARASSMENT_CHOICE, report.OTHER_CHOICE],
    "Offensive Content": [report.OFFENSIVE_CHOICE, report.OTHER_CHOICE],
    "Threatening": [report.THREAT_CHOICE, report.OTHER_CHOICE],
    "Not Harmful": [None, None]
}

# returns a report and associated confidence score, or None if the message is not toxic
def get_gpt4_response(message, openai_org_token, openai_token, sensitivity=0.7):
    return None, None
    
    openai.organization = openai_org_token
    openai.api_key = openai_token
    next_prompt = {"role": "user", "content": message.content}

    response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
    {"role": "system", "content": "You are a content moderation system for a livestreaming chat. Classify each input as either Spam, Harassment, Offensive Content, Threatening, or Not Harmful. Also provide a confidence score that the message belongs to the particular category."},
    {"role": "user", "content": "I am going to kill you."},
    {"role": "assistant", "content": "Threatening, 1.0"},
    {"role": "user", "content": "I love you"},
    {"role": "assistant", "content": "Not Harmful, 1.0"},
    {"role": "user", "content": "DM me for a link to free bitcoin!"},
    {"role": "assistant", "content": "Spam, 0.94"},
    {"role": "user", "content": "I think anyone who is not white is inferior."},
    {"role": "assistant", "content": "Offensive Content, 0.99"},
    {"role": "user", "content": "You are stupid and also look terrible. and your address is 450 Serra Mall, Stanford, CA."},
    {"role": "assistant", "content": "Harassment, 0.99"},
    {"role": "user", "content": "You live at 450 Serra Mall, Stanford, CA."},
    {"role": "assistant", "content": "Harassment, 0.98"},
    next_prompt
    ]
    )

    output = response['choices'][0]['message']['content']
    category = output[:output.find(",")].strip()
    score = float(output[output.find(",") + 1:])
    print("GPT eval: ", category, ", ", score)
    if category == "Not Harmful" or score < sensitivity:
        return None, None
    return generate_report(message, category), score

def generate_report(message, report_type):
    if report_type is None:
        return None
    auto_report_details = Report_Details()
    auto_report_details.message_id = message.id
    auto_report_details.message_content = message.content
    auto_report_details.reporter = None
    auto_report_details.report_reason = ATTRIBUTE_MAPPING[report_type][0]
    auto_report_details.report_subcategory = ATTRIBUTE_MAPPING[report_type][1]
    auto_report_details.organized_attack = 0
    auto_report_details.author = message.author.name
    auto_report_details.message_content = message.content
    auto_report_details.channel = message.channel
    auto_report_details.auto_flagged = 1
    return auto_report_details

# Message (discord message object, message.content contains the text)
def get_classification_result(message, openai_org_token, openai_token, sensitivity=0.7):
    report, score = get_gpt4_response(message, openai_org_token, openai_token, sensitivity=sensitivity)
    if report is None:
        return None, score
    else:
        return report.report_reason, score