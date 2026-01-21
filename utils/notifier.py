"""
Notification service for EcoFlow Power Management.

Supports Pushover and Telegram notifications for critical events.
Optional - system works without notifications if not configured.
"""
import os
import logging
import re
import requests
from typing import Optional, List

logger = logging.getLogger("notifier")


class Notifier:
    """Handles notifications to Pushover and Telegram"""
    
    def __init__(self):
        # Pushover configuration
        self.pushover_enabled = os.getenv("PUSHOVER_ENABLED", "false").lower() == "true"
        self.pushover_user = os.getenv("PUSHOVER_USER_KEY", "")
        self.pushover_token = os.getenv("PUSHOVER_API_TOKEN", "")
        
        # Telegram configuration
        self.telegram_enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        # Notification preferences
        self.notify_grid_loss = os.getenv("NOTIFY_GRID_LOSS", "true").lower() == "true"
        self.notify_soc_warnings = os.getenv("NOTIFY_SOC_WARNINGS", "true").lower() == "true"
        self.notify_shutdown = os.getenv("NOTIFY_SHUTDOWN_COMMANDS", "true").lower() == "true"
        self.notify_grid_restored = os.getenv("NOTIFY_GRID_RESTORED", "true").lower() == "true"
        self.notify_system = os.getenv("NOTIFY_SYSTEM_EVENTS", "true").lower() == "true"
        
        # Validate configuration
        if self.pushover_enabled and (not self.pushover_user or not self.pushover_token):
            logger.warning("Pushover enabled but credentials missing - disabling")
            self.pushover_enabled = False
            
        if self.telegram_enabled and (not self.telegram_token or not self.telegram_chat_id):
            logger.warning("Telegram enabled but credentials missing - disabling")
            self.telegram_enabled = False
        
        if self.pushover_enabled:
            logger.info("Pushover notifications enabled")
        if self.telegram_enabled:
            logger.info("Telegram notifications enabled")
        
        # Debug: Log notification preferences
        logger.debug(f"Notification preferences: grid_loss={self.notify_grid_loss}, soc={self.notify_soc_warnings}, shutdown={self.notify_shutdown}, restored={self.notify_grid_restored}, system={self.notify_system}")
    
    def send(self, message: str, priority: int = 0, title: Optional[str] = None):
        """
        Send notification to all enabled services.
        
        Args:
            message: Notification message
            priority: Priority level (0=normal, 1=high, 2=emergency)
            title: Optional title (defaults to "EcoFlow Monitor")
        """
        logger.info(f"send() called - title='{title}', pushover={self.pushover_enabled}, telegram={self.telegram_enabled}")
        
        if not self.pushover_enabled and not self.telegram_enabled:
            logger.warning("send() - No notification services enabled, skipping")
            return
        
        title = title or "EcoFlow Monitor"
        
        # Send to Pushover
        if self.pushover_enabled:
            logger.info(f"Attempting Pushover notification: {title}")
            try:
                self._send_pushover(message, priority, title)
                logger.info(f"✅ Pushover notification sent successfully: {title}")
            except Exception as e:
                logger.error(f"❌ Pushover notification failed: {e}", exc_info=True)
        
        # Send to Telegram
        if self.telegram_enabled:
            logger.info(f"Attempting Telegram notification: {title}")
            try:
                self._send_telegram(message)
                logger.info(f"✅ Telegram notification sent successfully: {title}")
            except Exception as e:
                logger.error(f"❌ Telegram notification failed: {e}", exc_info=True)
    
    def _send_pushover(self, message: str, priority: int, title: str):
        """Send notification via Pushover API"""
        # Strip HTML tags for Pushover (plain text only)
        plain_message = re.sub(r'<[^>]+>', '', message)
        
        logger.debug(f"Pushover API call - user={self.pushover_user[:8]}***, message_len={len(plain_message)}")
        
        data = {
            "token": self.pushover_token,
            "user": self.pushover_user,
            "message": plain_message,
            "title": title,
            "priority": priority
        }
        
        # Emergency priority (2) requires retry and expire parameters
        if priority == 2:
            data["retry"] = 60  # Retry every 60 seconds
            data["expire"] = 3600  # Expire after 1 hour
        
        response = requests.post(
            "https://api.pushover.net/1/messages.json",
            data=data,
            timeout=5
        )
        logger.debug(f"Pushover response status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"Pushover API error response: {response.text}")
        response.raise_for_status()
        result = response.json()
        logger.debug(f"Pushover result: {result}")
        if result.get("status") != 1:
            raise Exception(f"Pushover API error: {result}")
    
    def _send_telegram(self, message: str):
        """Send notification via Telegram Bot API"""
        response = requests.post(
            f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
            json={
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=5
        )
        response.raise_for_status()
        logger.debug(f"Telegram sent: {message}")
    
    # High-level notification methods
    
    def grid_lost(self, device_name: str):
        """Notify that grid power was lost"""
        logger.info(f"grid_lost() called for device={device_name}, notify_grid_loss={self.notify_grid_loss}")
        if not self.notify_grid_loss:
            logger.warning(f"grid_lost() - notifications disabled, skipping")
            return
        message = f"⚠️ <b>Grid Power Lost</b>\n\nDevice: {device_name}\nBattery power active"
        self.send(message, priority=1, title="Power Outage")
    
    def soc_warning(self, device_name: str, soc: int, threshold: int):
        """Notify about low battery SOC"""
        logger.info(f"soc_warning() called for device={device_name}, soc={soc}, notify_soc_warnings={self.notify_soc_warnings}")
        if not self.notify_soc_warnings:
            logger.warning(f"soc_warning() - notifications disabled, skipping")
            return
        
        # Determine urgency
        if soc <= threshold:
            priority = 1  # High (critical)
            emoji = "🚨"
        elif soc <= threshold + 5:
            priority = 1  # High
            emoji = "⚠️"
        else:
            priority = 0  # Normal
            emoji = "🔋"
        
        message = (
            f"{emoji} <b>Battery Low</b>\n\n"
            f"Device: {device_name}\n"
            f"Current: {soc}%\n"
            f"Threshold: {threshold}%"
        )
        self.send(message, priority=priority, title="Battery Warning")
    
    def shutdown_sent(self, device_name: str, agents: List[str]):
        """Notify that shutdown commands were sent"""
        logger.info(f"shutdown_sent() called for device={device_name}, agents={agents}, notify_shutdown={self.notify_shutdown}")
        if not self.notify_shutdown:
            logger.warning(f"shutdown_sent() - notifications disabled, skipping")
            return
        
        agent_list = "\n".join([f"  • {agent}" for agent in agents])
        message = (
            f"🛑 <b>Shutdown Initiated</b>\n\n"
            f"Device: {device_name}\n"
            f"Agents:\n{agent_list}"
        )
        self.send(message, priority=1, title="Shutdown Command")
    
    def grid_restored(self, device_name: str):
        """Notify that grid power was restored"""
        logger.info(f"grid_restored() called for device={device_name}, notify_grid_restored={self.notify_grid_restored}")
        if not self.notify_grid_restored:
            logger.warning(f"grid_restored() - notifications disabled, skipping")
            return
        message = f"✅ <b>Grid Power Restored</b>\n\nDevice: {device_name}\nShutdown aborted"
        self.send(message, priority=0, title="Power Restored")
    
    def system_startup(self, version: str):
        """Notify that the system started"""
        logger.info(f"system_startup() called for version={version}, notify_system={self.notify_system}")
        if not self.notify_system:
            logger.warning(f"system_startup() - notifications disabled, skipping")
            return
        message = f"🚀 <b>System Started</b>\n\nVersion: {version}\nMonitoring active"
        self.send(message, priority=0, title="System Startup")
    
    def data_stale(self, device_name: str, minutes: int):
        """Notify that device data is stale"""
        logger.info(f"data_stale() called for device={device_name}, minutes={minutes}, notify_system={self.notify_system}")
        if not self.notify_system:
            logger.warning(f"data_stale() - notifications disabled, skipping")
            return
        message = (
            f"⚠️ <b>Device Data Stale</b>\n\n"
            f"Device: {device_name}\n"
            f"No updates for {minutes} minutes\n"
            f"Check device connection"
        )
        self.send(message, priority=1, title="Data Stale")
    
    def connection_issue(self, service: str, error: str):
        """Notify about connection problems"""
        logger.info(f"connection_issue() called for service={service}, notify_system={self.notify_system}")
        if not self.notify_system:
            logger.warning(f"connection_issue() - notifications disabled, skipping")
            return
        message = f"⚠️ <b>Connection Issue</b>\n\nService: {service}\nError: {error}"
        self.send(message, priority=1, title="Connection Problem")
