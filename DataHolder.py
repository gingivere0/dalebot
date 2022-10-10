import sys
import os
import requests
import json
import base64
from PIL import Image


class DataHolder:
    def __init__(self):
        self.prompt_no_args = ""
        self.original_prompt = ""
        self.words = ""
        self.post_obj = None
        self.prompt_ind = 0
        self.sample_ind = 4
        self.num_ind = 8
        self.conform_ind = 10
        self.resx_ind = 18
        self.resy_ind = 17
        self.seed_ind = 11
        self.data_ind = 5
        self.num_loops = ""
        self.got_loops = False
        self.denoise_bool = False
        self.reply_string = ""
        self.original_message_id = -1
        self.exclude_ind = 1

    def setup(self, message):
        self.original_prompt = self.reply_string + message.content[6:]
        self.prompt_no_args = self.reply_string + message.content[6:]
        self.reply_string = ""
        self.words = self.original_prompt.split()
        self.prompt_ind = 0
        self.sample_ind = 4
        self.num_ind = 8
        self.conform_ind = 10
        self.resx_ind = 18
        self.resy_ind = 17
        self.seed_ind = 11
        self.num_loops = ""
        self.denoise_bool = False
        self.exclude_ind = 1

    # removes parameters from the prompt and parses them accordingly
    async def wordparse(self, message):

        for word in self.words:
            if 'samples=' in word:
                samples = word.split("=")[1]
                if samples.isnumeric() and int(samples) <= 100:
                    self.post_obj['data'][self.sample_ind] = int(samples)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'num=' in word:
                numpics = word.split("=")[1]
                if numpics.isnumeric() and int(numpics) < 17:
                    self.post_obj['data'][self.num_ind] = int(numpics)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'conform=' in word:
                conform = word.split("=")[1]
                if conform.isnumeric() and int(conform) <= 100:
                    self.post_obj['data'][self.conform_ind] = int(conform)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'res=' in word:
                resolution = word.split("=")[1]
                resx = resolution.split("x")[0]
                resy = resolution.split("x")[1]
                if resx.isnumeric() and resy.isnumeric() and int(resx) <= 1600 and int(resy) <= 1600:
                    self.post_obj['data'][self.resx_ind] = nearest64(int(resx))
                    self.post_obj['data'][self.resy_ind] = nearest64(int(resy))
                else:
                    await message.channel.send(
                        "I'm really stupid so I can't render images bigger than "
                        "1600x1600. Instead, try attaching an image and running !dale upscale")
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'dn=' in word:
                dn = word.split("=")[1]
                if float(dn) <= 1 and self.denoise_bool:
                    self.post_obj['data'][19] = float(dn)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'seed=' in word:
                seed = word.split("=")[1]

                self.post_obj['data'][self.seed_ind] = int(seed) if int(
                    seed) < sys.maxsize else sys.maxsize - 1
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if '{' in self.prompt_no_args and '}' in self.prompt_no_args and self.prompt_no_args.index(
                    '}') > self.prompt_no_args.index('{'):
                exclude = self.original_prompt.split('{', 1)[1].split('}', 1)[0]
                self.prompt_no_args = self.prompt_no_args.replace('{' + exclude + '}', "")
                self.post_obj['data'][self.exclude_ind] = exclude

            if 'loops=' in word:
                self.num_loops = word.split("=")[1]
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                self.got_loops = True

        self.post_obj['data'][self.prompt_ind] = self.prompt_no_args

    # attachments can either be upscales or part of a prompt
    # returns if is an is_upscale
    async def messageattachments(self, message):

        convertpng2txtfile(requests.get(message.attachments[0].url).content)

        if len(self.words) >= 1 and self.words[0] == "upscale":
            await self.upscalejson()
            return True

        self.attachedjsonframework()

        return False

    # the json object for using an image as a prompt is different from the json object for using just text.
    # this method is setting up the json object for when there is an image as a prompt
    def attachedjsonframework(self):
        # open post_obj template for image prompts
        f = open('imgdata.json')
        self.post_obj = json.load(f)
        f.close()

        self.prompt_ind = 1

        with open("output.txt", "r") as textfile:
            self.post_obj['data'][self.data_ind] = "data:image/png;base64," + textfile.read()

        # assign variable indices for image prompt json format
        self.sample_ind = 10
        self.num_ind = 16
        self.conform_ind = 18
        self.resx_ind = 27
        self.resy_ind = 26
        self.seed_ind = 20
        self.denoise_bool = True
        self.exclude_ind = 2

        # get the resolution of the original image, make the new image have the same resolution, adjusted to closest 64
        img = Image.open("output.png")

        self.post_obj['data'][self.resx_ind] = nearest64(img.size[0])
        self.post_obj['data'][self.resy_ind] = nearest64(img.size[1])

    # the json object for upscaling an image is different from the json object for generating an image.
    # this method sets up the json object for upscaling an image
    async def upscalejson(self):
        # load the base json template for the is_upscale
        f = open('updata.json')
        self.post_obj = json.load(f)
        f.close()

        with open("output.txt", "r") as textfile:
            self.post_obj['data'][1] = "data:image/png;base64," + textfile.read()
            # self.post_obj['data'][10] = "[\n\"data:image/png;base64," + textfile.read()+"\"\n]"

        with open("testout.txt", "w") as filefile:
            filefile.write(json.dumps(self.post_obj))
        # upscale up to 10 times if an is_upscale factor is included
        if len(self.words) > 1 and self.words[1].isnumeric() and float(self.words[1]) <= 10:
            self.post_obj['data'][6] = int(self.words[1])


# write attachment to file as image, then read image from file and write string to file as base64encoded bytes
# this is a function is a setup for later, as output.txt will be read from and passed as an image data string.
# there must be a better way to do this
def convertpng2txtfile(imgdata):

    if os.path.exists("output.png"):
        os.remove("output.png")
    with open("output.png", "wb") as imgfile:
        imgfile.write(imgdata)
    encodedattachment = base64.b64encode(open("output.png", "rb").read())
    if os.path.exists("output.txt"):
        os.remove("output.txt")
    with open("output.txt", "wb") as textfile:
        textfile.write(encodedattachment)


# rounds an integer to the nearest 64, with a min of 64. useful for getting acceptable resolutions
def nearest64(integer):
    if integer % 64 > 32:
        integer += 64 - (integer % 64)
    else:
        integer -= (integer % 64)
    if integer == 0:
        integer = 64
    return integer
