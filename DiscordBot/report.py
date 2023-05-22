from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    SPAM_REPORT_START = auto()
    HARASSMENT_REPORT_START = auto()
    OFFENSIVE_CONTENT_REPORT_START = auto()
    THREATS_REPORT_START = auto()
    OTHER_REPORT_START = auto()
    SELECT_REPORT_TARGRT = auto()
    REPORT_COMPLETE = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]
        
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

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_IDENTIFIED
            reply = ["I found this message:", "```" + message.author.name + ": " + message.content + "```"]
            select_report_type_reply = "Please select the reason for report from the following options:\n"
            select_report_type_reply += "`1`: Spam\n"
            select_report_type_reply += "`2`: Harassment\n"
            select_report_type_reply += "`3`: Offensive Content\n"
            select_report_type_reply += "`4`: Threats\n"
            select_report_type_reply += "`5`: Other\n"
            reply.append(select_report_type_reply)
            return reply
        
        if self.state == State.MESSAGE_IDENTIFIED:
            if message.content == "1":
                self.state = State.SPAM_REPORT_START
                reply = "Thank you for reporting! Please select the type of span by entering one of the following options: `1a`, `1b`, `1c`, `1d`:\n"
                reply += "`1a`: Scam\n"
                reply += "`1b`: Soliciation\n"
                reply += "`1c`: Repeated Unwanted Messages\n"
                reply += "`1d`: Bot\n"
                return [reply]
            elif message.content == "2":
                self.state = State.HARASSMENT_REPORT_START
                reply = "Thank you for reporting! Please select the type of harassment by entering one of the following options: `2a`, `2b`, `2c`, `2d`:\n"
                reply += "`2a`: Appearance Attack\n"
                reply += "`2b`: Sexual Harassment\n"
                reply += "`2c`: Targeted Attack\n"
                reply += "`2d`: Revealing Personal Info\n"
                return [reply]
            elif message.content == "3":
                self.state = State.OFFENSIVE_CONTENT_REPORT_START
                reply = "Thank you for reporting! Please select the type of offensive content by entering one of the following options: `3a`, `3b`:\n"
                reply += "`3a`: Hate Speech\n"
                reply += "`3b`: Sexual Content\n"
                return [reply]
            elif message.content == "4":
                self.state = State.THREATS_REPORT_START
                reply = "Thank you for reporting! Please select the type of threat by entering one of the following options: `4a`, `4b`, `4c`, `4d`:\n"
                reply += "`4a`: Threat to Swat\n"
                reply += "`4b`: Threat to Cyber Attack\n"
                reply += "`4c`: Self-harm\n"
                reply += "`4d`: Violent Messaging\n"
            elif message.content == "5":
                self.state = State.OTHER_REPORT_START
                reply = "Thank you for reporting! Please enter details.\n"
                return [reply]
            else:
                return ["Please choose from the list. Try again or say `cancel` to cancel."]
        
        # TODO: save user selection
        if self.state == State.SPAM_REPORT_START:
            if message.content not in ["1a", "1b", "1c", "1d"]:
                return ["Please choose from the list. Try again or say `cancel` to cancel."]
            self.state = State.SELECT_REPORT_TARGRT
            reply = "Do these messages bother you or the streamer?\n Select from `me` or `streamer`"
            return [reply]
        
        if self.state == State.HARASSMENT_REPORT_START:
            if message.content not in ["2a", "2b", "2c", "2d"]:
                return ["Please choose from the list. Try again or say `cancel` to cancel."]
            self.state = State.SELECT_REPORT_TARGRT
            reply = "Do these messages bother you or the streamer?\n Select from `me` or `streamer`"
            return [reply]
        
        if self.state == State.OFFENSIVE_CONTENT_REPORT_START:
            if message.content not in ["3a", "3b"]:
                return ["Please choose from the list. Try again or say `cancel` to cancel."]
            
        if self.state == State.THREATS_REPORT_START:
            if message.content not in ["4a", "4b", "4c", "4d"]:
                return ["Please choose from the list. Try again or say `cancel` to cancel."]
            self.state = State.REPORT_COMPLETE
            return ["Your report will be reviewed and potentially reported to local authorities."]
        
        if self.state == State.OTHER_REPORT_START:
            self.state = State.SELECT_REPORT_TARGRT
            reply = "Do these messages bother you or the streamer?\n Select from `me` or `streamer`"
            return [reply]

        if self.state == State.SELECT_REPORT_TARGRT:
            if message.content not in ["me", "streamer"]:
                return ["Please choose from the list. Try again or say `cancel` to cancel."]
            return ["TODO"]

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    


    

