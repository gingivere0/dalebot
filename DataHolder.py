import json
import sys
import re
import requests
import base64
import random

SDXL_RES = ("1024x1024", "1152x896", "896x1152", "1216x832", "832x1216", "1344x768", "768x1344", "1536x640", "640x1536")
SDXL_UNSUPPORTED_SAMPLERS = {'DDIM', 'PLMS', 'UniPC'}


class DataHolder:
    def __init__(self):
        self.is_disco = None
        self.arguments = []
        self.original_prompt = ""
        self.post_obj = None
        self.denoise_bool = False
        self.reply_string = ""
        self.is_loopback = False
        self.lora_names = []
        self.style_names = []
        self.sampler_names = []
        self.is_upscale = False
        self.attachment = None
        self.endpoint = '/sdapi/v1/txt2img'

    # reset to default values
    def reset(self):
        self.arguments = []
        self.original_prompt = ""
        self.post_obj = {
            'width': 1024,
            'height': 1024,
            'steps': 30,
            'sampler': 'DPM++ 2M SDE Karras',
            'styles': [],
            'save_images': True
        }
        self.denoise_bool = False
        self.reply_string = ""
        self.is_loopback = False
        self.is_upscale = False
        self.is_disco = False
        self.attachment = None
        self.endpoint = '/sdapi/v1/txt2img'

    def setup(self, message):
        self.reset()
        self.reply_string = ""
        self.original_prompt = self.reply_string + message

        # find anything in curly braces (negative prompt)
        # split the message string (sans negative) into the prompt and a list of tuples
        # containing options (e.g. "res=") and parameters (e.g. "512x512")
        negatives = re.findall(r'({.+})', self.original_prompt)
        negative = "" if len(negatives) == 0 else negatives[0]
        fragments = re.split(r'\s\w+=', self.original_prompt.replace(negative, ""))
        options = re.findall(r'(\w+=)', self.original_prompt)
        self.post_obj['prompt'] = fragments[0]
        self.arguments = list(zip(options, fragments[1:]))
        if negative != "":
            self.arguments.append(('negative=', negative[1:-1]))

    def set_available_options(self, loras, styles, samplers):
        self.lora_names = [l['alias'] for l in loras]
        self.style_names = [s['name'] for s in styles]
        for s in samplers:
            if s['name'] not in SDXL_UNSUPPORTED_SAMPLERS:
                self.sampler_names.append(s['name'])

    # removes parameters from the prompt and parses them accordingly
    async def wordparse(self):
        for arg in self.arguments:
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
                    self.post_obj['n_iter'] = int(numpics)

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
                self.post_obj['script_name'] = 'x/y/z plot'
                self.post_obj['script_args'] = xyz_plot_args(7, arg[1][1:-1])

            if arg[0] == 'loops=' and self.attachment is not None:
                self.post_obj['script_name'] = 'loopback'
                self.post_obj['script_args'] = loopback_args(int(arg[1]))

            if arg[0] == 'style1=' or arg[0] == 'style2=':
                style = arg[1].replace('"', '')
                if style in self.style_names:
                    self.post_obj['styles'].append(style)

            if arg[0] == 'sampler=':
                sampler = arg[1].replace('"', '')
                if arg[1].lower() == 'platter' and not self.is_disco:
                    self.post_obj['n_iter'] = 1
                    self.post_obj['script_name'] = 'x/y/z plot'
                    random_samplers = random.sample(self.sampler_names, 5)
                    self.post_obj['script_args'] = xyz_plot_args(9, x_vals_list=random_samplers)
                elif sampler in self.sampler_names:
                    self.post_obj['sampler_name'] = sampler

        # apply some random settings
        if self.is_disco:
            random_res = random.choice(SDXL_RES[:5])
            resx = random_res.split("x")[0]
            resy = random_res.split("x")[1]
            self.post_obj['width'] = resx
            self.post_obj['height'] = resy
            self.post_obj['styles'] = [random.choice(self.style_names)]

        if self.attachment is not None:
            if self.is_upscale:
                self.post_obj = {
                    'image': str(self.attachment)[2:-1],
                    'upscaler_1': 'ESRGAN_4x',
                    'save_images': True
                }
                self.endpoint = '/sdapi/v1/extra-single-image'
            else:
                self.post_obj['init_images'] = [str(self.attachment)[2:-1]]
                self.endpoint = '/sdapi/v1/img2img'

    async def add_attachment(self, url):
        try:
            img_bytes = requests.get(url).content
        except Exception as e:
            print(e)
            return
        self.attachment = base64.b64encode(img_bytes)


# generates the list of args for a loopback
def loopback_args(loops, final=0.5, curve=1, interrogator=0):
    return [loops, final, curve, interrogator]


# generates the list of args for an xyz plot
def xyz_plot_args(x_type,   x_vals='', x_vals_list=None,
                  y_type=0, y_vals='', y_vals_list=None,
                  z_type=0, z_vals='', z_vals_list=None):
    return [x_type, x_vals, x_vals_list,
            y_type, y_vals, y_vals_list,
            z_type, z_vals, z_vals_list,
            True, False, False, False, 0]


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
