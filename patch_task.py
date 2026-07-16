import os

filepath = '/home/bsk/.gemini/antigravity/brain/c067dd2a-b7be-4fc7-b320-06189bb5ccb4/task.md'
with open(filepath, 'r') as f:
    content = f.read()

content = content.replace('- [ ] aula-7.2.md', '- [x] aula-7.2.md')
content = content.replace('- [ ] exercicio-5.md', '- [x] exercicio-5.md')
content = content.replace('- [ ] projeto-final.md', '- [x] projeto-final.md')

with open(filepath, 'w') as f:
    f.write(content)
