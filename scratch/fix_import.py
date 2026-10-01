with open('backend/app/models.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('from sqlalchemy import ', 'from sqlalchemy import UniqueConstraint, ')

with open('backend/app/models.py', 'w', encoding='utf-8') as f:
    f.write(text)
