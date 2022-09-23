import discord
import os
from dotenv import load_dotenv
import requests
import json
import base64
import urllib.request
from PIL import Image

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
             "dn=0-1, describes the denoising amount when generating based off an existing image. Higher means more " \
             "changes. Defaults to 0.45\n" \
             "seed=0-very large number, describes the seed from which to begin generation. the same prompt with the " \
             "same seed will generate the same image.\n" \
             "\tseed is useful for making slight modifications to an image that you think is close to what you want\n" \
             "{exclude this}, use curly braces to define words that you want the AI to exclude during generation\n\n" \
             "Higher numbers for num and samples mean longer generation times.\n" \
             "Example of a complicated request:\n" \
             "!dale firetruck conform=20 num=4 samples=35 res=832x256 {birds}"

prompt_no_args = ""
original_prompt = ""
words = ""
postObj = None
sampleind = 4
numind = 8
conformind = 10
resxind = 17
resyind = 16
seedind = 11
dataind = 0
numloops = ""
gotloops = False
denoiseBool = False


@bot.event
async def on_ready():
    print(f'{bot.user} has logged in.')


@bot.event
async def on_message(message):
    global postObj
    # postObj['data'][4] = 20
    # postObj['data'][8] = 1
    # postObj['data'][10] = 10
    # postObj['data'][16] = 512
    # postObj['data'][17] = 512

    print('message received: ' + f'{message.content}')

    # ignore messages from the bot
    if message.author == bot.user:
        return

    if message.content[0:5] == "!dale":
        await message.add_reaction("🔄")

        setup(message)

        if len(message.attachments) > 0:
            await messageattachments(message)

        else:
            f = open('data.json')
            postObj = json.load(f)
            f.close()

        await wordparse(message)

        await postresponse(message)

        await message.remove_reaction("🔄", bot.user)
        await message.add_reaction("✅")

        if "help" in message.content[6:].split()[0]:
            await message.channel.send(helpstring)


# reset default variables for a normal word prompt
def setup(message):
    global prompt_no_args, original_prompt, words, postObj, sampleind, numind, conformind, resxind, resyind, seedind, denoiseBool, numloops
    original_prompt = message.content[6:]
    prompt_no_args = message.content[6:]
    words = original_prompt.split()
    sampleind = 4
    numind = 8
    conformind = 10
    resxind = 17
    resyind = 16
    seedind = 11
    numloops = ""
    denoiseBool = False


# attachments can either be upscales or part of a prompt
async def messageattachments(message):
    global prompt_no_args, words, postObj, sampleind, numind, conformind, resxind, resyind, seedind, denoiseBool, numloops

    # write attachment to file as image, then read image from file and write to as base64encoded bytes
    with open("output.png", "wb") as imgfile:
        imgfile.write(requests.get(message.attachments[0].url).content)
    encodedattachment = base64.b64encode(open("output.png", "rb").read())
    if os.path.exists("output.txt"):
        os.remove("output.txt")
    with open("output.txt", "wb") as textfile:
        textfile.write(encodedattachment)

    if len(words) >= 1 and words[0] == "upscale":
        await upscale(message)
        return

    attachedjsonframework()


def attachedjsonframework():
    global prompt_no_args, words, postObj, sampleind, numind, conformind, resxind, resyind, seedind, denoiseBool, numloops
    # open postObj template for image prompts
    f = open('imgdata.json')
    postObj = json.load(f)
    f.close()

    with open("output.txt", "r") as textfile:
        postObj['data'][4] = "data:image/png;base64," + textfile.read()

    # assign variable indices for image prompt json format
    sampleind = 8
    numind = 15
    conformind = 17
    resxind = 25
    resyind = 24
    seedind = 19
    denoiseBool = True

    # get the resolution of the original image, make the new image have the same resolution, adjusted to closest 64
    img = Image.open("output.png")

    postObj['data'][resxind] = nearest64(img.size[0])
    postObj['data'][resyind] = nearest64(img.size[1])


