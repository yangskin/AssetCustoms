import re
code = open(r'c:\Work\GIT\ToolTest\Plugins\AssetCustoms\Content\Python\unreal_integration\config_editor.py', encoding='utf-8').read()
keys_used = set(re.findall(r'_t\("(\w+)"', code))
keys_defined = set(re.findall(r'"(\w+)":\s*\{"en":', code))
missing = keys_used - keys_defined
extra = keys_defined - keys_used
print(f'Used: {len(keys_used)}, Defined: {len(keys_defined)}')
if missing:
    print(f'MISSING: {missing}')
else:
    print('All keys covered!')
if extra:
    print(f'Extra: {extra}')
