"""Offline guard tests for the RQ2-V2 sync loopback stall probe.

No SDK construction, external network, local server or provider inference.
The real pinned-SDK integration probe is separate and only run on Colab
after these tests pass. All scientific and API gates remain closed.
"""
from __future__ import annotations

import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rq2_v2_sync_timeout_loopback_probe as subject


class RQ2SyncTimeoutLoopbackGuardTests(unittest.TestCase):
    def test_external_address_is_blocked_before_any_socket_connect(self):
        with subject.only_local_server(12345):
            with socket.socket() as sock:
                with self.assertRaisesRegex(
                    subject.SyncTimeoutProbeBlocked, "Non-loopback",
                ):
                    sock.connect(("8.8.8.8", 443))

    def test_other_local_port_is_blocked(self):
        with subject.only_local_server(12345):
            with socket.socket() as sock:
                with self.assertRaises(subject.SyncTimeoutProbeBlocked):
                    sock.connect(("127.0.0.1", 12346))

    def test_external_dns_is_blocked(self):
        with subject.only_local_server(12345):
            with self.assertRaisesRegex(
                subject.SyncTimeoutProbeBlocked, "External DNS",
            ):
                socket.getaddrinfo("example.com", 443)

    def test_invalid_commit_pin_rejected_without_git(self):
        with patch.object(subject.subprocess, "check_output") as git:
            with self.assertRaisesRegex(
                subject.SyncTimeoutProbeBlocked, "commit pin",
            ):
                subject.verify_checkout(Path("."), "not-a-commit")
            git.assert_not_called()

    def test_dirty_checkout_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / ".git").mkdir()
            with patch.object(
                subject.subprocess, "check_output",
                side_effect=["a" * 40 + "\n", " M src/modified.py\n"],
            ):
                with self.assertRaisesRegex(
                    subject.SyncTimeoutProbeBlocked, "Unclean",
                ):
                    subject.verify_checkout(repo, "a" * 40)

    def test_real_sdk_never_reached_on_bad_pin(self):
        with patch.object(subject, "stalled_local_server") as server:
            with self.assertRaises(subject.SyncTimeoutProbeBlocked):
                subject.run_probe(
                    repo=Path("."), expected_commit="UNAPPROVED",
                )
            server.assert_not_called()

    def test_nested_timeout_is_recognized_without_exposing_error_text(self):
        try:
            try:
                raise TimeoutError("SECRET_NOT_TO_LOG")
            except TimeoutError as inner:
                raise RuntimeError("SDK_WRAPPER") from inner
        except RuntimeError as outer:
            self.assertTrue(subject._contains_timeout(outer))
        self.assertFalse(subject._contains_timeout(ValueError("not timeout")))

    def test_timeout_probe_is_short_and_pin_is_strict(self):
        self.assertGreater(subject.STALL_SECONDS, subject.MAX_ELAPSED_SECONDS)
        self.assertLess(subject.TIMEOUT_SECONDS, subject.MAX_ELAPSED_SECONDS)
        self.assertFalse(subject.SHA1.fullmatch("x" * 40))


if __name__ == "__main__":
    unittest.main()
