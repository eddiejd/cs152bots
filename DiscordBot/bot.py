# bot.py
import discord
from discord.ext import commands
from discord import ui
import os
import json
import logging
import re
import requests
from report import Report
from report import Select
from report import Data
from report import Mod_Report
from report import Report_Details
import openai_api_toxicity
import perspective_api_toxicity
from perspective_api_toxicity import perspective_analyze_message
from openai_api_toxicity import get_gpt4_response
import copy
from googleapiclient import discovery
from sentence_transformers import util
from similarity_model import SENTENCE_MODEL
from collections import defaultdict

import pdb

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    perspective_token = tokens['perspective']
    openai_org_token = tokens['openai_organization']
    openai_token = tokens['openai_sk']

perspective_api_client = discovery.build(
  "commentanalyzer",
  "v1alpha1",
  developerKey=perspective_token,
  discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
  static_discovery=False,
)

perspective_api_sensitivity = perspective_api_toxicity.SENSITIVITY_MODES["Moderate"]
similarity_threshold = 0.7

# Our universal data storage
data = Data()

class ModBot(discord.Client):
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.actual_channel = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.moderators = {} # Map from moderator IDs to the state of their moderation
        self.flagged_messages = {}
        self.prohibited_messages = ["DM me for a link to free bitcoin", "prohibit test"] # dummy predifined prohibited messages

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
        

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def handle_dm(self, message):
        # Handle a help message dm
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle the message; forward all the messages it returns to us
        """ 
        NOTES FROM EDDIE: We have to get funky with a while loop, because when a user selects something in a menu,
        They don't send a message back, and so our next handle_dm wouldn't actually trigger.
        Instead, we keep a loop going and wait for the user to complete an interaction with our select menu, and then loop
        back to getting our bot's next response to their chosen selection (which could be another selection menu, or a text-prompt)
        """ 
        send_message = message
        selections = []
        keep_loop = True
        while keep_loop:
            responses = await self.reports[author_id].handle_message(send_message)
            keep_loop = False
            for r in responses:
                # if this response is a list not a string (NOTE! ASSUMED TO BE A DROPDOWN OPTION LIST): 
                if isinstance(r, list):
                    # Then create our selection menu, send it to the user, and wait 
                    for option in r:
                        if len(option.label) >= 95: # discord has a limit of 100 character per label; truncate if label too long
                            option.label = option.label[:95] + "..."
                    select = Select(r, self.reports[author_id], k=1)
                    select_view = ui.View(timeout=None)
                    select_view.add_item(select)
                    await message.channel.send(view=select_view)
                    # POTENTIAL FLAG! Later on, with concurrency / many users at once, we may need to add a menu_id to our wait_for so we don't
                    # wake up early for another slection 
                    await self.wait_for("interaction")
                    selections = select.selections
                    keep_loop = True
                # If this response is just a string, then send as normal
                else:
                    await message.channel.send(r)
            send_message = selections
        
        # If our report is now completed or cancelled, remove from our ongoing reports
        completed_report = self.reports[author_id].report_complete()
        if completed_report:
            self.reports.pop(author_id)
            # if we had a completed report (not a cancelled one: which would just be True), add it to our data
            if isinstance(completed_report, Report_Details):
                data.add_report(completed_report)
                # if it was flagged as an organized attack, start actively monitoring for this message content (add to our flagged_ list)
                if completed_report.organized_attack:
                    completed_report.auto_flagged = 1
                    self.flagged_messages[completed_report.message_content] = completed_report
                
    
    async def handle_channel_message(self, message):
        # Handle moderating messages sent in the "group-#-mod" channel
        if message.channel.name == f'group-{self.group_num}-mod':
            author_id = message.author.id
            responses = []

            if message.content.startswith("!flag_sensitivity"):
                try:
                    global perspective_api_sensitivity
                    perspective_api_sensitivity = float(message.content[message.content.find(" ") + 1:].strip())
                    await message.channel.send(f"Set auto flag sensitivty to {perspective_api_sensitivity}")
                except:
                    await message.channel.send(f"Failed to set sensitivity, please type command in form `!flag_sensitivity [SENSITIVITY]`")

            if message.content.startswith("!similarity_threshold"):
                try:
                    global similarity_threshold
                    similarity_threshold = float(message.content[message.content.find(" ") + 1:].strip())
                    await message.channel.send(f"Set similarity threshold to {similarity_threshold}")
                except:
                    await message.channel.send(f"Failed to set similarity threshold, please type command in form `!similarity_threshold [THRESHOLD]`")

            # Only respond to messages if they're part of a moderating flow
            if author_id not in self.moderators and not message.content.startswith(Mod_Report.MOD_START_KEYWORD):
                return

            # If we don't currently have an active moderating flow for this user, add one
            if author_id not in self.moderators:
                self.moderators[author_id] = Mod_Report(self, data)

            # Let the mod_report class handle the message; forward all the messages it returns to us
            send_message = message
            selections = []
            keep_loop = True
            # NOTE: SEE DM FUNCTION ABOUT THE WHILE LOOP REASONING
            while keep_loop:
                responses = await self.moderators[author_id].handle_message(send_message)
                keep_loop = False
                for r in responses:
                    if isinstance(r, list):
                        # Note: a fixed k is currently a weird earlier artifact from Eddie (sorry) to ensure multiple-selection dropdowns. It's not actually what we want in our yes-no options. 
                        # We may want to make it so that each response here has a parameter itself for how many options should be selected (i.e. a bool: single-choice or any)
                        for option in r:
                            if len(option.label) >= 95: # discord has a limit of 100 character per label; truncate if label too long
                                option.label = option.label[:95] + "..."
                        select = Select(r, self.moderators[author_id], k=25)
                        select_view = ui.View(timeout=None)
                        select_view.add_item(select)
                        await message.channel.send(view=select_view)
                        # again, may need to specify.
                        await self.wait_for("interaction")
                        selections = select.selections
                        keep_loop = True
                    else:
                        await message.channel.send(r)
                send_message = selections
            
            # If completed or cancelled, remove from our ongoing moderations
            completed_moderator = self.moderators[author_id].moderator_complete()
            if completed_moderator:
                self.moderators.pop(author_id)
                
        
        # For messages in group-#, examine for flagged or prohibited messages 
        elif message.channel.name == f'group-{self.group_num}':
             # For messages in group-#, examine for flagged or prohibited messages 
            mod_channel = self.mod_channels[message.guild.id]
            flagged_or_prohibited = self.eval_text(message)
            if flagged_or_prohibited: 
                await mod_channel.send(self.code_format(message.content, flagged_or_prohibited))
                if "deleted" in flagged_or_prohibited:
                    await message.delete()
        return 
    
    def check_message_similarity(self, message, messages_to_compare, threshold=0.7):
        # check if message is similar to messages_to_compare
        message_embedding = SENTENCE_MODEL.encode(message.content)
        messages_to_compare_embeddings = SENTENCE_MODEL.encode(messages_to_compare)
        cos_similarities = util.cos_sim(message_embedding, messages_to_compare_embeddings)
        max_similarity = cos_similarities.max().item()
        max_similarity_index = cos_similarities.argmax().item()
        message_with_max_similarity = messages_to_compare[max_similarity_index]
        if max_similarity > threshold:
            return True, message_with_max_similarity
        return False, None


    def eval_text(self, message):
        ''''
        TODO: Once you know how you want to evaluate messages in your channel, 
        insert your code here! This will primarily be used in Milestone 3. 
        '''
        print(list(self.flagged_messages.keys()))
        # delete if prohibited: this will be useful with an auto-filter
        if message.content in self.prohibited_messages:
            return "deleted [prohibited message]"
        # delete if similar to prohibited messages
        elif self.check_message_similarity(message, self.prohibited_messages, similarity_threshold)[0]:
            return "deleted [prohibited message]"
        elif len(list(self.flagged_messages.keys())) > 0:
             # flag if the content matches previously user-flagged content 
            if message.content in list(self.flagged_messages.keys()):
                new_report = copy.copy(self.flagged_messages[message.content])
                new_report.author = message.author.name
                new_report.message_id = message.id
                new_report.message_content = message.content
                data.add_report(new_report)
                return "auto-flagged"
            else:
                # flag if the content is similar to previously user-flagged content
                is_similar, similar_message = self.check_message_similarity(message, list(self.flagged_messages.keys()), similarity_threshold)
                if is_similar:
                    new_report = copy.copy(self.flagged_messages[similar_message])
                    new_report.author = message.author.name
                    new_report.message_id = message.id
                    new_report.message_content = message.content
                    data.add_report(new_report)
                    return "auto-flagged"
        else:
            # GPT4 is super slow, so I think perspective api is better for livestreaming applicaiton
            #new_report, gpt_score = get_gpt4_response(message, openai_org_token, openai_token, sensitivity=perspective_api_sensitivity)
            new_report, score = perspective_analyze_message(perspective_api_client, message, sensitivity=perspective_api_sensitivity)
            #print("Perspective score: ", score, "GPT score: ", gpt_score)
            if new_report is not None:
                if score > perspective_api_toxicity.PERSPECTIVE_AUTODELETE_THRESHOLD:
                    return "deleted [exceeds toxicity threshold]"
                else:
                    data.add_report(new_report)
                    return "auto-flagged"
            else:
                return False
    
    
    def code_format(self, text, flagged_or_prohibited):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return "Bot " + flagged_or_prohibited + " the message: `" + text + "`"


client = ModBot()
client.run(discord_token)
