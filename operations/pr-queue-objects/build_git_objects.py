#!/usr/bin/env python3
"""Create verified Git objects only. Never update a branch, approve, or merge."""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import urllib.request

REPOSITORY = 'appolon1908-hue/Infustruction-repo'
BASE = f'https://api.github.com/repos/{REPOSITORY}/git/'
SHA = re.compile(r'[0-9a-f]{40}')
LIMIT = 20_000_000


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        raise RuntimeError('Git object API redirect refused')


def api(kind, value):
    require(kind in {'blobs', 'trees', 'commits'}, 'only immutable Git object endpoints allowed')
    request = urllib.request.Request(BASE + kind, data=json.dumps(value).encode(), method='POST', headers={
        'Authorization': 'Bearer ' + os.environ['GH_OBJECT_TOKEN'],
        'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'codestra-pr-object-builder',
    })
    with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
        return json.load(response)


def existing_blob(sha):
    require(SHA.fullmatch(sha), 'invalid base blob identity')
    request = urllib.request.Request(BASE + 'blobs/' + sha, headers={
        'Authorization': 'Bearer ' + os.environ['GH_OBJECT_TOKEN'],
        'Accept': 'application/vnd.github+json', 'User-Agent': 'codestra-pr-object-builder',
    })
    with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
        value = json.load(response)
    require(value.get('encoding') == 'base64', 'unexpected blob encoding')
    data = base64.b64decode(value['content'])
    require(len(data) <= LIMIT and digest(data) == sha, 'existing blob identity mismatch')
    return data.decode('utf-8').splitlines(keepends=True)


def publish(plan):
    require(SHA.fullmatch(plan['base_tree']) and SHA.fullmatch(plan['expected_tree']), 'invalid tree identity')
    require(plan['parents'] and all(SHA.fullmatch(p) for p in plan['parents']), 'invalid parents')
    entries, paths = [], set()
    for item in plan['entries']:
        path = item['path']
        require(str(PurePosixPath(path)) == path and not path.startswith('/')
                and not any(p in {'.git', '..'} for p in PurePosixPath(path).parts), 'unsafe path')
        require(path not in paths, 'duplicate tree entry')
        paths.add(path)
        require(item['mode'] in {'100644', '100755', '120000'}, 'unexpected mode')
        sha = item['sha']
        if 'content' in item or 'segments' in item:
            if 'segments' in item:
                old = existing_blob(item['base_blob'])
                parts = []
                for segment in item['segments']:
                    if isinstance(segment, list):
                        require(len(segment) == 2 and all(type(i) is int for i in segment)
                                and 0 <= segment[0] <= segment[1] <= len(old), 'invalid source slice')
                        parts.append(''.join(old[segment[0]:segment[1]]))
                    else:
                        require(isinstance(segment, str), 'invalid source segment')
                        parts.append(segment)
                data = ''.join(parts).encode('utf-8')
            else:
                data = item['content'].encode('utf-8')
            require(len(data) <= LIMIT and digest(data) == sha, 'content identity mismatch')
            actual = api('blobs', {'content': base64.b64encode(data).decode(), 'encoding': 'base64'})['sha']
            require(actual == sha, 'server blob identity mismatch')
        else:
            require(sha is None or SHA.fullmatch(sha), 'invalid existing blob identity')
        entries.append({'path': path, 'mode': item['mode'], 'type': 'blob', 'sha': sha})
    tree = api('trees', {'base_tree': plan['base_tree'], 'tree': entries})['sha']
    require(tree == plan['expected_tree'], 'candidate tree differs from locally reviewed tree')
    commit = api('commits', {'message': plan['message'], 'tree': tree, 'parents': plan['parents']})['sha']
    require(SHA.fullmatch(commit), 'invalid server commit')
    result = {'pr': plan['pr'], 'commit': commit, 'tree': tree, 'parents': plan['parents'], 'refs_updated': False}
    print(json.dumps(result), flush=True)
    return result


def load_plans():
    root = Path('operations/pr-queue-objects')
    parts = [(root / 'plans.0.b64').read_text().strip(),
             (root / 'plans.1.b64').read_text().strip(),
             ''.join((root / f'plans.2.{i}.b64').read_text().strip() for i in range(7)),
             (root / 'plans.3.b64').read_text().strip()]
    # Correct two identified transcription errors before checking the original
    # locally calculated hashes. No unmatched payload is ever accepted.
    parts[0] = parts[0].replace('W1eY+6KESUpmCjyyFxuUu8eBx', 'W1eY+6KESUpmCjyyFxuU8eBx')
    parts[1] = parts[1].replace('g4u9u4vJL6e', 'g4u9g4vJL6e')
    expected = [
        '4ce187349e60dfad15f8e6072f09088bef0b8924e585fe5b8a324922ccb5976e',
        'e681b7342ea3046c403491f214c081fbbc000c9fbbf4b4de50f5eea446fe827c',
        'be6350552bba06936974ba6d6acc94de3529c16597e2d06b7944515470978018',
        'f6b3fcdfa92a195126b9bd9aed08d20e26d78a6d377e63908c011a5ffcedcbe7',
    ]
    for i, part in enumerate(parts):
        require(hashlib.sha256(part.encode()).hexdigest() == expected[i], f'plan chunk {i} checksum mismatch')
    packed = ''.join(parts)
    require(hashlib.sha256(packed.encode()).hexdigest() ==
            '1e508796eb568f4806e8800b0e6f47c52662cea65d3d64c0bf7fdd74eceb59e2', 'plan checksum mismatch')
    data = gzip.decompress(base64.b64decode(packed, validate=True))
    require(len(data) <= LIMIT, 'oversized plans')
    plans = json.loads(data)
    require(isinstance(plans, list) and 0 < len(plans) <= 10, 'invalid plan count')
    return plans


def main():
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'wrong repository')
    require(os.environ.get('GITHUB_REF') == 'refs/heads/fix/pr-queue-source-snapshot-20260906', 'wrong helper ref')
    results = [publish(plan) for plan in load_plans()]
    Path('candidate-objects.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
