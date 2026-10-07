import unittest
from unittest.mock import MagicMock, patch
from src import push


class PushLifecycleTests(unittest.TestCase):
    def setUp(self):
        push.reset_registry()

    def test_late_unregister_from_a_cannot_remove_b(self):
        push.register_token("a@example.test", "device", "android")
        push.register_token("b@example.test", "device", "android")
        push.unregister_token("device", "a@example.test")
        self.assertEqual(push.registry_snapshot(), {"b@example.test": ["device"]})
        push.unregister_token("device", "b@example.test")
        push.unregister_token("device", "b@example.test")
        self.assertEqual(push.registry_snapshot(), {})

    def test_account_deletion_preserves_tokens_reassigned_to_another_account(self):
        push.register_token("a@example.test", "device", "android")
        push.register_token("a@example.test", "other", "ios")
        push.register_token("b@example.test", "device", "android")
        push.unregister_user("a@example.test")
        self.assertEqual(push.registry_snapshot(), {"b@example.test": ["device"]})

    def test_incoming_and_cancel_push_include_recipient_and_stay_data_only(self):
        push.register_token("b@example.test", "device", "android")
        messaging = MagicMock()
        with patch.object(push, "messaging", messaging):
            self.assertEqual(push.notify_incoming_call(
                to_user_email="b@example.test", from_email="c@example.test",
                from_display_name="Caller", call_id="call-1"), 1)
            self.assertEqual(push.notify_cancel_call(to_user_email="b@example.test", call_id="call-1"), 1)
        payloads = [call.kwargs for call in messaging.Message.call_args_list]
        self.assertEqual([p["data"]["type"] for p in payloads], ["incoming_call", "cancel_call"])
        for payload in payloads:
            self.assertEqual(payload["data"]["toUserId"], "b@example.test")
            self.assertEqual(payload["token"], "device")
            self.assertNotIn("notification", payload)

    def test_calls_for_a_after_switch_are_not_sent_to_b(self):
        push.register_token("a@example.test", "device", "android")
        push.register_token("b@example.test", "device", "android")
        messaging = MagicMock()
        with patch.object(push, "messaging", messaging):
            self.assertEqual(push.notify_incoming_call(
                to_user_email="a@example.test", from_email="c@example.test",
                from_display_name="Caller", call_id="call-1"), 0)
            messaging.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
