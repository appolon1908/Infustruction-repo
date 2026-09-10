"""Offline authority checks; no live GitHub, credentials or runtime are needed."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_stage6_authority_heads as validator


SHA = "a" * 40
OTHER_SHA = "b" * 40
DEFINITION = {"repository": "appolon1908-hue/Keycloak", "revision": SHA}
URL = "https://api.github.com/repos/appolon1908-hue/Keycloak/git/ref/heads/main"


class Response(io.BytesIO):
    def __init__(self, payload=None, raw=None, url=URL):
        super().__init__(raw if raw is not None else json.dumps(payload).encode())
        self.url = url

    def geturl(self):
        return self.url


def ref(sha=SHA):
    return {"ref": "refs/heads/main", "object": {"type": "commit", "sha": sha}}


def error(code, headers=None):
    return HTTPError(URL, code, "not printed", headers or {}, io.BytesIO(b"sensitive response"))


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.factory = patch.object(validator, "build_opener")
        self.open = self.factory.start().return_value.open
        self.addCleanup(self.factory.stop)
        sleeper = patch.object(validator.time, "sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def inspect(self, payload=None):
        self.open.return_value = Response(ref() if payload is None else payload)
        return validator.inspect_head("keycloak", DEFINITION)

    def test_live_match_preserves_original_tuple_api(self):
        self.open.return_value = Response(ref())
        self.assertEqual(validator.authority_head("keycloak", DEFINITION),
                         ("keycloak", DEFINITION["repository"], SHA))

    def test_drift_is_not_a_pass_or_a_rewritten_revision(self):
        result = self.inspect(ref(OTHER_SHA))
        self.assertEqual(result.status, "DRIFT")
        self.assertEqual((result.expected, result.observed), (SHA, OTHER_SHA))
        self.assertEqual(DEFINITION["revision"], SHA)

    def test_legacy_api_still_raises_for_drift(self):
        self.open.return_value = Response(ref(OTHER_SHA))
        with self.assertRaisesRegex(RuntimeError, "DRIFT"):
            validator.authority_head("keycloak", DEFINITION)

    def test_explicit_read_token_is_sent_only_to_canonical_url(self):
        os.environ["STAGE6_SOURCE_READ_TOKEN"] = "test-read-token"
        self.assertEqual(self.inspect().status, "MATCH")
        request = self.open.call_args.args[0]
        self.assertEqual(request.full_url, URL)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-read-token")
        self.assertEqual(self.open.call_args.kwargs["timeout"], validator.TIMEOUT)

    def test_no_implicit_github_token_fallback(self):
        os.environ["GITHUB_TOKEN"] = "must-not-be-used"
        self.inspect()
        self.assertIsNone(self.open.call_args.args[0].get_header("Authorization"))

    def test_invalid_credential_is_rejected_without_network_or_disclosure(self):
        os.environ["STAGE6_SOURCE_READ_TOKEN"] = "secret\nheader"
        result = validator.inspect_head("keycloak", DEFINITION)
        self.assertEqual(result.status, "INVALID_CREDENTIAL")
        self.assertNotIn("secret", result.detail)
        self.open.assert_not_called()

    def test_authentication_authorization_and_404_are_distinct_failures(self):
        for code, status in [(401, "AUTHENTICATION_FAILED"), (403, "ACCESS_DENIED"),
                             (404, "NOT_FOUND_OR_INACCESSIBLE")]:
            with self.subTest(code=code):
                self.open.reset_mock()
                self.open.side_effect = error(code)
                result = validator.inspect_head("keycloak", DEFINITION)
                self.assertEqual(result.status, status)
                self.assertIn("trusted read-only", result.detail)
                self.assertNotIn("sensitive", result.detail)
                self.open.assert_called_once()
        self.sleep.assert_not_called()

    def test_rate_limits_do_not_hammer_api_or_become_access_success(self):
        for code, headers in [(429, {}), (403, {"X-RateLimit-Remaining": "0"}),
                              (403, {"Retry-After": "120"})]:
            with self.subTest(code=code, headers=headers):
                self.open.reset_mock()
                self.open.side_effect = error(code, headers)
                self.assertEqual(validator.inspect_head("keycloak", DEFINITION).status, "RATE_LIMITED")
                self.open.assert_called_once()
        self.sleep.assert_not_called()

    def test_redirect_status_is_rejected_without_retry(self):
        self.open.side_effect = error(302)
        self.assertEqual(validator.inspect_head("keycloak", DEFINITION).status, "REDIRECT_REJECTED")
        self.open.assert_called_once()

    def test_redirect_handler_never_creates_a_followup_request(self):
        handler = validator.NoRedirect()
        self.assertIsNone(handler.redirect_request(Request(URL), None, 302, "moved", {},
                                                   "https://untrusted.example/collect"))

    def test_changed_response_url_fails_closed(self):
        self.open.return_value = Response(ref(), url="https://untrusted.example/collect")
        self.assertEqual(validator.inspect_head("keycloak", DEFINITION).status, "REDIRECT_REJECTED")

    def test_transient_server_error_retries_then_matches(self):
        self.open.side_effect = [error(503), Response(ref())]
        self.assertEqual(validator.inspect_head("keycloak", DEFINITION).status, "MATCH")
        self.assertEqual(self.open.call_count, 2)
        self.sleep.assert_called_once_with(1)

    def test_server_retries_are_bounded(self):
        self.open.side_effect = [error(502) for _ in range(validator.ATTEMPTS)]
        self.assertEqual(validator.inspect_head("keycloak", DEFINITION).status, "HTTP_ERROR")
        self.assertEqual(self.open.call_count, validator.ATTEMPTS)
        self.assertEqual(self.sleep.call_count, validator.ATTEMPTS - 1)

    def test_network_retries_recover(self):
        self.open.side_effect = [URLError("temporary"), Response(ref())]
        self.assertEqual(validator.inspect_head("keycloak", DEFINITION).status, "MATCH")
        self.assertEqual(self.open.call_count, 2)

    def test_timeout_retries_are_bounded_and_redacted(self):
        self.open.side_effect = TimeoutError("sensitive-token")
        result = validator.inspect_head("keycloak", DEFINITION)
        self.assertEqual(result.status, "NETWORK_ERROR")
        self.assertNotIn("sensitive-token", result.detail)
        self.assertEqual(self.open.call_count, validator.ATTEMPTS)

    def test_bad_json_and_encoding_are_explicit_failures(self):
        for raw in [b"{broken", b"\xff", b"null"]:
            with self.subTest(raw=raw):
                self.open.return_value = Response(raw=raw)
                self.assertEqual(validator.inspect_head("keycloak", DEFINITION).status, "INVALID_RESPONSE")

    def test_unexpected_ref_and_object_types_never_crash(self):
        for payload in [[], "secret", 42, {}, {"ref": "refs/heads/development"},
                        {"ref": "refs/heads/main", "object": None},
                        {"ref": "refs/heads/main", "object": []},
                        {"ref": "refs/heads/main", "object": {"type": "tag", "sha": SHA}}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.inspect(payload).status, "INVALID_RESPONSE")

    def test_untrusted_sha_types_never_crash(self):
        for sha in [None, [], {}, 3, True, "a" * 39, "A" * 40, "secret\n"]:
            with self.subTest(sha=sha):
                self.assertEqual(self.inspect(ref(sha)).status, "INVALID_RESPONSE")

    def test_response_size_is_bounded(self):
        self.open.return_value = Response(raw=b" " * (validator.MAX_RESPONSE_BYTES + 1))
        self.assertEqual(validator.inspect_head("keycloak", DEFINITION).status, "INVALID_RESPONSE")

    def test_invalid_definitions_make_no_request(self):
        for definition in [None, [], {}, {"repository": "../secret", "revision": SHA},
                           {"repository": "https://example.com/repo", "revision": SHA},
                           {"repository": "owner/..", "revision": SHA},
                           {"repository": "owner/repo?query", "revision": SHA},
                           {"repository": DEFINITION["repository"], "revision": 42}]:
            with self.subTest(definition=definition), self.assertRaises(validator.LockError):
                validator.inspect_head("keycloak", definition)
        self.open.assert_not_called()


class InputAndReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.lock = self.root / "lock.yaml"
        self.report = self.root / "report.json"
        self.lock.write_text(yaml.safe_dump({"repositories": {"keycloak": DEFINITION}}))

    def run_main(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            code = validator.main(["--lock", str(self.lock), "--json-report", str(self.report)])
        return code, output.getvalue(), json.loads(self.report.read_text())

    def test_valid_lock_is_loaded(self):
        self.assertEqual(validator.load_repositories(self.lock.read_bytes()), {"keycloak": DEFINITION})

    def test_empty_and_malformed_locks_fail_before_requests(self):
        for raw in [b"", b"[]", b"null", b"{}", b"repositories: {}", b"repositories: []",
                    b"repositories: null", b"repositories: [", b"\xff"]:
            with self.subTest(raw=raw), self.assertRaises(validator.LockError):
                validator.load_repositories(raw)

    def test_duplicate_mapping_keys_are_rejected(self):
        for raw in [b"repositories: {}\nrepositories: {}\n",
                    b"repositories:\n  keycloak: {}\n  keycloak: {}\n",
                    b"repositories:\n  keycloak:\n    revision: a\n    revision: b\n"]:
            with self.subTest(raw=raw), self.assertRaises(validator.LockError):
                validator.load_repositories(raw)

    def test_committed_source_lock_is_compatible_with_safe_loader(self):
        raw = validator.LOCK.read_bytes()
        actual = validator.load_repositories(raw)
        self.assertTrue(actual)
        self.assertEqual(actual, yaml.safe_load(raw)["repositories"])

    def test_runtime_aliases_allow_explicit_overrides(self):
        raw = (self.lock.read_text() + """
