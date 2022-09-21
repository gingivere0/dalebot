import discord
import os
from dotenv import load_dotenv
import requests
import json
import base64
import urllib.request


BOT_NAME = "DaleBot"

load_dotenv()
DISCORD_TOKEN = os.getenv("TOKEN")

bot = discord.Client(intents=discord.Intents.all())

url = "http://127.0.0.1:7860/api/predict"


helpstring = "Hi! For a simple request, you can type something like \"!dale firetruck\"\n" \
             "More complicated requests have the following options:\n\n" \
             "conform=1-30, describes how much the AI should conform to the prompt. Defaults to 7\n" \
             "num=1-16, describes how many pictures to generate. Defaults to 1\n" \
             "samples=1-100, describes how many times the ai should run over the picture. Defaults to 20\n" \
             "res=1-1600x1-1600, describes the resolution of the image. Defaults to 512x512\n" \
             "dn=0-1, describes the denoising amount when generating based off an existing image. Higher means more changes. Defaults to 0.65\n" \
             "seed=0-very large number, describes the seed from which to begin generation. the same prompt with the same seed will generate the same image.\n" \
             "\tseed is useful for making slight modifications to an image that you think is close to what you want\n" \
             "{exclude this}, use curly braces to define words that you want the AI to exclude during generation\n\n" \
             "Higher numbers for num and samples mean longer generation times.\n" \
             "Example of a complicated request:\n" \
             "!dale firetruck conform=20 num=4 samples=35 res=832x256 {birds}"

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in.')

@bot.event
async def on_message(message):
    # postObj['data'][4] = 20
    # postObj['data'][8] = 1
    # postObj['data'][10] = 10
    # postObj['data'][16] = 512
    # postObj['data'][17] = 512

    print('message received: '+f'{message.content}')
    if message.author == bot.user:
        return

    if message.content[0:5] =="!dale":
        await message.add_reaction("🔄")
        prompt = message.content[6:]
        words = prompt.split()
        postObj=""
        sampleind=4
        numind=8
        conformind=10
        resxind=16
        resyind=17
        seedind=11
        denoiseBool=False
        if len(message.attachments)>0:
            if len(words)>1 and words[0] == "upscale":
                f=open('updata.json')
                postObj = json.load(f)
                f.close()
                with open("output.png", "wb") as imgfile:
                    imgfile.write(requests.get(message.attachments[0].url).content)
                encodedattachment = base64.b64encode(open("output.png", "rb").read())
                if os.path.exists("output.txt"):
                    os.remove("output.txt")
                with open("output.txt", "wb") as textfile:
                    textfile.write(encodedattachment)
                with open("output.txt", "r") as textfile:
                    postObj['data'][0] = "data:image/png;base64," + textfile.read()
                if words[1].isnumeric() and float(words[1]) <= 10:
                    postObj['data'][5] = float(words[1])
                response = requests.post(url, json=postObj)
                # with open("outie.json","wb") as f:
                #     f.write(response.json())
                imgdata = base64.b64decode(response.json()['data'][0][0][22:])
                filename = "testimg.png"
                with open(filename, "wb") as f:
                    f.write(imgdata)
                with open(filename, 'rb') as f:
                    picture = discord.File(f)
                    await message.reply(file=picture)
                await message.add_reaction("🔄")
                await message.add_reaction("✅")
                return
            f = open('imgdata.json')
            postObj = json.load(f)
            f.close()
            with open("output.png","wb") as imgfile:
                imgfile.write(requests.get(message.attachments[0].url).content)
            encodedattachment = base64.b64encode(open("output.png", "rb").read())
            if os.path.exists("output.txt"):
                os.remove("output.txt")
            with open("output.txt", "wb") as textfile:
                textfile.write(encodedattachment)
            with open("output.txt", "r") as textfile:
                postObj['data'][4] = "data:image/png;base64,"+textfile.read()
            sampleind=8
            numind=15
            conformind=17
            resxind=24
            resyind=25
            denoiseBool=True

        else:
            f = open('data.json')
            postObj = json.load(f)
            f.close()

        for word in words:
            if 'samples=' in word:
                samples = word.split("=")[1]
                if samples.isnumeric() and int(samples) <= 100:
                    postObj['data'][sampleind] = int(samples)
                prompt = prompt.replace(word, "")
            if 'num=' in word:
                numpics = word.split("=")[1]
                if numpics.isnumeric() and int(numpics)<17:
                    postObj['data'][numind] = int(numpics)
                prompt = prompt.replace(word,"")
            if 'conform=' in word:
                conform = word.split("=")[1]
                if conform.isnumeric() and int(conform) <= 100:
                    postObj['data'][conformind] = int(conform)
                prompt = prompt.replace(word, "")
            if 'res=' in word:
                resolution = word.split("=")[1]
                resx = resolution.split("x")[1]
                resy = resolution.split("x")[0]
                if resx.isnumeric() and resy.isnumeric() and int(resx)<=1600 and int(resy)<=1600:
                    postObj['data'][resxind] = int(resx)
                    postObj['data'][resyind] = int(resy)
                else:
                    await message.channel.send("I am from the south and I'm really fucking stupid so I can't render images bigger than 1600x1600. Try using the upscaler (which doesn't exist yet)")
                prompt = prompt.replace(word, "")
            if 'dn=' in word:
                dn = word.split("=")[1]
                if float(dn) <= 1 and denoiseBool:
                    postObj['data'][18]=float(dn)
                prompt.replace(word,"")
            if 'seed=' in word:
                seed = word.split("=")[1]
                postObj['data'][seedind] = int(seed)
                prompt = prompt.replace(word, "")

        if '{' in prompt and '}' in prompt and prompt.index('}') > prompt.index('{'):
            exclude = prompt.split('{',1)[1].split('}',1)[0]
            print(exclude)
            prompt=prompt.replace('{'+exclude+'}',"")
            postObj['data'][1] = exclude
        print("prompt: "+prompt)
        postObj['data'][0] = prompt

        print("post object: "+json.dumps(postObj))
        response = requests.post(url, json=postObj)
        print("seed:" +json.dumps(response.json()).split("Seed:",1)[-1].split()[0][:-1])
        imgdata = base64.b64decode(response.json()['data'][0][0][22:])
        filename = "testimg.png"
        with open(filename, "wb") as f:
            f.write(imgdata)
        with open(filename, 'rb') as f:
            picture = discord.File(f)
            await message.reply("seed="+json.dumps(response.json()).split("Seed:",1)[-1].split()[0][:-1], file=picture)
        await message.add_reaction("🔄")
        await message.add_reaction("✅")
        if "help" in message.content[6:].split()[0]:
            await message.channel.send(helpstring)

    # if message.content == 'goodbye':
    #     await message.channel.send(f'Goodbye {message.author}')

bot.run(DISCORD_TOKEN)