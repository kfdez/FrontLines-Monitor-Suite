from unittest.mock import Mock

from server.service_manager import ServiceManager


def _manager():
    manager = object.__new__(ServiceManager)
    manager.reload_config = Mock()
    manager.add_log = Mock()
    manager.control_service = Mock()
    manager.auto_start = False
    manager._bot_thread = None

    manager.bot = Mock()
    manager.bot.token = "token"
    manager.bot.source_channel_id = 1
    manager.bot.target_channel_id = 2
    manager.bot.is_running.return_value = False

    manager.hv_monitor = Mock()
    manager.hv_monitor.auto_start = False
    manager.hv_monitor.store_url = "https://example.com/graphql"
    manager.hv_monitor.token = "storefront-token"
    manager.hv_monitor.is_running.return_value = False

    manager.shopify_monitor = Mock()
    manager.shopify_monitor.auto_start = False
    manager.shopify_monitor.is_running.return_value = False
    return manager


def test_start_auto_services_starts_all_enabled_modules():
    manager = _manager()
    manager.auto_start = True
    manager.hv_monitor.auto_start = True
    manager.shopify_monitor.auto_start = True

    manager.start_auto_services()

    manager.reload_config.assert_called_once()
    manager.control_service.assert_called_once_with("bot", "start")
    manager.hv_monitor.start.assert_called_once()
    manager.shopify_monitor.start.assert_called_once()


def test_start_auto_services_skips_disabled_modules():
    manager = _manager()

    manager.start_auto_services()

    manager.control_service.assert_not_called()
    manager.hv_monitor.start.assert_not_called()
    manager.shopify_monitor.start.assert_not_called()


def test_start_auto_services_skips_modules_with_missing_prerequisites():
    manager = _manager()
    manager.auto_start = True
    manager.bot.token = ""
    manager.hv_monitor.auto_start = True
    manager.hv_monitor.store_url = ""

    manager.start_auto_services()

    manager.control_service.assert_not_called()
    manager.hv_monitor.start.assert_not_called()
    messages = [call.args[0] for call in manager.add_log.call_args_list]
    assert any("SKUtto auto-start skipped" in message for message in messages)
    assert any("HV auto-start skipped" in message for message in messages)


def test_auto_start_failure_does_not_block_other_modules():
    manager = _manager()
    manager.auto_start = True
    manager.hv_monitor.auto_start = True
    manager.shopify_monitor.auto_start = True
    manager.control_service.side_effect = RuntimeError("bot failed")

    manager.start_auto_services()

    manager.hv_monitor.start.assert_called_once()
    manager.shopify_monitor.start.assert_called_once()
    assert any(
        "SKUtto auto-start failed" in call.args[0]
        for call in manager.add_log.call_args_list
    )


def test_stop_services_stops_running_modules_and_bot_thread():
    manager = _manager()
    manager.hv_monitor.is_running.return_value = True
    manager.shopify_monitor.is_running.return_value = True
    manager._bot_thread = Mock()
    manager._bot_thread.is_alive.return_value = True

    manager.stop_services()

    manager.hv_monitor.stop.assert_called_once()
    manager.shopify_monitor.stop.assert_called_once()
    manager.bot.stop_sync.assert_called_once()
