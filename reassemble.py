import json

with open('images.txt', 'w') as out_file, open('images.json', 'r') as in_file:
    lines = []
    for i in json.load(in_file):
        if 'docker.io' not in i['original_image']:
            reassembled = f"{i['original_image']}:{i['tag']}"   # {i['new_image_key']}
            lines.append(reassembled)
    out_file.write("\n".join(lines))
