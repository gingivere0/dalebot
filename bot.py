import copy
import os
from dotenv import load_dotenv
import requests
import json
from pathlib import Path

from DataHolder import DataHolder

import io
import base64

import interactions
from interactions import listen, slash_command, slash_option, OptionType, SlashContext
from interactions.api.events import MessageReactionAdd, MessageCreate
from interactions.models.discord import Message

BOT_NAME = "DaleBot"

load_dotenv()
DISCORD_TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
USERNAME = os.getenv("USER")
PASSWORD = os.getenv("PASS")
TRIGGER = "!dale"  # default value
SDXL = False  # default value

# bot = discord.Client(intents=discord.Intents.all())
ibot = interactions.Client(intents=interactions.Intents.ALL, debug_scope=GUILD_ID)

url = 'http://127.0.0.1:7860'

log = True

helpstring = "Hi! For a simple request, you can type something like \"!dale firetruck\"\n" \
             "More complicated requests have the following options:\n\n" \
             "conform=1-30, describes how much the AI should conform to the prompt. Defaults to 7\n" \
             "num=1-16, describes how many pictures to generate. Defaults to 1\n" \
             "steps=1-100, describes how many times the ai should run over the picture. Defaults to 30\n" \
             "res=1-1600x1-1600, describes the resolution of the image. Defaults to 1024x1024\n" \
             "dn=0-1, describes the denoising amount when generating based off an existing image. Higher means more " \
             "changes. Defaults to 0.75\n" \
             "seed=0-very large number, describes the seed from which to begin generation. the same prompt with the " \
             "same seed will generate the same image.\n" \
             "\tseed is useful for making slight modifications to an image that you think is close to what you want\n" \
             "sampler=\"Euler a\", describes the sampling method to use. there are a lot, so type sampler=help to " \
             "get a full list\n" \
             "{exclude this}, use curly braces to define words that you want the AI to exclude during generation\n\n" \
             "Higher numbers for num and steps mean longer generation times.\n" \
             "Click the die emote on my messages to reroll the same prompt with a different seed.\n" \
             "Respond to my messages with \"!dale extra words\" to include extra words in a previous prompt.\n" \
             "Example of a complicated request (will take a couple minutes to reply. only works if a style name " \
             "\"cartoon\" has been set; remove that parameter otherwise):\n" \
             "!dale firetruck conform=20 num=4 steps=15 res=832x256 sampler=\"DPM2 a Karras\" {birds} " \
             "style1=\"cartoon\" "

# data_holder = DataHolder()
s = requests.Session()

queue = []
iss = None

@listen(interactions.api.events.Startup)
async def on_startup():
    global s, helpstring
    if json.loads(s.get(url + '/config').content).get("detail") == "Not authenticated":
        headers = {"Connection": "keep-alive", "Host": "127.0.0.1:7860"}
        payload = {'username': USERNAME, 'password': PASSWORD}

        res = s.post(url + '/login', headers=headers, data=payload)
        try:
            if json.loads(res.content).get("detail") == "Incorrect credentials.":
                print("Incorrect credentials. Please make sure the user and pass in .env match the user and pass given "
                      "after --gradio-auth")
                os._exit(1)
        except Exception:
            pass

    load_config()
    helpstring = helpstring.replace("!dale", TRIGGER)

    Path("log").mkdir(parents=True, exist_ok=True)
    print(f'{ibot.user} has logged in.')

    await load_available_settings()


