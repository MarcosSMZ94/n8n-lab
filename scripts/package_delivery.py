"""Empacota apenas arquivos entregáveis; recusa incluir segredos locais."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {'.git', '.local', '__pycache__'}


def selected_files():
    return sorted(path for path in ROOT.rglob('*') if path.is_file()
        and not (set(path.relative_to(ROOT).parts) & EXCLUDED_PARTS)
        and path.name not in {'.env', 'MANIFEST.sha256'}
        and path.suffix not in {'.pyc', '.zip'})


def main():
    files = selected_files()
    sensitive = []
    access_file = ROOT / '.local/access.json'
    if access_file.exists():
        access = json.loads(access_file.read_text(encoding='utf-8'))
        sensitive.extend(v for k,v in access.items() if 'password' in k or 'token' in k)
    vps_access = ROOT / '.local/vps/access.json'
    if vps_access.exists():
        access = json.loads(vps_access.read_text(encoding='utf-8'))
        sensitive.extend(v for k,v in access.items() if 'password' in k or 'token' in k)
    env_file = ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            if '=' in line:
                key, value = line.split('=',1)
                if any(x in key for x in ['PASSWORD', 'ENCRYPTION_KEY', 'AUTH_TOKEN']):
                    sensitive.append(value.strip("'\""))
    for path in files:
        data = path.read_bytes()
        if any(secret.encode() in data for secret in sensitive if len(secret)>12):
            raise RuntimeError('Segredo local encontrado em arquivo entregável: ' + str(path.relative_to(ROOT)))
    manifest = '\n'.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(ROOT).as_posix() for p in files) + '\n'
    manifest_file = ROOT / 'MANIFEST.sha256'
    manifest_file.write_text(manifest, encoding='utf-8', newline='\n')
    target = ROOT.parent / 'entregas/n8n-ares-2026-10-11.zip'
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files+[manifest_file]:
            archive.write(path, 'n8n-lab/' + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(not (set(Path(n).parts) & EXCLUDED_PARTS) for n in archive.namelist())
        assert not any(Path(n).name=='.env' for n in archive.namelist())
    print(f'ZIP validado: {len(files)+1} arquivos; nenhum segredo local incluído.')
    print(target)


if __name__=='__main__':
    main()
