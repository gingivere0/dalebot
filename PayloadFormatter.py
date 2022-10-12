import requests
import json
from enum import Enum

responsestr = {}


def setup():
    global responsestr
    response_format = requests.get("http://127.0.0.1:7860/config")
    responsestr = response_format.json()


class PayloadFormat(Enum):
    TXT2IMG = 0
    IMG2IMG = 1
    UPSCALE = 2


def do_format(data_holder, payload_format: PayloadFormat):

    # dependencies have ids that point to components. these components (usually) have a label (like "Sampling steps")
    # and a default value (like "20"). we find the dependency we want (key "js" must have value "submit").
    # then iterate through the ids in that dependency and match them with the corresponding id in the components.
    # store the label:value pairs in txt2imgjson.
    dependenciesjson = responsestr["dependencies"]
    componentsjson = responsestr["components"]
    dependencylist = ""
    labelvaluetuplelist = []
    for dep in dependenciesjson:
        if (dep["js"] == "submit" and payload_format == PayloadFormat.TXT2IMG) or (dep["js"] == "submit_img2img" and payload_format == PayloadFormat.IMG2IMG):
            dependencylist = dep["inputs"]
            for i in dep["outputs"]:
                dependencylist.append(i)
    for identifier in dependencylist:
        for component in componentsjson:
            if identifier == component["id"]:
                labelvaluetuplelist.append((component["props"].get("label") if component["props"].get(
                    "label") is not None else "", component["props"].get("value")))

    # iterate through txt2imgjson, find a label you're looking for, and store the index for later use by data_holder
    for i in range(0, len(labelvaluetuplelist)):
        if labelvaluetuplelist[i][0] == "Prompt":
            data_holder.prompt_ind = i
        elif labelvaluetuplelist[i][0] == "Negative Prompt":
            data_holder.exclude_ind = i
        elif labelvaluetuplelist[i][0] == "Sampling Steps":
            data_holder.exclude_ind = i
        elif labelvaluetuplelist[i][0] == "Batch count":
            data_holder.num_ind = i
        elif labelvaluetuplelist[i][0] == "CFG Scale":
            data_holder.conform_ind = i
        elif labelvaluetuplelist[i][0] == "Seed":
            data_holder.seed_ind = i
        elif labelvaluetuplelist[i][0] == "Height":
            data_holder.resy_ind = i
        elif labelvaluetuplelist[i][0] == "Width":
            data_holder.resx_ind = i
        elif labelvaluetuplelist[i][0] == "Denoising strength":
            data_holder.denoise_ind = i

    # overwrite the data that exists in data.json with the data we've created from the schema in /config
    # should probably make this so it starts from new instead of injecting
    data = []
    for i in labelvaluetuplelist:
        data.append(i[1])
    filejson = ""
    filename = ""
    if payload_format == PayloadFormat.TXT2IMG:
        filename = "data.json"
    elif payload_format == PayloadFormat.IMG2IMG:
        filename = "imgdata.json"
    with open(filename, "r") as f:
        filejson = json.load(f)
        filejson["data"] = data
    with open(filename, "w") as f:
        f.write(json.dumps(filejson, indent=2))
    with open("txt2imgjson.json", "w") as f:
        f.write(json.dumps(data))