# reacting to a dalepost with "🎲" will prompt dale to reroll the prompt with a different seed
@listen(MessageReactionAdd)
async def on_message_reaction_add(event: MessageReactionAdd):
    data_holder = DataHolder(iss)
    message = event.message
    emoji = event.emoji
    author = event.author
    if author == ibot.user:
        return
    if message.author == ibot.user:
        if emoji.name == "🎲":
            await message.add_reaction("🔄")
            parent_message = await message.channel.fetch_message(message.message_reference.message_id)
            await handle_message(parent_message)
            await message.remove_reaction("🔄", ibot.user)
            await message.add_reaction("✅")

        if emoji.name == "🔎":
            await message.add_reaction("🔄")
            data_holder.setup('')
            data_holder.is_upscale = True
            await data_holder.add_attachment(message.attachments[0].url)
            await data_holder.wordparse()
            await postresponse(data_holder, message)
            await message.remove_reaction("🔄", ibot.user)
            await message.add_reaction("✅")

        if emoji.name == "🪩":
            await message.add_reaction("🔄")
            parent_message = await message.channel.fetch_message(message.message_reference.message_id)
            original_text = await get_original_message_text(parent_message)
            data_holder.setup(original_text[len(TRIGGER) + 1:])
            data_holder.is_disco = True
            await data_holder.wordparse()
            await postresponse(data_holder, message)
            await message.remove_reaction("🔄", ibot.user)
            await message.add_reaction("✅")

        if emoji.name == "🖼️":
            await message.add_reaction("🔄")
            parent_message = await message.channel.fetch_message(message.message_reference.message_id)
            original_text = await get_original_message_text(parent_message)
            data_holder.setup(original_text[len(TRIGGER) + 1:])
            await data_holder.add_attachment(message.attachments[0].url)
            data_holder.is_disco = True
            await data_holder.wordparse()
            await postresponse(data_holder, message)
            await message.remove_reaction("🔄", ibot.user)
            await message.add_reaction("✅")


async def get_original_message_text(message: Message):
    if message.message_reference is not None:
        return await get_original_message_text(await message.channel.fetch_message(message.message_reference.message_id))
    return message.content


# include prompts from the parent messages in the current prompt
async def get_all_parent_contents(data_holder: DataHolder, message: Message):
    if message.content[0:len(TRIGGER)] == TRIGGER:
        data_holder.reply_string = " " + message.content[len(TRIGGER) + 1:] + " " + data_holder.reply_string

    # recursively get prompts from all parent messages in this reply chain
    if message.message_reference is not None:
        await get_all_parent_contents(data_holder, await message.channel.fetch_message(message.message_reference.message_id))


@listen(MessageCreate)
async def on_message(event: MessageCreate):
    await handle_message(event.message)


async def handle_message(message: Message):
    print(f'Message received: {message.content}')
    data_holder = DataHolder(iss)

    # ignore messages from the bot
    if message.author == ibot.user:
        return

    if message.content == '!d styles':
        await message.reply(data_holder.list_styles())

    if message.content == '!d loras':
        await message.reply(data_holder.list_loras())

    if message.content[0:len(TRIGGER)] == TRIGGER:
        # get previous prompts if this message is a response to another message
        if message.message_reference is not None:
            await get_all_parent_contents(await message.channel.fetch_message(message.message_reference.message_id))

        await message.add_reaction("🔄")
        await ibot.change_presence(activity='🎨')

        # set the default indices in case the previous prompt wasn't default
        data_holder.setup(message.content[len(TRIGGER) + 1:])

        if len(message.attachments) > 0:
            await data_holder.add_attachment(message.attachments[0].url)

        await data_holder.wordparse()

        await postresponse(data_holder, message)

        await message.remove_reaction("🔄", ibot.user)
        await message.add_reaction("✅")

        await ibot.change_presence(activity=None)

        if (len(message.content[len(TRIGGER) + 1:].split()) > 0
                and "help" in message.content[len(TRIGGER) + 1:].split()[0]):
            await message.channel.send(helpstring)


