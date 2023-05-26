from enum import Enum, auto
import discord
import re
from discord import ui
from discord.ext import commands
import pandas as pd
import copy

class State(Enum):
    # User States
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    SPAM_REPORT_START = auto()
    HARASSMENT_REPORT_START = auto()
    OFFENSIVE_CONTENT_REPORT_START = auto()
    THREATS_REPORT_START = auto()
    OTHER_REPORT_START = auto()
    SELECT_REPORT_TARGET = auto()
    FILTERING_OPTION = auto()
    ASK_ORGANIZED_ATTACK = auto()
    REPORT_COMPLETE = auto()

    # Moderator States
    MOD_START = auto()
    REPORT_SELECTION = auto()
    ASK_VIOLATION = auto()
    MALICIOUS_REPORT = auto()
    ASK_DANGER = auto()
    ASK_PUNISHMENT= auto()
    PREVIOUS_PUNISHMENT = auto()
    FLAG_SIMILAR = auto()
    ASK_VIOLATION_2 = auto()
    ASK_PUNISHMENT_2 = auto()
    ASK_FILTER_WORDS = auto()
    MOD_COMPLETE = auto()
    

# selection menu class, which will store our selected options in our drow-downs
class Select(ui.Select):
    def __init__(self, options, report, k):
        self.selections = None
        self.report = report
        max_values = 1
        # if k is greater than one, then make multiple choice (NOTE: Eddie can fix. Should switch to a bool)
        if k > 1:
            max_values = len(options)
        super().__init__(placeholder="Select", custom_id="idk", options=options, min_values=1, max_values=max_values)
        
    async def callback(self, interaction):
        self.selections = self.values
        await interaction.response.defer()

# class for storing the details of an individual report
class Report_Details:
    def __init__(self):
        self.message_id = None
        self.message_content = None
        self.reporter = None
        self.report_reason = None
        self.report_subcategory = None
        self.organized_attack = None
        self.author = None
        self.channel = None
        self.auto_flagged = 0

# class for storing our data of reports                                        
class Data:
    def __init__(self):
        # list of malicious reporters
        self.malicious_reporters = []
        # df with our reported messages
        self.moderate_messages = pd.DataFrame(columns = ['ID', 'Content', 'Author', 'Reporter', "Report_Reason", "Report_SubCategory", "Organized_Attack", "Auto_Flagged", 'Channel', 'Deleted'])
        self.priority_order = {'Threats': 0, 'Harassment': 1, 'Offensive Content': 2, 'Spam': 3, 'Other': 4}

    # return up to the top 25 messages (max allowed in a selection menu) in priority order 
    def top_25_messages(self):
        df = self.moderate_messages.loc[self.moderate_messages['Deleted'] == 0]
        sorted_df = df.sort_values(by=['Report_Reason'], key=lambda x: x.map(self.priority_order))
        return sorted_df.head(25)

    # return past offenses of user
    def past_offenses(self, author):
        # NOTE: Eddie can fix here. Should use separate bool for "deleted" and "dismissed", since right now this includes rejected/dismissed reports
        df = self.moderate_messages.loc[(self.moderate_messages['Author'] == author) & (self.moderate_messages['Deleted'] == 1)]
        return df

    # return similar, not-yet-deleted messages
    def get_similar_messages(self, content):
        df = self.moderate_messages.loc[(self.moderate_messages.Content == str(content)) & (self.moderate_messages.Deleted == 0)]
        return df.head

    # remove a selected message from the channel, and mark as deleted in our dataset  
    async def remove_selected_message(self, ID):
        match = self.moderate_messages.loc[self.moderate_messages['ID'] == int(ID)]
        channel = match['Channel'].iloc[0]
        msg = await channel.fetch_message(ID)
        await msg.delete()
        self.moderate_messages.loc[self.moderate_messages.ID == int(ID), 'Deleted'] = 1

    # add a new report to our moderate_messages df
    def add_report(self, report_details):
        new_report = {'ID': int(report_details.message_id), 'Content': report_details.message_content, 'Author': str(report_details.author), 'Reporter' : report_details.reporter, 'Report_Reason' : report_details.report_reason,
                      "Report_SubCategory": report_details.report_subcategory, 'Organized_Attack': report_details.organized_attack, 'Auto_Flagged': report_details.auto_flagged, 'Channel': report_details.channel, 'Deleted': 0
                      }
        # NOTE: Right now it only adds the message if not already reported (so our moderator doesn't see double). Currently a bit buggy(?)
        # In the future, we may want to adjust our priority moderator queue with the running tally of the number of times a message has been reported (i.e. many times should move up)
        if report_details.message_id not in self.moderate_messages['ID']:
            self.moderate_messages = pd.concat([self.moderate_messages, pd.DataFrame([new_report])], ignore_index=True)