runtime:
  notification: &worker
    repository: UNVERIFIED
    compose_service: notification-worker-staging
  scheduler:
    <<: *worker
    compose_service: scheduler-staging
  second_scheduler:
    <<: *worker
    compose_service: another-worker-staging
""").encode()
        self.assertEqual(validator.load_repositories(raw), {"keycloak": DEFINITION})
        self.assertEqual(yaml.load(raw, Loader=validator.UniqueSafeLoader), yaml.safe_load(raw))

    def test_repository_aliases_preserve_explicit_revision_override(self):
        raw = f"""
defaults: &defaults
  repository: {DEFINITION['repository']}
  revision: {SHA}
repositories:
  keycloak:
    <<: *defaults
    revision: {OTHER_SHA}
""".encode()
        self.assertEqual(validator.load_repositories(raw)["keycloak"],
                         {"repository": DEFINITION["repository"], "revision": OTHER_SHA})

    def test_merge_sequences_and_nested_aliases_match_safe_loader(self):
        raw = f"""
base: &base
  repository: {DEFINITION['repository']}
  revision: {SHA}
override: &override
  revision: {OTHER_SHA}
nested: &nested
  <<: [*override, *base]
repositories:
  keycloak:
    <<: *nested
  another:
    <<: *nested
""".encode()
        actual = validator.load_repositories(raw)
        self.assertEqual(actual, yaml.safe_load(raw)["repositories"])
        self.assertEqual(actual["keycloak"]["revision"], OTHER_SHA)

    def test_duplicate_literal_keys_inside_inline_merge_are_rejected(self):
        raw = f"""