# sends post_obj to the AI, gets a response,
# pulls the seed (if it exists) and the imgdata string from the response
# responds to the message with the new image and the seed (if it exists)
async def postresponse(data_holder: DataHolder, message):
    printable_po = copy.deepcopy(data_holder.post_obj)
    if 'image' in printable_po:
        printable_po.pop('image')
    if 'init_images' in printable_po:
        printable_po.pop('init_images')
    print(printable_po)
    global s
    if log:
        with open("log/post_obj.json", "w") as f:
            f.write(json.dumps(data_holder.post_obj, indent=2))
    r_json = s.post(url + data_holder.endpoint, json=data_holder.post_obj, timeout=300).json()
    if log:
        with open("log/responsejson.json", "w") as f:
            f.write(json.dumps(r_json, indent=2))

    try:
        if 'images' in r_json:
            seed = json.loads(r_json['info']).get('seed', 0)
            with io.BytesIO(base64.b64decode(r_json['images'][0])) as img_bytes:
                pic = interactions.models.discord.File(img_bytes, 'dale.png')
                reply_text = data_holder.info + f'\nseed={str(seed)}'
                replied_message = await message.reply(reply_text, file=pic)
            await replied_message.add_reaction("🎲")
            await replied_message.add_reaction("🔎")
            await replied_message.add_reaction("🪩")
            await replied_message.add_reaction("🖼️")
        elif 'image' in r_json:
            with io.BytesIO(base64.b64decode(r_json['image'])) as img_bytes:
                pic = interactions.models.discord.File(img_bytes, 'dale.png')
                await message.reply(file=pic)
        else:
            with io.BytesIO(base64.b64decode(r_json['images'][0])) as img_bytes:
                pic = interactions.models.discord.File(img_bytes, 'dale.png')
                await message.reply(file=pic)
    except Exception as e:
        await message.remove_reaction("🔄", ibot.user)
        await message.add_reaction("❌")
        print(type(e))
        print(e)
        return


# tons of duplicate code for quick txt2img slash command test
@slash_command(name="dale", description="generate an image", nsfw=True)
@slash_option(
    name="prompt",
    description="description of your image",
    required=True,
    opt_type=OptionType.STRING
)
@slash_option(
    name="image",
    description="image for img2img",
    opt_type=OptionType.ATTACHMENT
)
async def txt2img(ctx: SlashContext, prompt: str, attachment: interactions.models.Attachment = None):
    try:
        global s
        data_holder = DataHolder(iss)
        data_holder.setup(prompt)

        if attachment:
            await data_holder.add_attachment(attachment.url)

        await data_holder.wordparse()
        await ctx.defer()

        if log:
            with open("log/post_obj.json", "w") as f:
                f.write(json.dumps(data_holder.post_obj, indent=2))
        r_json = s.post(url + data_holder.endpoint, json=data_holder.post_obj, timeout=300).json()
        if log:
            with open("log/responsejson.json", "w") as f:
                f.write(json.dumps(r_json, indent=2))

        with io.BytesIO(base64.b64decode(r_json['images'][0])) as img_bytes:
            pic = interactions.models.discord.File(img_bytes, 'dale.png')
            await ctx.send(content="dale is here", file=pic)
    except Exception as e:
        print("error", e)


async def submit_request():
    pass


# retrieves loras, styles, and samplers
async def load_available_settings():
    global s, iss
    loras = s.get(url + '/sdapi/v1/loras').json()
    styles = s.get(url + '/sdapi/v1/prompt-styles').json()
    samplers = s.get(url + '/sdapi/v1/samplers').json()
    loaded_settings = {}
    try:
        with open('install_specific_settings.json') as f:
            loaded_settings = json.load(f)
    except Exception as e:
        print("Error loading install specific settings: ", e)

    iss = (loras, styles, samplers, loaded_settings)

    # data_holder.set_available_options(loras, styles, samplers, loaded_settings)


def load_config():
    global TRIGGER, SDXL
    vals = {}
    try:
        with open('config.json') as f:
            vals = json.load(f)
    except Exception as e:
        print("Error loading config values: ", e)
    TRIGGER = vals['trigger']
    SDXL = vals['sdxl']


ibot.start(DISCORD_TOKEN)
