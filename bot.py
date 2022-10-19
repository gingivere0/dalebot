import discord
import os
from dotenv import load_dotenv
import requests
import json
from pathlib import Path

import PayloadFormatter
from DataHolder import DataHolder

BOT_NAME = "DaleBot"

load_dotenv()
DISCORD_TOKEN = os.getenv("TOKEN")
USERNAME = os.getenv("USER")
PASSWORD = os.getenv("PASS")

bot = discord.Client(intents=discord.Intents.all())

url = "http://127.0.0.1:7860/api/predict"

helpstring = "Hi! For a simple request, you can type something like \"!dale firetruck\"\n" \
             "More complicated requests have the following options:\n\n" \
             "conform=1-30, describes how much the AI should conform to the prompt. Defaults to 7\n" \
             "num=1-16, describes how many pictures to generate. Defaults to 1\n" \
             "samples=1-100, describes how many times the ai should run over the picture. Defaults to 20\n" \
             "res=1-1600x1-1600, describes the resolution of the image. Defaults to 512x512\n" \
             "dn=0-1, describes the denoising amount when generating based off an existing image. Higher means more " \
             "changes. Defaults to 0.45\n" \
             "seed=0-very large number, describes the seed from which to begin generation. the same prompt with the " \
             "same seed will generate the same image.\n" \
             "\tseed is useful for making slight modifications to an image that you think is close to what you want\n" \
             "sampler=\"Euler a\", describes the sampling method to use. there are a lot, so type sampler=help to " \
             "get a full list\n" \
             "{exclude this}, use curly braces to define words that you want the AI to exclude during generation\n\n" \
             "Higher numbers for num and samples mean longer generation times.\n" \
             "Click the die emote on my messages to reroll the same prompt with a different seed.\n" \
             "Respond to my messages with \"!dale extra words\" to include extra words in a previous prompt.\n" \
             "Example of a complicated request (will take a couple minutes to reply):\n" \
             "!dale firetruck conform=20 num=4 samples=15 res=832x256 sampler=\"DPM2 a Karras\" {birds}"

data_holder = DataHolder()
s = requests.Session()


@bot.event
async def on_ready():
    global s
    if json.loads(s.get("http://127.0.0.1:7860/config").content).get("detail") == "Not authenticated":
        headers = {"Connection": "keep-alive", "Host": "127.0.0.1:7860"}
        payload = {'username': USERNAME, 'password': PASSWORD}

        res = s.post('http://127.0.0.1:7860/login', headers=headers, data=payload)
        try:
            if json.loads(res.content).get("detail") == "Incorrect credentials.":
                print("Incorrect credentials. Please make sure the user and pass in .env match the user and pass given "
                      "after --gradio-auth")
                os._exit(1)
        except Exception:
            pass
    PayloadFormatter.setup(s)

    Path("log").mkdir(parents=True, exist_ok=True)
    print(f'{bot.user} has logged in.')


# reacting to a dalepost with "🎲" will prompt dale to reroll the prompt with a different seed
@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return
    if reaction.message.author == bot.user:
        if reaction.emoji == "🎲":
            await reaction.message.add_reaction("🔄")
            parent_message = await reaction.message.channel.fetch_message(reaction.message.reference.message_id)
            await on_message(parent_message)
            await reaction.message.remove_reaction("🔄", bot.user)
            await reaction.message.add_reaction("✅")


# include prompts from the parent messages in the current prompt
async def get_all_parent_contents(message):
    if message.content[0:5] == "!dale":
        data_holder.reply_string = " " + message.content[6:] + " " + data_holder.reply_string

    # recursively get prompts from all parent messages in this reply chain
    if message.reference is not None:
        await get_all_parent_contents(await message.channel.fetch_message(message.reference.message_id))


@bot.event
async def on_message(message):
    # post_obj['data'][4] = 20
    # post_obj['data'][8] = 1
    # post_obj['data'][10] = 10
    # post_obj['data'][16] = 512
    # post_obj['data'][17] = 512

    print(f'Message received: {message.content}')

    # ignore messages from the bot
    if message.author == bot.user:
        return

    if message.content[0:5] == "!dale":

        # get previous prompts if this message is a response to another message
        if message.reference is not None:
            await get_all_parent_contents(await message.channel.fetch_message(message.reference.message_id))

        await message.add_reaction("🔄")

        await bot.change_presence(activity=discord.Game('with myself: ' + message.content))

        # set the default indices in case the previous prompt wasn't default
        data_holder.setup(message)

        # messages with attachments have different post_obj formats
        # if the message is an upscale or img2img, format post_obj accordingly
        is_upscale = False
        if len(message.attachments) > 0:
            is_upscale = await data_holder.messageattachments(message)
        else:
            f = open('data.json')
            data_holder.post_obj = json.load(f)
            f.close()

        if not is_upscale:
            await data_holder.wordparse(message)

        await postresponse(message)

        await message.remove_reaction("🔄", bot.user)
        await message.add_reaction("✅")

        await bot.change_presence(activity=None)

        if len(message.content[6:].split()) > 0 and "help" in message.content[6:].split()[0]:
            await message.channel.send(helpstring)


# sends post_obj to the AI, gets a response,
# pulls the seed (if it exists) and the imgdata string from the response
# responds to the message with the new image and the seed (if it exists)
async def postresponse(message):
    global s
    with open("log/post_obj.json", "w") as f:
        f.write(json.dumps(data_holder.post_obj, indent=2))
    response = s.post(url, json=data_holder.post_obj, timeout=60)
    responsestr = json.dumps(response.json(), indent=2)
    with open("log/responsejson.json", "w") as f:
        f.write(responsestr)
    seed = ""
    if "Seed:" in responsestr:
        seed = responsestr.split("Seed:", 1)[-1].split()[0][:-1]

    # loops an image back into the AI
    # if data_holder.num_loops.isnumeric() and int(data_holder.num_loops) > 1:
    #     if int(data_holder.num_loops) > 15:
    #         data_holder.num_loops = "15"
    #     for x in range(0, int(data_holder.num_loops) - 1):
    #         # if the original message doesn't have an attachment, we have to run the setup on the post_obj
    #         if len(message.attachments) == 0:
    #             message.attachments = [1]
    #             convertpng2txtfile(imgdata)
    #             data_holder.attachedjsonframework()
    #             await data_holder.wordparse(message)
    #         with open("attachment.txt", "r") as textfile:
    #             data_holder.post_obj['data'][4] = "data:image/png;base64," + textfile.read()
    #         data_holder.post_obj['data'][data_holder.prompt_ind] = data_holder.prompt_no_args
    #         response = requests.post(url, json=data_holder.post_obj)
    #         responsestr = json.dumps(response.json())
    #         seed = ""
    #         if "Seed:" in responsestr:
    #             seed = responsestr.split("Seed:", 1)[-1].split()[0][:-1]
    #         imgdata = base64.b64decode(response.json()['data'][0][0][22:])
    #         filename = "testimg.png"
    #         with open(filename, "wb") as f:
    #             f.write(imgdata)

    try:
        picture = discord.File(response.json()['data'][0][0]['name'])
    except Exception:
        await message.remove_reaction("🔄", bot.user)
        await message.add_reaction("❌")
        return
    if len(seed) > 0:
        await (await message.reply("seed=" + seed, file=picture)).add_reaction("🎲")
    else:
        await message.reply(file=picture)

bot.run(DISCORD_TOKEN)
