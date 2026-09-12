
""" a module for reading in an Obsidian Vault and creating a file (index.html)
    with links to each of the .md files in the vault- formatted for use in Notes.app etc. 
""" 
import os


os.chdir("/Users/curtis/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian")

print("Obsidian Vault (.md): \n", os.listdir())


links = {}
for f in os.listdir():
    if f.endswith(".md"):
        name = f.split(".")[0]
        l_name = name.replace(" ", "%20")
        link = f"obsidian://open?vault=Obsidian&file={l_name}"
        links.update({name: link})
        print("-> ", link)

with open("obsidian_index.html", "w") as f:

    f.write("""

    <!DOCTYPE html>
            
    <html>
            
    <body>

    <h1>Obsidian Index</h1>

    <ul>

    """)

    for name, link in sorted(links.items()):

        f.write(f'<li><a href="{link}">{name}</a></li>\n')




