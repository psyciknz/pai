# Signal interface.
# Only exposes critical status changes and accepts commands
from pydbus import SystemBus
from gi.repository import GLib

import time
import logging
import datetime
import json

from threading import Thread, Event

from config_defaults import *
from config import *

logger = logging.getLogger('PAI').getChild(__name__)


class SignalInterface(Thread):
    """Interface Class using Signal"""

    signal = None
    alarm = None
    stop_running = Event()
    thread = None
    loop = None
    

    def stop(self):
        """ Stops the Pushbullet interface"""
        self.stop_running.set()
        if self.loop is not None:
            logger.info("Stopping Signal Interface")
            self.loop.quit()

    def event(self, raw):
        """Handle Live Event"""
        #logger.debug("Live Event: raw={}".format(raw))

        # TODO Improve message display
        if raw['type'] == 'Partition' or raw['type'] == 'System' or raw['type'] == 'Trouble':
            self.send_message(json.dumps(raw))
        

    def change(self, element, label, property, value):
        """Handle Property Change"""
        #logger.debug("Property Change: element={}, label={}, property={}, value={}".format(
        #    element,
        #    label,
        #    property,
        #    value))
        
        # TODO Improve message display
        if element == 'partition' or element == 'system' or element == 'trouble':
            self.send_message("{} {} {} {}".format(element, label, property, value))

       
    def set_alarm(self, alarm):
        self.alarm = alarm

    def run(self):
        logger.info("Starting Signal Interface")
        try:
            self.thread = Thread(target=self.loop)
            self.thread.start()
        except:
            logger.exception("PB")
            return False

        bus = SystemBus()
        while not self.stop_running.is_set():
            try:
                self.signal = bus.get('org.asamk.Signal')
                self.signal.onMessageReceived = self.handle_message
                self.loop = GLib.MainLoop()
                self.send_message("Active")

                logger.debug("Signal Interface Running")
                self.loop.run()
            except (KeyboardInterrupt, SystemExit):
                logger.info("Exit start")
                self.stop_running.set()
                self.loop.quit()
                self.stop()
            except:
                logger.exception("signal")
    
    def send_message(self, message):
        if self.signal is None:
            return

        for contact in SIGNAL_CONTACTS:
            self.signal.sendMessage(message, [], [contact])

    def handle_message (timestamp, source, groupID, message, attachments):
        """ Handle Signal message. It should be a command """

        logger.debug("Received Message {}".format(message))
        try:
            message = json.loads(str(message))
        except:
            logger.exception("Unable to parse message")
            return

        if self.alarm == None:
            return

        if source in SIGNAL_CONTACTS:
            ret = self.send_command(message)

            if ret:
                logger.info("From {} ACCEPTED: {}".format(p.get('sender_email_normalized'), message))
            else:
                logger.warning("From {} UNKNOWN: {}".format(p.get('sender_email_normalized'), message))
        else:
            logger.warning("Command from INVALID SENDER {}: {}".format(p.get('sender_email_normalized'), message))



    def send_command(self, message):
        """Handle message received from the MQTT broker"""
        """Format TYPE LABEL COMMAND """
        tokens = message.split(" ")

        if len(tokens) != 3:
            logger.warning("Message format is invalid")
            return

        if self.alarm == None:
            logger.error("No alarm registered")
            return

        element_type = tokens[0].lower()
        element = tokens[1]
        command = self.normalize_payload(tokens[2])
        
        # Process a Zone Command
        if element_type == 'zone':
            if command not in ['bypass', 'clear_bypass']:
                logger.error("Invalid command for Zone {}".format(command))
                return

            if not self.alarm.control_zone(element, command):
                logger.warning(
                    "Zone command refused: {}={}".format(element, command))

        # Process a Partition Command
        elif element_type == 'partition':
            if command not in ['arm', 'disarm', 'arm_stay', 'arm_sleep']:
                logger.error(
                    "Invalid command for Partition {}".format(command))
                return

            if not self.alarm.control_partition(element, command):
                logger.warning(
                    "Partition command refused: {}={}".format(element, command))
       
        # Process an Output Command
        elif element_type == 'output':
            if command not in ['on', 'off', 'pulse']:
                logger.error("Invalid command for Output {}".format(command))
                return

            if not self.alarm.control_output(element, command):
                logger.warning(
                    "Output command refused: {}={}".format(element, command))
        else:
            logger.error("Invalid control property {}".format(element))


    def normalize_payload(self, message):
        message = message.strip().lower()

        if message in ['true', 'on', '1', 'enable']:
            return 'on'
        elif message in ['false', 'off', '0', 'disable']:
            return 'off'
        elif message in ['pulse', 'arm', 'disarm', 'arm_stay', 'arm_sleep', 'bypass', 'clear_bypass']:
            return message

        return None

