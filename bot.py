import discord
import configparser
import asyncio
import json
import time
import datetime
from dateutil.relativedelta import relativedelta
import calendar
import random

config = configparser.ConfigParser()
config.read('config.ini')
settings = config['SETTINGS']
bountySettings = config['SERAPHICBOUNTY']
bountyChannelId = int(bountySettings['bountyChannel'])
with open('giveaway_data.json', 'r') as f:
    giveaway_data = json.load(f)

def message_is_not_pinned(m):
    return m.pinned == False

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # create the background task and run it in the background
        self.giveaway_background_task = self.loop.create_task(self.giveaway_background_task())

    async def on_ready(self):
        print('Logged on as', self.user)
    
    async def giveaway_background_task(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(60)
            
            if(await self.is_bounty_over()):
                await self.process_bounty()
                
    
    async def write_giveaway_data(self):
        with open('giveaway_data.json', 'w') as f:
            json.dump(giveaway_data, f, indent=4)

    async def is_bounty_over(self):
        return time.time() > giveaway_data["currentGiveaway"]["endTime"]
    
    async def process_bounty(self):
        winningNumber = random.randint(int(bountySettings['min']), int(bountySettings['max']))
        winningUser = False
        #Check all entries for a winner
        for userId in giveaway_data["currentGiveaway"]["entries"]:
            if winningNumber in giveaway_data["currentGiveaway"]["entries"][userId]:
                winningUser = self.get_user(int(userId))
        
        #Archive the current drawing
        ts = time.gmtime()
        giveaway_data["archive"][time.strftime("%Y%m%d", ts)] = giveaway_data["currentGiveaway"].copy()
        giveaway_data["archive"][time.strftime("%Y%m%d", ts)]["winningNumber"] = winningNumber
        giveaway_data["currentGiveaway"]["entries"] = {}

        #Figure out the next draw datetime
        today = datetime.datetime.now()
        rd = relativedelta(days=1, weekday=calendar.TUESDAY)
        giveaway_day = today + rd
        giveaway_day = giveaway_day.replace(hour=22, minute=0, second=0)
        giveaway_data["currentGiveaway"]["endTime"] = int(giveaway_day.timestamp())
        await self.write_giveaway_data()

        #Purge channel of non-pinned messages
        await self.get_channel(bountyChannelId).purge(limit=None, check=message_is_not_pinned, bulk=False)

        #Announce the results
        embedMessage = discord.Embed(title="Giveaway for {0}".format(time.strftime("%B %d", ts)), color=0x00ff00)
        embedMessage.add_field(name="Winning number", value=winningNumber, inline=False)

        if winningUser != False:
            embedMessage.add_field(name="Winner", value='<@'+str(winningUser.id)+'>', inline=False)
            embedMessage.add_field(name="Winner's guesses", value=giveaway_data["archive"][time.strftime("%Y%m%d", ts)]["entries"][str(winningUser.id)], inline=False)
            await self.get_channel(bountyChannelId).send('Congratulations <@{0}>! <@{1}> remember to give them their prize!'.format(winningUser.id, bountySettings["moneyGiverId"]))
        else:
            embedMessage.add_field(name="Winner", value="Nobody, better luck next week!", inline=False)

        await self.get_channel(bountyChannelId).send(embed=embedMessage)

    async def on_message(self, message):
        if message.channel.id != bountyChannelId :
            return

        if message.author == self.user:
            return

        if message.content.isnumeric() :
            userId = str(message.author.id)
            entry = int(message.content)
            
            #Create user's entry list if it doesn't exist
            if not userId in giveaway_data["currentGiveaway"]["entries"]:
                giveaway_data["currentGiveaway"]["entries"][str(userId)] = []

            #If the user has already entered this number
            if entry in giveaway_data["currentGiveaway"]["entries"][userId]:
                await message.add_reaction('\U0000274E')
                await message.channel.send("You have already chosen this number.")
                return
            
            #Incorrect values
            if entry < int(bountySettings['min']) or entry > int(bountySettings['max']):
                await message.add_reaction('\U0000274E')
                await message.channel.send("The numbers must be between {0} and {1}.".format(bountySettings['min'], bountySettings['max']))
                return
            
            #Value already picked
            for userId in giveaway_data["currentGiveaway"]["entries"]:
                if entry in giveaway_data["currentGiveaway"]["entries"][userId]:
                    await message.add_reaction('\U0000274E')
                    await message.channel.send("Someone else has already chosen this number.")
                    return

            giveaway_data["currentGiveaway"]["entries"][userId].append(entry)
            await self.write_giveaway_data()
            await message.add_reaction('\U00002705')
            

client = MyClient()
client.run(settings['token'])