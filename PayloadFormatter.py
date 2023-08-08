import requests
import json
from enum import Enum
import platform

responsestr = {}
txt2img_fn_index = 0
img2img_fn_index = 0
upscale_fn_index = 0
style_name_fn_index = 0
model_name_fn_index = 0
s = requests.session()


# only need to get the schema once
def setup(session):
    global responsestr, s
    s = session
    response_format = s.get("http://127.0.0.1:7860/config")
    responsestr = response_format.json()
    with open("schema.txt","w") as f:
        f.write(json.dumps(responsestr))


# prob don't need to do this lmao
class PayloadFormat(Enum):
    TXT2IMG = 0
    IMG2IMG = 1
    UPSCALE = 2
    MODELCHANGE = 3


def do_format(data_holder, payload_format: PayloadFormat):

    # dependencies have ids that point to components. these components (usually) have a label (like "Sampling steps")
    # and a default value (like "20"). we find the dependency we want (key "js" must have value "submit" for txt2img,
    # "submit_img2img" for img2img, and "get_extras_tab_index" for upscale).
    # then iterate through the ids in that dependency and match them with the corresponding id in the components.
    # store the label:value pairs in labelvaluetuplelist.
    # example:
    # {"components":[
    #               { "id": 6,
    #                 "props":{
    #                           "label":"Prompt",
    #                           "value":""
    #                          }
    #                 }, etc ],
    #   "dependencies":[
    #                  { "inputs":{
    #                       6,etc
    #                              },
    #                     "js":"submit", etc
    #                   }]
    # }
    #
    # schema["dependencies"]["input"][0] equals 6 which is the id of the component for Prompt
    dependenciesjson = responsestr["dependencies"]
    componentsjson = responsestr["components"]
    dependencylist = []
    labelvaluetuplelist = []
    global txt2img_fn_index, img2img_fn_index, upscale_fn_index, style_name_fn_index, model_name_fn_index

    for dep in range(0, len(dependenciesjson)):
        if (dependenciesjson[dep]["js"] == "submit" and payload_format == PayloadFormat.TXT2IMG) or (dependenciesjson[dep]["js"] == "submit_img2img" and payload_format == PayloadFormat.IMG2IMG) or (dependenciesjson[dep]["js"] == "get_extras_tab_index" and payload_format == PayloadFormat.UPSCALE):
            dependencylist = dependenciesjson[dep]["inputs"].copy()
            for i in dependenciesjson[dep]["outputs"]:
                try:
                    dependencylist.append(i.copy())
                except:
                    dependencylist.append(i)
        # later on, json payload uses the function index to determine what parameters to accept.
        # function index is the position in dependencies in the schema that the function appears,
        # so txt2img is the 13th function (in this version, could change in the future)
        if dependenciesjson[dep]["js"] == "submit" and txt2img_fn_index == 0:
            # not sure if it's different on linux but this is a guess
            txt2img_fn_index = dep
        elif dependenciesjson[dep]["js"] == "submit_img2img" and img2img_fn_index == 0:
            img2img_fn_index = dep
        elif dependenciesjson[dep]["js"] == "get_extras_tab_index" and upscale_fn_index == 0:
            upscale_fn_index = dep
        elif dependenciesjson[dep]["js"] == "ask_for_style_name" and style_name_fn_index == 0:
            style_name_fn_index = dep
        # idk of a better way to do this. probably really inefficient but only needs to happen once
        elif len(dependenciesjson[dep]["targets"]) == 1 and model_name_fn_index < 2:
            for component in componentsjson:
                if dependenciesjson[dep]["targets"][0] == component["id"] and component["props"].get("label") == "Stable Diffusion checkpoint":
                    model_name_fn_index = dep
                    data_holder.model_names = component["props"].get("choices")
                    break

    # should probably put this in another method or something
    # gets the list of style names
    prepend = "{\"fn_index\": %s,\"data\": " % style_name_fn_index
    data = "[\"\", \"\",\"\"]"
    postend = ",\"session_hash\": \"cucp21gbbx8\"}"
    post_obj = prepend+data+postend
    response = s.post("http://127.0.0.1:7860/api/predict", data=post_obj, timeout=60)
    data_holder.style_names = response.json()["data"][0]["choices"]

    for identifier in dependencylist:
        for component in componentsjson:
            if identifier == component["id"]:
                # one of the labels is empty
                if component["props"].get("name") == "label":
                    labelvaluetuplelist.append(("", 0))
                # img2img has a duplicate label that messes things up
                elif component["props"].get("label") == "Image for img2img" and component["props"].get("elem_id") != "img2img_image":
                    labelvaluetuplelist.append(("", None))
                # upscale has a duplicate label that messes things up
                elif component["props"].get("label") == "Source" and component["props"].get("elem_id") == "pnginf_image":
                    labelvaluetuplelist.append(("", None))
                # only gonna use the one upscaler, idc
                elif component["props"].get("label") == "Upscaler 1":
                    labelvaluetuplelist.append((component["props"].get("label"), "ESRGAN_4x"))
                # slightly changing the img2img Script label so it doesn't clash with another label of the same name
                elif component["props"].get("label") == "Script" and len(component["props"].get("choices")) > 3:
                    labelvaluetuplelist.append(("Scripts", "None"))
                elif component["props"].get("label") == "Sampling method":
                    labelvaluetuplelist.append(("Sampling method", "Euler a"))
                    data_holder.sampling_methods = component["props"].get("choices")
                # these are the labels and values we actually care about
                else:
                    labelvaluetuplelist.append((component["props"].get("label"), component["props"].get("value")))
                break

    with open("log/indices.txt", "w") as f:
        # iterate through labelvaluetuplelist, find a label you're looking for, and store the index for
        # later use by data_holder
        for i in range(0, len(labelvaluetuplelist)):
            if labelvaluetuplelist[i][0] == "Prompt":
                data_holder.prompt_ind = i
                f.write(f'prompt: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Negative prompt":
                data_holder.exclude_ind = i
                f.write(f'negprompt: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Sampling Steps":
                data_holder.sample_ind = i
                f.write(f'samples: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Batch count":
                data_holder.num_ind = i
                f.write(f'num: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "CFG Scale":
                data_holder.conform_ind = i
                f.write(f'conform: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Seed":
                data_holder.seed_ind = i
                f.write(f'seed: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Height":
                data_holder.resy_ind = i
                f.write(f'resy: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Width":
                data_holder.resx_ind = i
                f.write(f'resx: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Denoising strength":
                data_holder.denoise_ind = i
                f.write(f'dn: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Image for img2img":
                data_holder.data_ind = i
                f.write(f'data: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Source":
                data_holder.data_ind = i
                f.write(f'data: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Resize":
                data_holder.resize_ind = i
                f.write(f'resize: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Scripts":
                data_holder.script_ind = i
                f.write(f'script: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Loops":
                data_holder.loop_ind = i
                f.write(f'loops: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Sampling method":
                data_holder.sampling_methods_ind = i
                f.write(f'sampling method: {str(i)}\n')
            elif labelvaluetuplelist[i][0] == "Style 1":
                data_holder.style1_ind = i
            elif labelvaluetuplelist[i][0] == "Style 2":
                data_holder.style2_ind = i

    data = []
    for i in labelvaluetuplelist:
        data.append(i[1])
    filename = "data.json"
    prepend = "{\"fn_index\": %s,\"data\": " % txt2img_fn_index
    if payload_format == PayloadFormat.IMG2IMG:
        filename = "imgdata.json"
        prepend = "{\"fn_index\": %s,\"data\": " % img2img_fn_index
    elif payload_format == PayloadFormat.UPSCALE:
        filename = "updata.json"
        prepend = "{\"fn_index\": %s,\"data\": " % upscale_fn_index
    elif payload_format == PayloadFormat.MODELCHANGE:
        filename = "modelchange.json"
        prepend = "{\"fn_index\": %s,\"data\": " % model_name_fn_index
        data = ["filler"]
    postend = ",\"session_hash\": \"cucp21gbbx8\"}"
    with open(filename, "w") as f:
        f.write(prepend)
        f.write(json.dumps(data, indent=2))
        f.write(postend)


