#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import sys
import time
from datetime import datetime
import urllib
import logging
import random
import string
import json
import threading

import pytz
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

kCurDevVersCount = 2  # current version of plugin devices

kAnyDevice = "ANYDEVICE"
kOtherContact = "OTHER-NON-CONTACT"


################################################################################
class Plugin(indigo.PluginBase):

    ########################################
    # Main Plugin methods
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s',
                                 datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        self.logLevel = int(self.pluginPrefs.get("logLevel", logging.INFO))
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(f"logLevel = {self.logLevel}")

        self.triggers = {}

        self.pollFrequency = float(pluginPrefs.get('pollFrequency', "10")) * 60.0
        self.logger.debug(f"pollFrequency = {self.pollFrequency}")
        self.next_poll = time.time()

        self.accountSID = pluginPrefs.get('accountSID', False)
        self.authToken = pluginPrefs.get('authToken', False)
        if self.accountSID and self.authToken:
            self.twilioClient = Client(self.accountSID, self.authToken)
        else:
            self.logger.warning("accountSID and/or authToken not set")
            self.twilioClient = None

    def startup(self):
        self.logger.info("Starting Twilio")

    def shutdown(self):
        self.logger.info("Shutting down Twilio")

    def runConcurrentThread(self):
        try:
            while True:
                if self.twilioClient:
                    if (self.pollFrequency > 0.0) and (time.time() > self.next_poll):
                        self.next_poll = time.time() + self.pollFrequency
                        for dev in indigo.devices.iter("self.twilioNumber"):
                            self.checkMessages(dev)
                self.sleep(60.0)

        except self.StopThread:
            pass

    ####################

    def triggerStartProcessing(self, trigger):
        self.logger.debug(f'Adding Trigger {trigger.name} ({trigger.id:d}) - {trigger.pluginTypeId}')
        assert trigger.id not in self.triggers
        self.triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.logger.debug(f'Removing Trigger {trigger.name} ({trigger.id:d})')
        assert trigger.id in self.triggers
        del self.triggers[trigger.id]

    def triggerCheck(self, device):

        for triggerId, trigger in sorted(self.triggers.items()):
            self.logger.debug(f'Checking Trigger {trigger.name} ({trigger.id}), Type: {trigger.pluginTypeId}')

            if (trigger.pluginProps["twilioNumber"] != str(device.id)) and (
                    trigger.pluginProps["twilioNumber"] != kAnyDevice):
                self.logger.debug(f'\tSkipping Trigger {trigger.name} ({trigger.id}), wrong device: {device.id}')

            if trigger.pluginTypeId == "messageReceived":
                indigo.trigger.execute(trigger)

            elif trigger.pluginTypeId == "patternMatch":
                matchType = trigger.pluginProps["matchType"]
                field = trigger.pluginProps["matchField"]
                pattern = trigger.pluginProps["matchString"]
                self.logger.debug(f'\tChecking field {field} for pattern \'{pattern}\' using {matchType}')

                if matchType == "regexMatch":
                    cPattern = re.compile(pattern)
                    match = cPattern.search(device.states[field])
                    if match:
                        regexMatch = match.group()
                        self.logger.debug(f'\tExecuting regexMatch Trigger {trigger.name} ({trigger.id:d}), match: {matchResult}')
                        device.updateStateOnServer(key="matchResult", value=regexMatch)
                        indigo.trigger.execute(trigger)
                    else:
                        self.logger.debug(f'\tNo regexMatch Match for Trigger {trigger.name} ({trigger.id:d})')

                elif matchType == "exactMatch":
                    if pattern == device.states[field]:
                        self.logger.debug(f'\tExecuting exactMatch Trigger {trigger.name} ({trigger.id:d})')
                        device.updateStateOnServer(key="matchResult", value=pattern)
                        indigo.trigger.execute(trigger)
                    else:
                        self.logger.debug(f'\tNo exactMatch Match for Trigger {trigger.name} ({trigger.id:d})')

                elif matchType == "simpleMatch":
                    if pattern in device.states[field]:
                        self.logger.debug(f'\tExecuting simpleMatch Trigger {trigger.name} ({trigger.id:d})')
                        indigo.trigger.execute(trigger)
                        device.updateStateOnServer(key="matchResult", value=pattern)
                    else:
                        self.logger.debug(f"\tNo simpleMatch Match for Trigger {trigger.name} ({trigger.id:d})")

                else:
                    self.logger.warning(f'\tUnknown Match Type {trigger.name} ({trigger.id:d}), {trigger.pluginTypeId}')

            else:
                self.logger.warning(f"\tUnknown Trigger Type {trigger.name} ({trigger.id:d}), {trigger.pluginTypeId}")

    ####################
    def validatePrefsConfigUi(self, valuesDict):
        self.logger.debug(u"validatePrefsConfigUi called")
        errorDict = indigo.Dict()

        accountSID = valuesDict['accountSID']
        if len(accountSID) < 30:
            errorDict['accountSID'] = "Enter Account SID from Twilio Console Dashboard"

        authToken = valuesDict['authToken']
        if len(authToken) < 30:
            errorDict['authToken'] = "Enter Auth Token from Twilio Console Dashboard"

        if len(errorDict) > 0:
            return False, valuesDict, errorDict
        return True, valuesDict

    ########################################
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.logLevel = valuesDict.get(u"logLevel", logging.INFO)
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(f"logLevel = {self.logLevel}")

            self.accountSID = valuesDict.get('accountSID', False)
            self.authToken = valuesDict.get('authToken', False)
            if self.accountSID and self.authToken:
                self.twilioClient = Client(self.accountSID, self.authToken)
            else:
                self.logger.warning("accountSID and/or authToken not set")

            self.pollFrequency = float(self.pluginPrefs.get('pollFrequency', "10")) * 60.0
            self.logger.debug(f"pollFrequency = {str(self.pollFrequency)}")
            self.next_poll = time.time()

    ########################################
    # Called for each enabled Device belonging to plugin
    #
    def deviceStartComm(self, device):
        self.logger.debug(f'Called deviceStartComm(self, device): {device.name} ({device.id})')

        instanceVers = int(device.pluginProps.get('devVersCount', 0))
        self.logger.debug(f"{device.name}: Device Current Version = {instanceVers}")

        if instanceVers >= kCurDevVersCount:
            self.logger.debug(f"{device.name}: Device Version is up to date")

        elif instanceVers < kCurDevVersCount:
            newProps = device.pluginProps
            newProps["devVersCount"] = kCurDevVersCount

            if device.deviceTypeId == 'twilioNumber':
                newProps["address"] = device.pluginProps["twilioNumber"]

            device.replacePluginPropsOnServer(newProps)
            self.logger.debug(f'deviceStartComm: Updated {device.name} to version {kCurDevVersCount}')

        else:
            self.logger.warning(f'Unknown device version: {instanceVers} for device {device.name}')

        device.stateListOrDisplayStateIdChanged()

    ########################################
    # Terminate communication with servers
    #
    def deviceStopComm(self, device):
        self.logger.debug(f'Called deviceStopComm(self, device): {device.name} ({device.id})')

    ########################################
    # Plugin Actions object callbacks
    ########################################

    def sendSMSAction(self, pluginAction):
        smsDevice = indigo.devices[pluginAction.deviceId]
        smsMessage = pluginAction.props["smsMessage"]
        if pluginAction.props.get("twilioContact", kOtherContact) == kOtherContact:
            smsTo = pluginAction.props["smsTo"]
        else:
            contactID = int(pluginAction.props["twilioContact"])
            contactDevice = indigo.devices[contactID]
            smsTo = contactDevice.pluginProps['contactNumber']
        self.sendSMS(smsDevice, smsTo, smsMessage)

    def sendSMS(self, smsDevice, smsTo, smsMessage):
        smsNumber = smsDevice.pluginProps['twilioNumber']
        to = indigo.activePlugin.substitute(smsTo)
        message = indigo.activePlugin.substitute(smsMessage)

        try:
            self.logger.debug(f"sendSMS message '{message}' to {to} using {smsDevice.name}")
            self.twilioClient.messages.create(to=to, from_=smsNumber, body=message)
            smsDevice.updateStateOnServer(key="numberStatus", value="Message Sent")
            smsDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(f"sendSMS twilioClient.messages.create error: {e}")
            smsDevice.updateStateOnServer(key="numberStatus", value="Create Failure")
            smsDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
        else:
            broadcastDict = {'messageFrom': smsNumber, 'messageTo': to, 'messageText': message}
            indigo.server.broadcastToSubscribers(u"messageSent", broadcastDict)

    ########################################

    def sendMMSAction(self, pluginAction):
        mmsDevice = indigo.devices[pluginAction.deviceId]
        mmsMessage = pluginAction.props["mmsMessage"]
        mmsUrl = pluginAction.props["mmsUrl"]
        if pluginAction.props.get("twilioContact", kOtherContact) == kOtherContact:
            mmsTo = pluginAction.props["mmsTo"]
        else:
            contactID = int(pluginAction.props["twilioContact"])
            contactDevice = indigo.devices[contactID]
            mmsTo = contactDevice.pluginProps['contactNumber']
        self.sendMMS(mmsDevice, mmsTo, mmsMessage, mmsUrl)

    def sendMMS(self, mmsDevice, mmsTo, mmsMessage, mmsUrl):
        mmsNumber = mmsDevice.pluginProps['twilioNumber']
        to = indigo.activePlugin.substitute(mmsTo)
        message = indigo.activePlugin.substitute(mmsMessage)
        urls = indigo.activePlugin.substitute(mmsUrl)
        urlList = urls.split(",")

        try:
            self.logger.debug(f"sendMMS message '{message}' to {to} using {mmsDevice.name} with {urlList}")
            self.twilioClient.messages.create(to=to, from_=mmsNumber, body=message, media_url=urlList)
            mmsDevice.updateStateOnServer(key="numberStatus", value="Message Sent")
            mmsDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(f"sendMMS twilioClient.messages.create error: {e}")
            mmsDevice.updateStateOnServer(key="numberStatus", value="Create Failure")
            mmsDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
        else:
            broadcastDict = {'messageFrom': mmsNumber, 'messageTo': to, 'messageText': message}
            indigo.server.broadcastToSubscribers(u"messageSent", broadcastDict)

    ########################################

    def voiceCallAction(self, pluginAction):
        callDevice = indigo.devices[pluginAction.deviceId]
        musicBucket = pluginAction.props["bucket"]
        if pluginAction.props.get("twilioContact", kOtherContact) == kOtherContact:
            callTo = pluginAction.props["callTo"]
        else:
            contactID = int(pluginAction.props["twilioContact"])
            contactDevice = indigo.devices[contactID]
            callTo = contactDevice.pluginProps['contactNumber']
        self.voiceCall(callDevice, callTo, musicBucket)

    def voiceCall(self, callDevice, callTo, musicBucket):
        bucket = indigo.activePlugin.substitute(musicBucket)
        callNumber = callDevice.pluginProps['twilioNumber']
        callURL = "https://twimlets.com/holdmusic?Bucket=" + bucket
        try:
            self.logger.debug(f"voiceCall call to {callTo} using {callDevice.name} with {callURL}")
            self.twilioClient.calls.create(to=callTo, from_=callNumber, url=callURL)
            callDevice.updateStateOnServer(key="numberStatus", value="Message Sent")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(f"voiceCall twilioClient.calls.create error: {e}")
            callDevice.updateStateOnServer(key="numberStatus", value="Create Failure")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

    ########################################

    def voiceMessageAction(self, pluginAction):
        callDevice = indigo.devices[pluginAction.deviceId]
        messageText = pluginAction.props["messageText"]
        if pluginAction.props.get("twilioContact", kOtherContact) == kOtherContact:
            callTo = pluginAction.props["callTo"]
        else:
            contactID = int(pluginAction.props["twilioContact"])
            contactDevice = indigo.devices[contactID]
            callTo = contactDevice.pluginProps['contactNumber']
        self.voiceMessage(callDevice, callTo, messageText)

    def voiceMessage(self, callDevice, callTo, messageText):
        to = indigo.activePlugin.substitute(callTo)
        message = indigo.activePlugin.substitute(messageText)
        callNumber = callDevice.pluginProps['twilioNumber']
        callURL = "https://twimlets.com/message?" + urllib.parse.quote("Message[0]=" + message, "=")
        try:
            self.logger.debug(f"voiceMessage call to {to} using {callDevice.name} with {callURL}")
            self.twilioClient.calls.create(to=to, from_=callNumber, url=callURL)
            callDevice.updateStateOnServer(key="numberStatus", value="Message Sent")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(f"voiceMessage twilioClient.calls.create error: {e}")
            callDevice.updateStateOnServer(key="numberStatus", value="Create Failure")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

    ########################################

    def doFlowAction(self, pluginAction):
        callDevice = indigo.devices[pluginAction.deviceId]
        flowSID = pluginAction.props["flowSID"]
        flowMessage = pluginAction.props["flowMessage"]
        if pluginAction.props.get("twilioContact", kOtherContact) == kOtherContact:
            callTo = pluginAction.props["callTo"]
        else:
            contactID = int(pluginAction.props["twilioContact"])
            contactDevice = indigo.devices[contactID]
            callTo = contactDevice.pluginProps['contactNumber']
        self.doFlow(callDevice, callTo, flowSID, flowMessage)

    def doFlow(self, callDevice, callTo, flowSID, flowMessage):
        to = indigo.activePlugin.substitute(callTo)
        message = indigo.activePlugin.substitute(flowMessage)
        callNumber = callDevice.pluginProps['twilioNumber']
        callURL = f"https://studio.twilio.com/v1/Flows/{flowSID}/Engagements"
        auth = ''.join(
            random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(16))
        params = {
            "auth": auth,
            "message": message
        }
        try:
            self.logger.debug(f"doFlow call to {to} using {callDevice.name} with {flowSID}")
            self.twilioClient.studio.flows(flowSID).engagements.create(to=to, from_=callNumber,
                                                                       parameters=json.dumps(params))
            callDevice.updateStateOnServer(key="last_auth", value=auth)
            callDevice.updateStateOnServer(key="numberStatus", value="Flow Activated")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(f"doFlow twilioClient.studio.flows error: {e}")
            callDevice.updateStateOnServer(key="numberStatus", value="Flow Failure")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

    ########################################

    def checkMessagesAction(self, pluginAction, twilioDevice):
        self.checkMessages(twilioDevice)

    def checkMessages(self, twilioDevice):

        deleteMsgs = twilioDevice.pluginProps.get('delete', False)
        lastMessageStamp = datetime.strptime(self.pluginPrefs.get(u"lastMessageStamp", "2000-01-01 00:00:00"),'%Y-%m-%d %H:%M:%S')
        self.logger.debug(f"checkMessages: checking {twilioDevice.name}, lastMessageStamp {lastMessageStamp}")
        messageStamp = lastMessageStamp

        try:
            for message in self.twilioClient.messages.list(to=twilioDevice.address):
                self.logger.debug(f"checkMessages: Message from {message.from_}, to: {message.to}, direction: {message.direction}, date_sent: '{message.date_sent}'")
                if message.date_sent and (
                        message.date_sent.replace(tzinfo=pytz.UTC) > lastMessageStamp.replace(tzinfo=pytz.UTC)):
                    messageStamp = message.date_sent
                    if message.direction == "inbound":
                        stateList = [{'key': 'messageFrom', 'value': message.from_},
                                     {'key': 'messageTo', 'value': message.to},
                                     {'key': 'messageText', 'value': message.body}]
                        twilioDevice.updateStatesOnServer(stateList)
                        self.triggerCheck(twilioDevice)
                        broadcastDict = {'messageFrom': message.from_, 'messageTo': message.to,
                                         'messageText': message.body}
                        indigo.server.broadcastToSubscribers(u"messageReceived", broadcastDict)

                    if deleteMsgs:
                        try:
                            self.twilioClient.messages(message.sid).delete()
                        except TwilioException as e:
                            if e[0:6] == "HTTP 4":
                                self.logger.warning(f"checkMessages: twilioClient.messages.delete() error: {e}")
                            else:
                                self.logger.exception(f"checkMessages: twilioClient.messages.delete() error: {e}")

        except Exception as e:
            self.logger.exception(f"checkMessages: twilioClient.messages.list error: {e}")
            twilioDevice.updateStateOnServer(key="numberStatus", value="Error")
            twilioDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

        else:
            self.pluginPrefs[u"lastMessageStamp"] = messageStamp.strftime('%Y-%m-%d %H:%M:%S')
            twilioDevice.updateStateOnServer(key="numberStatus", value="Success")
            twilioDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
            self.logger.debug(u"checkMessages: Done")

    ########################################
    # Indigo 2021 HTTP Request handling
    # Call as:  https://myreflector.indigodomo.net/message/com.flyingdiver.indigoplugin.twilio/check_messages?api_key=XXXX
    ########################################

    def checkMessagesWebHook(self, action, dev=None, callerWaitingForResult=None):
        self.logger.debug(f"webHook activated, props = {action.props}")

        # run check in separate thread.  Allows immediate return to server, and delay for Twilio bug
        threading.Timer(3.0, lambda: self.checkAllMessages()).start()
        return "200"

    ########################################
    # Menu Methods
    ########################################

    def checkAllMessages(self):
        for dev in indigo.devices.iter("self.twilioNumber"):
            if dev.enabled:
                self.checkMessages(dev)

    def pickTwilioNumber(self, filter_arg=None, valuesDict=None, typeId=0, targetId=0):
        retList = [(kAnyDevice, "Any")]
        for dev in indigo.devices.iter("self.twilioNumber"):
            self.logger.debug(f"pickTwilioNumber, dev.id = {dev.id}, dev.name = {dev.name}")
            retList.append((dev.id, dev.name))
        retList.sort(key=lambda tup: tup[1])
        return retList

    def pickTwilioContact(self, filter_arg=None, valuesDict=None, typeId=0, targetId=0):
        retList = [(kOtherContact, "Non-Contact Number")]
        for dev in indigo.devices.iter("self.twilioContact"):
            self.logger.debug(f"pickTwilioContact, dev.id = {dev.id}, dev.name = {dev.name}")
            retList.append((dev.id, dev.name))
        retList.sort(key=lambda tup: tup[1])
        return retList
