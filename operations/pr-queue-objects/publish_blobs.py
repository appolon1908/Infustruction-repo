"""Upload verified blobs; tree/commit/ref publication belongs to the connector."""
import json
import os
from pathlib import Path
import build_git_objects as builder


class BlobPhaseComplete(Exception):
    pass


original_api = builder.api


def blobs_only(kind, value):
    if kind != 'blobs':
        raise BlobPhaseComplete()
    return original_api(kind, value)


builder.require(os.environ.get('GITHUB_REPOSITORY') == builder.REPOSITORY, 'wrong repository')
builder.require(os.environ.get('GITHUB_REF') == 'refs/heads/fix/pr-queue-source-snapshot-20260906', 'wrong helper ref')
builder.api = blobs_only
results = []
for plan in builder.load_plans():
    try:
        builder.publish(plan)
    except BlobPhaseComplete:
        result = {'pr': plan['pr'], 'blobs_verified': True,
                  'expected_tree': plan['expected_tree'], 'refs_updated': False}
        results.append(result)
        print(json.dumps(result), flush=True)
    else:
        raise RuntimeError('unexpected non-blob publication')
Path('candidate-objects.json').write_text(json.dumps(results, indent=2) + '\n')
