import requests
import json
from enum import Enum

responsestr = {}


# only need to get the schema once
def setup():
    global responsestr
    response_format = requests.get("http://127.0.0.1:7860/config")
    responsestr = response_format.json()


# prob don't need to do this lmao
class PayloadFormat(Enum):
    TXT2IMG = 0
    IMG2IMG = 1
    UPSCALE = 2


def do_format(data_holder, payload_format: PayloadFormat):

    # dependencies have ids that point to components. these components (usually) have a label (like "Sampling steps")
    # and a default value (like "20"). we find the dependency we want (key "js" must have value "submit" for txt2img,
    # "submit_img2img" for img2img, and "get_extras_tab_index" for upscale).
    # then iterate through the ids in that dependency and match them with the corresponding id in the components.
    # store the label:value pairs in txt2imgjson.
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
    # dict["dependencies"]["input"] equals 6 which is the id of the component for Prompt
    dependenciesjson = responsestr["dependencies"]
    componentsjson = responsestr["components"]
    dependencylist = []
    labelvaluetuplelist = []

    for dep in dependenciesjson:
        if (dep["js"] == "submit" and payload_format == PayloadFormat.TXT2IMG) or (dep["js"] == "submit_img2img" and payload_format == PayloadFormat.IMG2IMG) or (dep["js"] == "get_extras_tab_index" and payload_format == PayloadFormat.UPSCALE):
            dependencylist = dep["inputs"].copy()
            for i in dep["outputs"]:
                try:
                    dependencylist.append(i.copy())
                except:
                    dependencylist.append(i)
            break

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
                # these are the labels and values we actually care about
                else:
                    labelvaluetuplelist.append((component["props"].get("label"), component["props"].get("value")))
                break

    # iterate through txt2imgjson, find a label you're looking for, and store the index for later use by data_holder
    for i in range(0, len(labelvaluetuplelist)):
        if labelvaluetuplelist[i][0] == "Prompt":
            data_holder.prompt_ind = i
            print(f'prompt: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Negative Prompt":
            data_holder.exclude_ind = i
            print(f'negprompt: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Sampling Steps":
            data_holder.exclude_ind = i
            print(f'samples: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Batch count":
            data_holder.num_ind = i
            print(f'num: {str(i)}')
        elif labelvaluetuplelist[i][0] == "CFG Scale":
            data_holder.conform_ind = i
            print(f'conform: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Seed":
            data_holder.seed_ind = i
            print(f'seed: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Height":
            data_holder.resy_ind = i
            print(f'resy: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Width":
            data_holder.resx_ind = i
            print(f'resx: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Denoising strength":
            data_holder.denoise_ind = i
            print(f'dn: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Image for img2img":
            data_holder.data_ind = i
            print(f'data: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Source":
            data_holder.data_ind = i
            print(f'data: {str(i)}')
        elif labelvaluetuplelist[i][0] == "Resize":
            data_holder.resize_ind = i
            print(f'resize: {str(i)}')
    data = []
    for i in labelvaluetuplelist:
        data.append(i[1])
    filejson = ""
    filename = "data.json"
    prepend = "{\"fn_index\": 11,\"data\": "
    if payload_format == PayloadFormat.IMG2IMG:
        filename = "imgdata.json"
        prepend = "{\"fn_index\": 31,\"data\": "
    elif payload_format == PayloadFormat.UPSCALE:
        filename = "updata.json"
        prepend = "{\"fn_index\": 41,\"data\": "
    postend = ",\"session_hash\": \"cucp21gbbx8\"}"
    with open(filename, "w") as f:
        f.write(prepend)
        f.write(json.dumps(data, indent=2))
        f.write(postend)
    with open("txt2imgjson.json", "w") as f:
        f.write(json.dumps(data, indent=2))