YES_NO_OPTIONS = [discord.SelectOption(label="Yes"), discord.SelectOption(label='No')]
PUNISHMENT_1_OPTIONS = [discord.SelectOption(label="Warning"), discord.SelectOption(label='24 Hour Time Out'), discord.SelectOption(label='Shadow Ban'), discord.SelectOption(label='Ban')]
PUNISHMENT_2_OPTIONS = [discord.SelectOption(label='24 Hour Time Out'), discord.SelectOption(label='Shadow Ban'), discord.SelectOption(label='Ban')]    

# Class for handling our moderator channel
class Mod_Report:
    MOD_START_KEYWORD = "start"
    CANCEL_KEYWORD = "cancel"
    # Default selection options 
    YES_NO_OPTIONS = [discord.SelectOption(label="Yes"), discord.SelectOption(label='No')]
    PUNISHMENT_1_OPTIONS = [discord.SelectOption(label="Warning"), discord.SelectOption(label='24 Hour Time Out'), discord.SelectOption(label='Shadow Ban'), discord.SelectOption(label='Ban')]

    def __init__(self, client, data):
        self.state = State.MOD_START
        self.client = client
        self.message = None
        self.data = data
        self.selected = None
        self.channel = None
        self.authors_remaining = []
        self.current_author = None

    async def handle_message(self, message):
        if not isinstance(message, list) and message.content == self.CANCEL_KEYWORD: 
            self.state = State.MOD_COMPLETE
            return ["Moderation flow cancelled."]

        # To start, display top 25 reports
        if self.state == State.MOD_START:
            reply =  ["Thank you for starting the moderation process. Please select from ongoing user reports and flagged messages, ranked in order of report-type (threat, harassment, offensive content, spam, other)"]
            top_25_df = self.data.top_25_messages()
            report_options = []
            for index, report in top_25_df.iterrows():
                content = report['Content']
                report_options.append(discord.SelectOption(label=f"Content: {content}",
                                                           description=f"Author: {report['Author']}, Report Reason: {report['Report_Reason']}, Report SubCategory: {report['Report_SubCategory']}",
                                                           value=report['ID']))
            # if none, then complete
            if len(report_options) == 0: 
                self.state == State.MOD_COMPLETE
                return ["No reported messages left to moderate!"]

            self.state = State.REPORT_SELECTION
            reply.append(report_options)
            return reply

        # Select whether the messages were a violation
        if self.state == State.REPORT_SELECTION:
            self.state = State.ASK_VIOLATION
            self.selected = message
            reply = ["Does this message violate channel / website policies?"]
            reply.append(YES_NO_OPTIONS)
            return reply

        
        # Handle violation paths
        if self.state == State.ASK_VIOLATION:
            choice = message[0]
            if choice == "Yes":
                # delete each message if violation
                for message_id in self.selected:
                    await self.data.remove_selected_message(message_id)
                reply = ["The messages have been deleted"]
                # move on to asking about whether dangerous
                self.state =  State.ASK_DANGER
                reply.append("Is the content illegal or does it pose an immediate threat?") 
                reply.append(YES_NO_OPTIONS)
                return reply
            else:
                # move on to asking if malicious report if not violation 
                self.state = State.MALICIOUS_REPORT
                # Remove from our list of reports. NOTE: Eddie will change to add separate "Dismissed" flag in the future
                for message_id in self.selected:
                    self.data.moderate_messages.loc[self.data.moderate_messages.ID == int(message_id), 'Deleted'] = 1
                reply = ["Is this a malicious report?"]
                reply.append(YES_NO_OPTIONS)
                return reply

        # Handle malicious report selection
        if self.state == State.MALICIOUS_REPORT:
            choice = message[0]
            reply = []
            if choice == "Yes":
                messages = copy.copy(self.data.moderate_messages)
                authors = set()
                # if malicious, collect ALL offending authors in the selected messages
                for message_id in self.selected:
                    match = messages.loc[messages['ID'] == int(message_id)]
                    author = match['Author'].iloc[0]
                    authors.add(author)
                # Loop through each, and issue the appropriate warning or timeout depending on if their first time offense
                # NOTE: multiple fake offenses from the same reporter in one selection, will still be considered a first-time warning, not a warning + timeout
                for author in list(authors):
                    if author in self.data.malicious_reporters:
                        reply.append(f"SYSTEM: Repeat malicious reporter {author} has been given a 24 Hour Timeout.")
                    else:
                        reply.append(f"SYSTEM: First-time malicious reporter {author} has been warned.")
                        self.data.malicious_reporters.append(author)
                
                self.state = State.MOD_COMPLETE
                reply.append("Moderation flow completed.")
                return reply
            # NOTE: Eddie will just standardize the if-elses lol
            else:
                self.state = State.MOD_COMPLETE
                reply = ["Moderation flow completed."]
                return reply

        # Handle danger selection (for real reports)
        if self.state == State.ASK_DANGER:
            choice = message[0]
            reply = []
            if choice == "Yes":
                # IF yes, ban all authors involve and complete
                messages = copy.copy(self.data.moderate_messages)
                authors = set() 
                for message_id in self.selected:
                    match = messages.loc[messages['ID'] == int(message_id)]
                    author = match['Author'].iloc[0]
                    authors.add(author)
                for author in list(authors):
                    reply.append(f"SYSTEM: User {author} have been banned, and reported to law enforcement")
                self.state = State.MOD_COMPLETE
                reply.append("Moderation flow completed.")
                return reply
            else:
                # Otherwise, begin loop through each author individual to decide punishment 
                messages = copy.copy(self.data.moderate_messages)
                authors = set()

                for message_id in self.selected:
                    match = messages.loc[messages['ID'] == int(message_id)]
                    author = match['Author'].iloc[0]
                    authors.add(author)
                
                self.authors_remaining = list(authors)
                
                self.state = State.PREVIOUS_PUNISHMENT
                reply.append("We will now go through each of the authors of your selected message(s), to determine appropriate punishments")
                # Move on to Previous Punishments without returning yet


        if self.state == State.PREVIOUS_PUNISHMENT:
            # If no more authors to punish, move on to final organized_attack path
            if len(self.authors_remaining) == 0:
                report_options = []
                content_to_check = set()
                # loop through to get a set of all the content in the selected messages, if flagged as part of an organized attack 
                for message_id in self.selected:
                    match = self.data.moderate_messages.loc[self.data.moderate_messages.ID == int(message_id)]
                    content = match['Content'].iloc[0]
                    organized_attack = match['Organized_Attack'].iloc[0]
                    if organized_attack:
                        content_to_check.add(content)

                # loop through the content to build a dropdown of any remaining similar but unselected messages
                # EDDIE NOTE: Currently stops at an error-throwing number of similar messages (>25). May want to switch if we do an auto filter here rather than selection menu.
                total_options = 0
                for content in list(content_to_check):
                    similar_df = self.data.get_similar_messages(content)
                    print(similar_df)
                    for index, report in similar_df.iterrows():
                        total_options += 1
                        content = report['Content']
                        if total_options < 25: 
                            report_options.append(discord.SelectOption(label=f"Content: {content}",
                                                                        description=f"Author: {report['Author']}, Report Reason: {report['Report_Reason']}, Report SubCategory: {report['Report_SubCategory']}",
                                                                       value=report['ID']))
                # Finish if no organized_attack messages or similar non-deleted messages for them
                if len(report_options) == 0: 
                    self.state == State.MOD_COMPLETE
                    return ["No reported messages left to moderate!"]

                self.state = State.REPORT_SELECTION
                reply = ['This content may be part of an organized attack. Please verify the following similar messages in the options below'] 
                reply.append(report_options)
                return reply

            # if authors left:
            self.current_author = self.authors_remaining[0]
            self.authors_remaining.pop(0) # Note: Can merge lines. Got a weird reference error before but should just pop directly into current_author in theory

            # For the author: print their past offenses (including the ones just deleted)
            past_offenses = self.data.past_offenses(self.current_author)
            if past_offenses.empty:
                reply.append(f"Note: {self.current_author} is a first-time offender \n")
            else:
                reply.append(f"Here are all historic reports of the offending author {self.current_author}: \n")
                for index, report in past_offenses.iterrows():
                    content = report['Content']
                    offense = report['Report_Reason']
                    reply.append(f"Message: {content}, Reported Offense: {offense}")

            # now ask for punishment 
            reply.append(f"Which punishment do you believe should be issued to author: {self.current_author}?")
            reply.append(PUNISHMENT_1_OPTIONS)
            self.state = State.ASK_PUNISHMENT
            return reply

        if self.state == State.ASK_PUNISHMENT:
            choice = message[0]
            reply = [f"SYSTEM: User {self.current_author} has been issued a punishment of {choice} \n"]
            # NOTE FROM EDDIE: currently requires moderator to enter a message to loop back to Previous_Punishment for any remaining authors / terminate the flow (simplest to implement)
            # Can just get more creative with the loop /discord api to prevent the need for this 
            reply.append("Type anything to move to the next author")
            self.state = State.PREVIOUS_PUNISHMENT
            return reply 

    def moderator_complete(self):
        return self.state == State.MOD_COMPLETE
        

