from yaml import safe_load

with open('secret.yaml', 'r', encoding='utf8') as secret_file:
    config = safe_load(secret_file)
