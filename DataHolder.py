import sys
import os
import requests
import json
import base64
from PIL import Image
import shlex

import PayloadFormatter


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
        self.num_loop = ""
        self.denoise_bool = False
        self.reply_string = ""
        self.original_message_id = -1
        self.exclude_ind = 1
        self.denoise_ind = 19
        self.resize_ind = 6
        self.script_ind = 35
        self.loop_ind = 42
        self.is_looping = False
        self.sampling_methods = []
        self.sampling_methods_ind = 5
        self.style1_ind = 3
        self.style2_ind = 4
        self.style_names = []
        self.model_names = []
        self.is_model_change = False
        self.is_upscale = False

    def setup(self, message):
        self.reply_string = ""
        self.original_prompt = self.reply_string + message.content[6:]
        self.prompt_no_args = self.reply_string + message.content[6:]
        # split on spaces, removes quotes
        # put the quotes back in because I didn't want them gone. I couldn't find a better way to do this
        # for i in range(0, len(self.words)):
        #     if "=" in self.words[i] and " " in self.words[i]:
        #         equalsind = self.words[i].index("=")
        #         self.words[i] = self.words[i][:equalsind + 1] + '"' + self.words[i][equalsind + 1:] + '"'
        tempString = self.original_prompt
        if "=\"" in tempString:
            equalsind = tempString.index("=\"")
            tempString = tempString[:equalsind + 1] + " " + tempString[equalsind + 1:]

        self.words = new_split(tempString)
        for i in range(0, len(self.words)):
            if i >= len(self.words):
                break
            if self.words[i][-1] == "=" and i + 1 <= len(self.words):
                self.words[i] += self.words[i + 1]
                del self.words[i + 1]
        self.num_loop = ""
        self.denoise_bool = False
        self.is_looping = False
        self.is_model_change = False
        self.is_upscale = False

        # self.prompt_ind = 0
        # self.sample_ind = 4
        # self.num_ind = 8
        # self.conform_ind = 10
        # self.resx_ind = 18
        # self.resy_ind = 17
        # self.seed_ind = 11
        # self.exclude_ind = 1
        # self.denoise_ind = 19

        # PayloadFormatter.do_format(self, PayloadFormatter.PayloadFormat.TXT2IMG)

    # removes parameters from the prompt and parses them accordingly
    async def wordparse(self, message):
        for word in self.words:
            if 'model=' in word:
                # PayloadFormatter.do_format(self, PayloadFormatter.PayloadFormat.MODELCHANGE)
                with open('modelchange.json') as f:
                    self.post_obj = json.load(f)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                # shlex pre-removed the quotation marks, which i don't want, so i'm adding them back in so
                # i can remove the word from prompt_no_args
                equalsind = word.index('=')
                word = word[:equalsind + 1] + '"' + word[equalsind + 1:] + '"'
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                model = word.split("=")[1]
                # remove quotation marks
                model = model.replace('"', '')
                self.is_model_change = True
                for default_model in self.model_names:
                    if default_model.lower().split(" [")[0] == model.lower() or default_model.lower() == model.lower():
                        self.post_obj['data'][0] = model
                        return
                await message.reply(
                    "Model name \"" + model + "\" not found. Please make sure "
                                              "model name matches one of: \n" + ", ".join(self.model_names))
                return

            if 'hd=' in word:
                hd = word.split("=")[1]
                if hd.isnumeric() and int(hd) <= 100:
                    self.post_obj['enable_hr'] = int(hd)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'samples=' in word:
                samples = word.split("=")[1]
                if samples.isnumeric() and int(samples) <= 100:
                    self.post_obj['steps'] = int(samples)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'num=' in word:
                numpics = word.split("=")[1]
                if numpics.isnumeric() and int(numpics) < 17:
                    self.post_obj['batch_size'] = int(numpics)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'conform=' in word:
                conform = word.split("=")[1]
                if conform.isnumeric() and int(conform) <= 100:
                    self.post_obj['cfg_scale']= int(conform)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'res=' in word:
                resolution = word.split("=")[1]
                resx = resolution.split("x")[0]
                resy = resolution.split("x")[1]
                if resx.isnumeric() and resy.isnumeric() and int(resx) <= 1600 and int(resy) <= 1600:
                    self.post_obj['width'] = nearest64(int(resx))
                    self.post_obj['height'] = nearest64(int(resy))
                else:
                    await message.reply(
                        "I'm really stupid so I can't render images bigger than "
                        "1600x1600. Instead, try attaching an image and running !dale upscale")
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'dn=' in word:
                dn = word.split("=")[1]
                if float(dn) <= 1 and self.denoise_bool:
                    self.post_obj['denoising_strength'] = float(dn)
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if 'seed=' in word:
                seed = word.split("=")[1]
                self.post_obj['seed'] = int(seed) if int(
                    seed) < sys.maxsize else sys.maxsize - 1
                self.prompt_no_args = self.prompt_no_args.replace(word, "")

            if '{' in self.prompt_no_args and '}' in self.prompt_no_args and self.prompt_no_args.index(
                    '}') > self.prompt_no_args.index('{'):
                exclude = self.original_prompt.split('{', 1)[1].split('}', 1)[0]
                self.prompt_no_args = self.prompt_no_args.replace('{' + exclude + '}', "")
                self.post_obj['negative_prompt']= exclude

            if 'loops=' in word:
                self.num_loop = word.split("=")[1]
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                if len(message.attachments) > 0:
                    self.post_obj['data'][self.script_ind] = "Loopback"
                    self.post_obj['data'][self.loop_ind] = int(self.num_loop)
                # self.is_looping = True

            if 'sampler=' in word:
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                # shlex pre-removed the quotation marks, which i don't want, so i'm adding them back in so
                # i can remove the word from prompt_no_args
                equalsind = word.index('=')
                word = word[:equalsind+1]+'"'+word[equalsind+1:]+'"'
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                sampler = word.split("=")[1]
                # remove quotation marks
                sampler = sampler.replace('"', '')
                for default_sampler in self.sampling_methods:
                    if default_sampler.lower() == sampler.lower():
                        self.post_obj['hr_sampler_name'] = default_sampler
                        break
                if sampler.lower() not in map(str.lower, self.sampling_methods):
                    await message.reply("Sampling method not found. Defaulting to \"Euler a\". Please make sure "
                                        "sampler matches one of: \n" + ", ".join(self.sampling_methods))

            if 'style1=' in word:
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                # shlex pre-removed the quotation marks, which i don't want, so i'm adding them back in so
                # i can remove the word from prompt_no_args
                equalsind = word.index('=')
                word = word[:equalsind + 1] + '"' + word[equalsind + 1:] + '"'
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                style = word.split("=")[1]
                # remove quotation marks
                style = style.replace('"', '')
                for default_style in self.style_names:
                    if default_style.lower() == style.lower():
                        self.post_obj['styles'] = "["+default_style+"]"
                        break
                if style.lower() not in map(str.lower, self.style_names):
                    await message.reply("Style name \""+style+"\" not found. Ignoring this parameter. Please make sure "
                                        "style name matches one of: \n" + ", ".join(self.style_names))

            if 'style2=' in word:
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                # shlex pre-removed the quotation marks, which i don't want, so i'm adding them back in so
                # i can remove the word from prompt_no_args
                equalsind = word.index('=')
                word = word[:equalsind + 1] + '"' + word[equalsind + 1:] + '"'
                self.prompt_no_args = self.prompt_no_args.replace(word, "")
                style = word.split("=")[1]
                # remove quotation marks
                style = style.replace('"', '')
                for default_style in self.style_names:
                    if default_style.lower() == style.lower():
                        self.post_obj['data'][self.style2_ind] = default_style
                        break
                if style.lower() not in map(str.lower, self.style_names):
                    await message.reply("Style name \""+style+"\" not found. Ignoring this parameter. Please make sure "
                                        "style name matches one of: \n" + ", ".join(self.style_names))

        self.post_obj['prompt'] = self.prompt_no_args

    # attachments can either be upscales or part of a prompt
    # returns if is an is_upscale
    async def messageattachments(self, message):

        convertpng2txtfile(requests.get(message.attachments[0].url).content)

        if (len(self.words) >= 1 and self.words[0] == "upscale") or self.is_upscale:
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

        # PayloadFormatter.do_format(self, PayloadFormatter.PayloadFormat.IMG2IMG)

        with open("attachmentstring.txt", "r") as textfile:
            self.post_obj['data'][self.data_ind] = "data:image/png;base64," + textfile.read()

        # assign variable indices for image prompt json format
        # self.sample_ind = 10
        # self.num_ind = 16
        # self.conform_ind = 18
        # self.resx_ind = 27
        # self.resy_ind = 26
        # self.seed_ind = 20
        # self.exclude_ind = 2

        self.denoise_bool = True

        # get the resolution of the original image, make the new image have the same resolution, adjusted to closest 64
        img = Image.open("attachment.png")

        self.post_obj['data'][self.resx_ind] = nearest64(img.size[0])
        self.post_obj['data'][self.resy_ind] = nearest64(img.size[1])

    # the json object for upscaling an image is different from the json object for generating an image.
    # this method sets up the json object for upscaling an image
    async def upscalejson(self):
        # load the base json template for the is_upscale
        f = open('updata.json')
        self.post_obj = json.load(f)
        f.close()

        # PayloadFormatter.do_format(self, PayloadFormatter.PayloadFormat.UPSCALE)

        with open("attachmentstring.txt", "r") as textfile:
            self.post_obj['data'][self.data_ind] = "data:image/png;base64," + textfile.read()
            # self.post_obj['data'][10] = "[\n\"data:image/png;base64," + textfile.read()+"\"\n]"

        # upscale up to 10 times if an is_upscale factor is included
        if len(self.words) > 1 and self.words[1].isnumeric() and float(self.words[1]) <= 10:
            self.post_obj['data'][self.resize_ind] = int(self.words[1])


# write attachment to file as image, then read image from file and write string to file as base64encoded bytes
# this is a function is a setup for later, as attachment.txt will be read from and passed as an image data string.
# there must be a better way to do this
def convertpng2txtfile(imgdata):
    if os.path.exists("attachment.png"):
        os.remove("attachment.png")
    with open("attachment.png", "wb") as imgfile:
        imgfile.write(imgdata)
    encodedattachment = base64.b64encode(open("attachment.png", "rb").read())
    if os.path.exists("attachmentstring.txt"):
        os.remove("attachmentstring.txt")
    with open("attachmentstring.txt", "wb") as textfile:
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


def new_split(value):
    lex = shlex.shlex(value)
    lex.quotes = '"'
    lex.whitespace_split = True
    lex.commenters = ''
    return list(lex)