START_KEYWORD = "report"
MOD_KEYWORD = "start"
CANCEL_KEYWORD = "cancel"
HELP_KEYWORD = "help"
REPORTING_OPTIONS = [discord.SelectOption(label="Spam"), discord.SelectOption(label='Harassment'), discord.SelectOption(label='Offensive Content'), discord.SelectOption(label='Threats'), discord.SelectOption(label='Other')]
SPAM_OPTIONS = [discord.SelectOption(label="Scam"), discord.SelectOption(label='Soliciation'), discord.SelectOption(label='Repeated Unwanted Messages'), discord.SelectOption(label='Bot'), discord.SelectOption(label='Other')]
HARASSMENT_OPTIONS = [discord.SelectOption(label="Appearance Attack"), discord.SelectOption(label='Sexual Harassment'), discord.SelectOption(label='Targeted Attack'), discord.SelectOption(label='Revealing Personal Info'), discord.SelectOption(label='Other')]
OFFENSIVE_CONTENT_OPTIONS = [discord.SelectOption(label="Hate Speech"), discord.SelectOption(label='Sexual Content'), discord.SelectOption(label='Other')]
THREATS_OPTIONS = [discord.SelectOption(label="Threat to Swat"), discord.SelectOption(label='Threat to Cyber Attack'), discord.SelectOption(label='Self-harm'), discord.SelectOption(label='Violent Messaging'), discord.SelectOption(label='Other')]
TARGET_OPTIONS = [discord.SelectOption(label="Me"), discord.SelectOption(label='Streamer')]
FILTER_OPTIONS = [discord.SelectOption(label="Yes"), discord.SelectOption(label='No')]
ORGANIZED_ATTACK_OPTIONS = [discord.SelectOption(label="Yes"), discord.SelectOption(label='Unsure'), discord.SelectOption(label='No')]


