from googleapiclient import discovery
import json
import os
import report
from report import Report_Details

PERSPECTIVE_AUTODELETE_THRESHOLD = 0.9

SENSITIVITY_MODES = {
    "Extra Strict": 0.3,
    "Strict": 0.5,
    "Moderate": 0.7,
    "Loose": 0.9,
}

REPORT_HIERARCHY = {
    "THREAT",
    "SEXUALLY_EXPLICIT",
    "SEVERE_TOXICITY",
    "IDENTITY_ATTACK",
    "INSULT",
    "TOXICITY"
}

ATTRIBUTE_MAPPING = {
    "THREAT": [report.THREAT_CHOICE, report.OTHER_CHOICE],
    "SEXUALLY_EXPLICIT": [report.OFFENSIVE_CHOICE, report.SEXUAL_CONTENT_CHOICE],
    "SEVERE_TOXICITY": [report.HARASSMENT_CHOICE, report.TARGET_ATTACK_CHOICE],
    "IDENTITY_ATTACK": [report.OFFENSIVE_CHOICE, report.HATE_SPEECH_CHOICE],
    "INSULT": [report.HARASSMENT_CHOICE, report.TARGET_ATTACK_CHOICE],
    "TOXICITY": [report.HARASSMENT_CHOICE, report.TARGET_ATTACK_CHOICE],
}


def parse_perspective_response(response):
    attribute_scores = {}
    for attribute in response['attributeScores'].keys():
        attribute_scores[attribute] = response['attributeScores'][attribute]['summaryScore']['value']
    return attribute_scores

def get_message_report_type(msg_attributes, sensitivity):
    for attribute in REPORT_HIERARCHY:
        if msg_attributes[attribute] > sensitivity:
            return attribute, msg_attributes[attribute]
    return None, None

# returns a report and associated confidence score, or None if the message is not toxic
def perspective_analyze_message(perspective_api_client, message, sensitivity = 0.7):
    print("ANALYZING MESSAGE")
    analyze_request = {
        'comment': { 'text': message.content},
        'requestedAttributes': {'TOXICITY': {}, 'SEVERE_TOXICITY': {}, 'IDENTITY_ATTACK': {}, 'INSULT': {}, 'THREAT': {}, 'SEXUALLY_EXPLICIT': {}}
        }
    response = perspective_api_client.comments().analyze(body=analyze_request).execute()
    parsed_response = parse_perspective_response(response)
    report_type, score = get_message_report_type(parsed_response, sensitivity)
    print(parsed_response)
    print("MSG CATEGORY:", report_type, "with score", score)
    print()
    return generate_report(message, report_type), score

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

