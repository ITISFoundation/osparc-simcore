search_text = "replace_me_og_description"
replace_text = "my pretty description"
path = "./source-output/s4l/index.html"
with open(path, 'r') as file:
    data = file.read() 
    data = data.replace(search_text, replace_text) 

with open(path, 'w') as file: 
    file.write(data)