# Class for handling our user reports dms
class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    REPORTING_OPTIONS = [discord.SelectOption(label="Spam"), discord.SelectOption(label='Harassment'), discord.SelectOption(label='Offensive Content'), discord.SelectOption(label='Threats'), discord.SelectOption(label='Other')]
    SPAM_OPTIONS = [discord.SelectOption(label="Scam"), discord.SelectOption(label='Soliciation'), discord.SelectOption(label='Repeated Unwanted Messages'), discord.SelectOption(label='Bot'), discord.SelectOption(label='Other')]
    HARASSMENT_OPTIONS = [discord.SelectOption(label="Appearance Attack"), discord.SelectOption(label='Sexual Harassment'), discord.SelectOption(label='Targeted Attack'), discord.SelectOption(label='Revealing Personal Info'), discord.SelectOption(label='Other')]
    OFFENSIVE_CONTENT_OPTIONS = [discord.SelectOption(label="Hate Speech"), discord.SelectOption(label='Sexual Content'), discord.SelectOption(label='Other')]
    THREATS_OPTIONS = [discord.SelectOption(label="Threat to Swat"), discord.SelectOption(label='Threat to Cyber Attack'), discord.SelectOption(label='Self-harm'), discord.SelectOption(label='Violent Messaging'), discord.SelectOption(label='Other')]
    TARGET_OPTIONS = [discord.SelectOption(label="Me"), discord.SelectOption(label='Streamer')]
    FILTER_OPTIONS = [discord.SelectOption(label="Yes"), discord.SelectOption(label='No')]
    ORGANIZED_ATTACK_OPTIONS = [discord.SelectOption(label="Yes"), discord.SelectOption(label='Unsure'), discord.SelectOption(label='No')]

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
        self.report_details = Report_Details()

    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''
        
        if not isinstance(message, list) and message.content == self.CANCEL_KEYWORD: 
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
    
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            self.report_details.reporter = message.author.name
            self.report_details.organized_attack = 0
            return [reply]

        # Initial Reporting
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Identified message, now have user select report type, as we store our report details
            self.state = State.MESSAGE_IDENTIFIED
            reply = ["I found this message:", "```" + message.author.name + ": " + message.content + "```"]
            reply.append("Please select the reason for reporting the message:\n")
            reply.append(REPORTING_OPTIONS)
            self.report_details.author = message.author.name
            self.report_details.message_id = message.id
            self.report_details.message_content = message.content
            self.report_details.channel = message.channel
            return reply
        
        # Follow paths depending on selected abuse type 
        if self.state == State.MESSAGE_IDENTIFIED:
            choice = message[0]
            reply = ["Thank you for reporting! Please select the type of " + choice + " from the following options:"]
            if choice == "Spam":
                self.state = State.SPAM_REPORT_START
                reply.append(SPAM_OPTIONS)
            elif choice == "Harassment":
                self.state = State.HARASSMENT_REPORT_START
                reply.append(HARASSMENT_OPTIONS)
            elif choice == "Offensive Content":
                self.state = State.OFFENSIVE_CONTENT_REPORT_START
                reply.append(OFFENSIVE_CONTENT_OPTIONS)
            elif choice == "Threats":
                self.state = State.THREATS_REPORT_START
                reply.append(THREATS_OPTIONS)
            elif choice == "Other":
                self.state = State.OTHER_REPORT_START
                reply = ["Thank you for reporting! Please enter more details.\n"]
            else:
                return ["Try again or say `cancel` to cancel."]
            self.report_details.report_reason = choice
            return reply

        # Move on to selecting abuse target if the message was "harassment", "spam", or "Other"
        if self.state == State.SPAM_REPORT_START or self.state == State.HARASSMENT_REPORT_START or self.state == State.OTHER_REPORT_START:
            if not isinstance(message, list):
                self.report_details.report_subcategory = message.content
            else:
                self.report_details.report_subcategory = message[0]

            self.state = State.SELECT_REPORT_TARGET
            reply = ["Do these messages target you or the streamer?"]
            reply.append(TARGET_OPTIONS)
            return reply

        # Move on to the option to filter messages if the message was "offensive content"
        if self.state == State.OFFENSIVE_CONTENT_REPORT_START:
            self.report_details.report_subcategory = message[0]
            self.state = State.FILTERING_OPTION
            reply = ["I'm sorry to hear that. Would you like to stop seeing messages from the user as we complete our moderation process?"]
            reply.append(FILTER_OPTIONS)
            return reply

        # End and move to law enforcement if the message was "threats"
        if self.state == State.THREATS_REPORT_START:
            self.report_details.report_subcategory = message[0]
            self.state = State.REPORT_COMPLETE
            return ["Your report will be reviewed and potentially reported to local authorities."]
        
        # Responding based on abuse target 
        if self.state == State.SELECT_REPORT_TARGET:
            choice = message[0]
            if choice == "Me":
                # Again move on to the option to filter the author's content if reporter is target
                self.state =  State.FILTERING_OPTION
                reply = ["I'm sorry to hear that. Would you like to stop seeing messages from the user as we complete our moderation process?"]
                reply.append(FILTER_OPTIONS)
                return reply
            elif choice == "Streamer":
                # Otherwise move on to clarifying whether it was an organized attack 
                self.state = State.ASK_ORGANIZED_ATTACK
                reply = ["Is this part of an organized attack?"]
                reply.append(ORGANIZED_ATTACK_OPTIONS)
                return reply
            else:
                print("Error: Didn't receive Me or Streamer. Please type 'cancel' to restart.")

        # Path for if user wants to block author. Both paths move on to organized attack (NOTE: Can standardize if-statement in future. Just wanted to error-check) 
        if self.state == State.FILTERING_OPTION:
            choice = message[0]
            if choice == "Yes":
                reply = ["SYSTEM: " + self.report_details.reporter + " blocked " + self.report_details.author]
                self.state = State.ASK_ORGANIZED_ATTACK
                reply.append("Is the reported message part of an organized attack?")
                reply.append(self.ORGANIZED_ATTACK_OPTIONS)
                return reply
            elif choice == "No":
                self.state = State.ASK_ORGANIZED_ATTACK
                reply = ["Is the reported message part of an organized attack?"]
                reply.append(self.ORGANIZED_ATTACK_OPTIONS)
                return reply
            else:
                return ['Error: Blocked was not Yes or No. Please type cancel to restart.']

        # Path for clarifying whether it was an organized attack
        if self.state == State.ASK_ORGANIZED_ATTACK:
            choice = message[0]
            if choice == "Yes" or choice == "Unsure":
                # no actual classifier for this milestone. just keep track so that we can monitor for exact match
                self.report_details.organized_attack = 1
                self.state = State.REPORT_COMPLETE 
                reply = "Note that our classifier has begun monitoring for similar messages\n"
                reply += "Thank you for your report. Your report will be reviewed, and the appropriate actions will be taken. This may include content removal, timeout, shadowban, ban, or a report to authorities if necessary."
                return [reply]
            elif choice == "No":
                self.state = State.REPORT_COMPLETE
                return ["Thank you for your report. Your report will be reviewed, and the appropriate actions will be taken. This may include content removal, timeout, shadowban, ban, or a report to authorities if necessary."]
            else:
                return ["Error: Invalid answer for Organized attack. Try again or type `cancel` to restart."]
        return []

    def report_complete(self):
        # return our report_details at the end, so we can add them to our data
        if self.state == State.REPORT_COMPLETE:
            return self.report_details
        return False
