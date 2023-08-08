import json

f = open('txt2img.json')
post_obj = json.load(f)
f.close()
print(post_obj)
print(post_obj['enable_hr'])