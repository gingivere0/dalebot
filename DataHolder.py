import base64
import json
import os
import shlex
import sys
import re

import requests
from PIL import Image

SDXL_RES = ("1024x1024", "1152x896", "896x1152", "1216x832", "832x1216", "1344x768", "768x1344", "1536x640", "640x1536")


class DataHolder:
    def __init__(self):
        self.prompt = ""
        self.arguments = []
        self.prompt_no_args = ""
        self.original_prompt = ""
        self.words = ""
        self.post_obj = None
        self.num_loop = ""
        self.denoise_bool = False
        self.reply_string = ""
        self.is_looping = False
        self.sampling_methods = []
        self.style_names = []
        self.model_names = []
        self.is_model_change = False
        self.is_upscale = False

    def setup(self, message):
        self.reply_string = ""
        self.original_prompt = self.reply_string + message
        self.prompt_no_args = self.reply_string + message

        # find anything in curly braces (negative prompt)
        # split the message string (sans negative) into the prompt and a list of tuples
        # containing options (e.g. "res=") and parameters (e.g. "512x512")
        negatives = re.findall(r'({.+})', self.original_prompt)
        negative = "" if len(negatives) == 0 else negatives[0]
        fragments = re.split(r'\s\w+=', self.original_prompt.replace(negative, ""))
        options = re.findall(r'(\w+=)', self.original_prompt)
        self.prompt = fragments[0]
        self.arguments = list(zip(options, fragments[1:]))
        if negative != "":
            self.arguments.append(('negative=', negative[1:-1]))

        self.num_loop = ""
        self.denoise_bool = False
        self.is_looping = False
        self.is_model_change = False
        self.is_upscale = False

    # removes parameters from the prompt and parses them accordingly
    async def wordparse(self):
        self.post_obj['prompt'] = self.prompt
        self.post_obj['width'] = 1024
        self.post_obj['height'] = 1024
        self.post_obj['steps'] = 30
        self.post_obj['save_images'] = True
        for arg in self.arguments:
            if arg[0] == 'model=':
                print("change model")

            if arg[0] == 'hd=':
                hd = arg[1]
                if hd.isnumeric() and int(hd) <= 100:
                    self.post_obj['enable_hr'] = int(hd)

            if arg[0] == 'steps=':
                steps = arg[1]
                if steps.isnumeric() and int(steps) <= 100:
                    self.post_obj['steps'] = int(steps)

            if arg[0] == 'num=':
                numpics = arg[1]
                if numpics.isnumeric() and int(numpics) < 17:
                    self.post_obj['batch_size'] = int(numpics)

            if arg[0] == 'conform=':
                conform = arg[1]
                if conform.isnumeric() and int(conform) <= 100:
                    self.post_obj['cfg_scale'] = int(conform)

            if arg[0] == 'res=':
                resolution = arg[1]
                resx = resolution.split("x")[0]
                resy = resolution.split("x")[1]
                closest_resolution = nearest_sdxl(resx, resy)
                self.post_obj['width'] = closest_resolution[0]
                self.post_obj['height'] = closest_resolution[1]

            if arg[0] == 'dn=':
                dn = arg[1]
                if float(dn) <= 1 and self.denoise_bool:
                    self.post_obj['denoising_strength'] = float(dn)

            if arg[0] == 'seed=':
                seed = arg[1]
                self.post_obj['seed'] = int(seed) if int(
                    seed) < sys.maxsize else sys.maxsize - 1

            if arg[0] == 'negative=':
                exclude = arg[1]
                self.post_obj['negative_prompt'] = exclude

            if arg[0] == 'sr=':
                # absolutely wretched
                self.post_obj['script_name'] = 'x/y/z plot'
                self.post_obj['script_args'] = [7, arg[1][1:-1], '',
                                                0, '', '',
                                                0, '', '',
                                                True, False,
                                                False, False, 0]

    # removes parameters from the prompt and parses them accordingly
    async def wordparseX(self, message):
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
                word = word[:equalsind + 1] + '"' + word[equalsind + 1:] + '"'
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
                        self.post_obj['styles'] = "[" + default_style + "]"
                        break
                if style.lower() not in map(str.lower, self.style_names):
                    await message.reply(
                        "Style name \"" + style + "\" not found. Ignoring this parameter. Please make sure "
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
                    await message.reply(
                        "Style name \"" + style + "\" not found. Ignoring this parameter. Please make sure "
                                                  "style name matches one of: \n" + ", ".join(self.style_names))

        self.post_obj['prompt'] = self.prompt_no_args
        self.post_obj['save_images'] = True

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


# computes the aspect ratio of the requested resolution, then returns the closest value
# in the list of supported SDXL resolutions
def nearest_sdxl(resx, resy):
    res_string = resx + "x" + resy
    if res_string in SDXL_RES:
        return resx, resy
    ratios = [1.0, 1.29, 0.78, 1.46, 0.68, 1.75, 0.57, 2.4, 0.42]
    ratio = round(int(resx) / int(resy), 2)
    closest = ratios[min(range(len(ratios)), key=lambda i: abs(ratios[i] - ratio))]
    best = SDXL_RES[ratios.index(closest)]
    return int(best.split("x")[0]), int(best.split("x")[1])


def new_split(value):
    lex = shlex.shlex(value)
    lex.quotes = '"'
    lex.whitespace_split = True
    lex.commenters = ''
    return list(lex)
