import discord
import os
from dotenv import load_dotenv
import requests
import json
import base64


BOT_NAME = "DaleBot"

load_dotenv()
DISCORD_TOKEN = os.getenv("TOKEN")

bot = discord.Client(intents=discord.Intents.all())

url = "http://127.0.0.1:7860/api/predict"
f = open('data.json')
postObj = json.load(f)

helpstring = "Hi! For a simple request, you can type something like \"!dale firetruck\"\n" \
             "More complicated requests have the following options:\n\n" \
             "conform=1-30, describes how much the AI should conform to the prompt. Defaults to 10\n" \
             "num=1-16, describes how many pictures to generate. Defaults to 1\n" \
             "samples=1-100, describes how many times the ai should run over the picture. Defaults to 20\n" \
             "res=1-1600x1-1600, describes the resolution of the image. Defaults to 512x512\n\n" \
             "Higher numbers for all of these mean longer generation times.\n" \
             "Example of a complicated request:\n" \
             "!dale firetruck conform=20 num=4 samples=35 res=600x700"

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in.')

@bot.event
async def on_message(message):
    postObj['data'][4] = 20
    postObj['data'][8] = 1
    postObj['data'][10] = 10
    postObj['data'][16] = 512
    postObj['data'][17] = 512

    print('message received: '+f'{message.content}')
    if message.author == bot.user:
        return

    if message.content[0:5] =="!dale":
        await message.add_reaction("🔄")
        prompt = message.content[6:]
        words = prompt.split()
        for word in words:
            if 'samples=' in word:
                samples = word.split("=")[1]
                if (samples.isnumeric() and int(samples) <= 100):
                    postObj['data'][4] = int(samples)
            if 'num=' in word:
                numpics = word.split("=")[1]
                if(numpics.isnumeric() and int(numpics)<17):
                    postObj['data'][8] = int(numpics)
                prompt.replace(word,"")
            if 'conform=' in word:
                conform = word.split("=")[1]
                if (conform.isnumeric() and int(conform) <= 100):
                    postObj['data'][10] = int(conform)
                prompt.replace(word, "")
            if 'res=' in word:
                resolution = word.split("=")[1]
                resx = resolution.split("x")[0]
                resy = resolution.split("x")[1]
                if (resx.isnumeric() and resy.isnumeric() and int(resx)<=1600 and int(resy)<=1600):
                    postObj['data'][16] = int(resx)
                    postObj['data'][17] = int(resy)
                else:
                    await message.channel.send("I am from the south and I'm really fucking stupid so I can't render images bigger than 1600x1600. Try using the upscaler (which doesn't exist yet)")
                prompt.replace(word, "")
        # if words[-1].isnumeric():
        #     if(int(words[-1])<17):
        #         postObj['data'][8] = int(words[-1])
        #     prompt = prompt.rsplit(' ',1)[0]
        print(postObj['data'][8])
        print(prompt)
        postObj['data'][0] = prompt
        print(postObj)
        response = requests.post(url, json=postObj)
        imgdata = base64.b64decode(response.json()['data'][0][0][22:])
        filename = "testimg.png"
        with open(filename, "wb") as f:
            f.write(imgdata)
        with open(filename, 'rb') as f:
            picture = discord.File(f)
            await message.channel.send(file=picture)
        await message.add_reaction("🔄")
        await message.add_reaction("✅")
        if "help" in message.content[6:].split()[0]:
            await message.channel.send(helpstring)

    # if message.content == 'goodbye':
    #     await message.channel.send(f'Goodbye {message.author}')

bot.run(DISCORD_TOKEN)