async def wordparse(message):
    global words, original_prompt, prompt_no_args, numloops, postObj, gotloops

    for word in words:
        if 'samples=' in word:
            samples = word.split("=")[1]
            if samples.isnumeric() and int(samples) <= 100:
                postObj['data'][sampleind] = int(samples)
            prompt_no_args = prompt_no_args.replace(word, "")

        if 'num=' in word:
            numpics = word.split("=")[1]
            if numpics.isnumeric() and int(numpics) < 17:
                postObj['data'][numind] = int(numpics)
            prompt_no_args = prompt_no_args.replace(word, "")

        if 'conform=' in word:
            conform = word.split("=")[1]
            if conform.isnumeric() and int(conform) <= 100:
                postObj['data'][conformind] = int(conform)
            prompt_no_args = prompt_no_args.replace(word, "")

        if 'res=' in word:
            resolution = word.split("=")[1]
            resx = resolution.split("x")[0]
            resy = resolution.split("x")[1]
            if resx.isnumeric() and resy.isnumeric() and int(resx) <= 1600 and int(resy) <= 1600:
                postObj['data'][resxind] = nearest64(int(resx))
                postObj['data'][resyind] = nearest64(int(resy))
            else:
                await message.channel.send(
                    "I am from the south and I'm really fucking stupid so I can't render images bigger than "
                    "1600x1600. Try using the upscaler (which doesn't exist yet)")
            prompt_no_args = prompt_no_args.replace(word, "")

        if 'dn=' in word:
            dn = word.split("=")[1]
            if float(dn) <= 1 and denoiseBool:
                postObj['data'][18] = float(dn)
            prompt_no_args = prompt_no_args.replace(word, "")

        if 'seed=' in word:
            seed = word.split("=")[1]
            postObj['data'][seedind] = int(seed)
            prompt_no_args = prompt_no_args.replace(word, "")

        if '{' in prompt_no_args and '}' in prompt_no_args and prompt_no_args.index('}') > prompt_no_args.index('{'):
            exclude = original_prompt.split('{', 1)[1].split('}', 1)[0]
            print(exclude)
            prompt_no_args = prompt_no_args.replace('{' + exclude + '}', "")
            postObj['data'][1] = exclude

        if 'loops=' in word:
            numloops = word.split("=")[1]
            prompt_no_args = prompt_no_args.replace(word, "")
            gotloops = True

    postObj['data'][0] = prompt_no_args
    print(prompt_no_args)


# asdf
async def upscale(message):
    # load the base json template for the upscale
    f = open('updata.json')
    global postObj
    postObj = json.load(f)
    f.close()

    with open("output.txt", "r") as textfile:
        postObj['data'][0] = "data:image/png;base64," + textfile.read()

    # upscale up to 10 times if an upscale factor is included
    if len(words) > 1 and words[1].isnumeric() and float(words[1]) <= 10:
        postObj['data'][5] = float(words[1])

    await postresponse(message)


# sends postObj to the AI, gets a response,
# pulls the seed (if it exists) and the imgdata string from the response
# responds to the message with the new image and the seed (if it exists)
async def postresponse(message):
    global postObj
    response = requests.post(url, json=postObj)
    responsestr = json.dumps(response.json())
    seed = ""
    if "Seed:" in responsestr:
        seed = responsestr.split("Seed:", 1)[-1].split()[0][:-1]
        print("seed:" + seed)
    imgdata = base64.b64decode(response.json()['data'][0][0][22:])
    filename = "testimg.png"
    with open(filename, "wb") as f:
        f.write(imgdata)

    # loops an image back into the AI
    if numloops.isnumeric() and int(numloops) > 1:
        for x in range(0, int(numloops)-1):
            if len(message.attachments) == 0:
                message.attachments = [1]
                with open("output.png", "wb") as imgfile:
                    imgfile.write(imgdata)
                encodedattachment = base64.b64encode(open("output.png", "rb").read())
                if os.path.exists("output.txt"):
                    os.remove("output.txt")
                with open("output.txt", "wb") as textfile:
                    textfile.write(encodedattachment)
                attachedjsonframework()
                await wordparse(message)
            with open("output.txt", "r") as textfile:
                postObj['data'][4] = "data:image/png;base64," + textfile.read()
            postObj['data'][0] = prompt_no_args
            with open("testout.txt", "w") as filefile:
                filefile.write(json.dumps(postObj))
            response = requests.post(url, json=postObj)
            responsestr = json.dumps(response.json())
            seed = ""
            if "Seed:" in responsestr:
                seed = responsestr.split("Seed:", 1)[-1].split()[0][:-1]
                print("seed:" + seed)
            imgdata = base64.b64decode(response.json()['data'][0][0][22:])
            filename = "testimg.png"
            with open(filename, "wb") as f:
                f.write(imgdata)

    with open(filename, 'rb') as f:
        picture = discord.File(f)
        if len(seed) > 0:
            await message.reply("seed=" + seed, file=picture)
        else:
            await message.reply(file=picture)


# rounds an integer to the nearest 64. useful for getting acceptable resolutions
def nearest64(integer):
    if integer % 64 > 32:
        integer += 64 - (integer % 64)
    else:
        integer -= (integer % 64)
    return integer


bot.run(DISCORD_TOKEN)