repositories:
  keycloak:
    <<: {{repository: {DEFINITION['repository']}, revision: {SHA}, revision: {OTHER_SHA}}}
""".encode()
        with self.assertRaises(validator.LockError):
            validator.load_repositories(raw)

    def test_duplicate_merge_directives_are_rejected(self):
        raw = f"""
defaults: &defaults
  repository: {DEFINITION['repository']}
  revision: {SHA}
repositories:
  keycloak:
    <<: *defaults
    <<: *defaults
""".encode()
        with self.assertRaises(validator.LockError):
            validator.load_repositories(raw)

    def test_malformed_merge_operands_fail_closed(self):
        for operand in ["42", "[42]", "null"]:
            raw = f"repositories: {{keycloak: {{<<: {operand}}}}}".encode()
            with self.subTest(operand=operand), self.assertRaises(validator.LockError):
                validator.load_repositories(raw)

    def test_invalid_component_keys_cannot_inject_logs(self):
        for component in [True, 3, "bad\nname", ""]:
            raw = yaml.safe_dump({"repositories": {component: DEFINITION}}).encode()
            with self.subTest(component=component), self.assertRaises(validator.LockError):
                validator.load_repositories(raw)

    def test_parser_error_does_not_echo_source_content(self):
        self.lock.write_text("repositories: [sensitive-source")
        code, output, report = self.run_main()
        self.assertEqual(code, 2)
        self.assertEqual(report["validation"], "FAIL")
        self.assertNotIn("sensitive-source", output + json.dumps(report))

    def test_invalid_lock_still_writes_failure_report_without_network(self):
        self.lock.write_text("repositories: {}")
        with patch.object(validator, "build_opener") as opener:
            code, output, report = self.run_main()
        opener.assert_not_called()
        self.assertEqual(code, 2)
        self.assertIn("AUTHORITY_VALIDATION=FAIL", output)
        self.assertEqual(report["results"], [])

    def test_missing_lock_has_a_report_not_a_traceback(self):
        self.lock.unlink()
        code, _, report = self.run_main()
        self.assertEqual(code, 2)
        self.assertEqual(report["error"], "cannot read source lock")
        self.assertIsNone(report["lock_sha256"])

    def test_all_matching_is_the_only_zero_exit(self):
        match = validator.Result("keycloak", DEFINITION["repository"], SHA, "MATCH", SHA)
        before = self.lock.read_bytes()
        with patch.object(validator, "inspect_head", return_value=match):
            code, output, report = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(report["validation"], "PASS")
        self.assertEqual(report["lock_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual((report["required"], report["matched"], report["failed"]), (1, 1, 0))
        self.assertIn("AUTHORITY_HEADS=1/1", output)
        self.assertEqual(self.lock.read_bytes(), before)

    def test_mixed_results_are_sorted_and_fail_closed(self):
        repositories = {"z": DEFINITION, "a": DEFINITION}
        self.lock.write_text(yaml.safe_dump({"repositories": repositories}))
        def inspect(component, definition):
            return validator.Result(component, definition["repository"], SHA,
                                    "MATCH" if component == "z" else "DRIFT", OTHER_SHA)
        with patch.object(validator, "inspect_head", side_effect=inspect):
            code, _, report = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual((report["required"], report["matched"], report["failed"]), (2, 1, 1))
        self.assertEqual([item["component"] for item in report["results"]], ["a", "z"])

    def test_worker_exception_is_attributed_and_redacted(self):
        with patch.object(validator, "inspect_head", side_effect=RuntimeError("sensitive-token")):
            code, output, report = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual(report["results"][0]["status"], "INTERNAL_ERROR")
        self.assertEqual(report["results"][0]["component"], "keycloak")
        self.assertNotIn("sensitive-token", output + json.dumps(report))

    def test_report_cannot_overwrite_lock(self):
        before = self.lock.read_bytes()
        with patch("sys.stdout", new_callable=io.StringIO):
            code = validator.main(["--lock", str(self.lock), "--json-report", str(self.lock)])
        self.assertEqual(code, 2)
        self.assertEqual(self.lock.read_bytes(), before)

    def test_report_write_failure_is_nonzero(self):
        self.lock.write_text("repositories: {}")
        with patch.object(validator, "write_report", side_effect=OSError("sensitive-path")), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            code = validator.main(["--lock", str(self.lock), "--json-report", str(self.report)])
        self.assertEqual(code, 2)
        self.assertIn("AUTHORITY_REPORT=FAIL", output.getvalue())
        self.assertNotIn("sensitive-path", output.getvalue())

    def test_report_output_is_deterministic_and_atomic(self):
        report = {"results": [], "validation": "FAIL"}
        validator.write_report(self.report, report)
        before = self.report.read_bytes()
        validator.write_report(self.report, report)
        self.assertEqual(self.report.read_bytes(), before)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["lock.yaml", "report.json"])


if __name__ == "__main__":
    unittest.main()
