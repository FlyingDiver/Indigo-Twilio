#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import sys
import time
from datetime import datetime
import pytz
import urllib
import logging
import random
import string
import json

from twilio.rest import Client
from twilio.base.exceptions import TwilioException

kCurDevVersCount = 2        # current version of plugin devices

kAnyDevice      = "ANYDEVICE"
kOtherContact   = "OTHER-NON-CONTACT"

################################################################################
class Plugin(indigo.PluginBase):

    ########################################
    # Main Plugin methods
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        try:
            self.logLevel = int(self.pluginPrefs[u"logLevel"])
        except:
            self.logLevel = logging.INFO
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(u"logLevel = " + str(self.logLevel))

    def startup(self):
        self.logger.info(u"Starting Twilio")

        self.triggers = { }

        self.pollFrequency = float(self.pluginPrefs.get('pollFrequency', "10")) * 60.0
        self.logger.debug(u"pollFrequency = " + str(self.pollFrequency))
        self.next_poll = time.time()

        self.accountSID = self.pluginPrefs.get('accountSID', False)
        self.authToken = self.pluginPrefs.get('authToken', False)
        if self.accountSID and self.authToken:
            self.twilioClient = Client(self.accountSID, self.authToken)
            response = self.twilioClient.request('GET', 'https://api.twilio.com:8443')
            self.logger.debug(u"Twilio API Check response = {}".format(response))
            if response.status_code != 200:
                self.logger.warning(u"Twilio API Check failed.  Twilio will stop working when the next API version is implemented.")
        else:
            self.logger.warning(u"accountSID and/or authToken not set")
            self.twilioClient = None
                     
                     
    def shutdown(self):
        self.logger.info(u"Shutting down Twilio")


    def runConcurrentThread(self):

        try:
            while True:

                if self.twilioClient:
                    if (self.pollFrequency > 0.0) and (time.time() > self.next_poll):
                        self.next_poll = time.time() + self.pollFrequency
                        for dev in indigo.devices.iter("self"):
                            if (dev.deviceTypeId == "twilioNumber"):
                                self.checkMessages(dev)

                self.sleep(60.0)

        except self.StopThread:
            pass

    ####################

    def triggerStartProcessing(self, trigger):
        self.logger.debug("Adding Trigger %s (%d) - %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
        assert trigger.id not in self.triggers
        self.triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.logger.debug("Removing Trigger %s (%d)" % (trigger.name, trigger.id))
        assert trigger.id in self.triggers
        del self.triggers[trigger.id]

    def triggerCheck(self, device):

        for triggerId, trigger in sorted(self.triggers.iteritems()):
            self.logger.debug("Checking Trigger %s (%s), Type: %s" % (trigger.name, trigger.id, trigger.pluginTypeId))

            if (trigger.pluginProps["twilioNumber"] != str(device.id)) and (trigger.pluginProps["twilioNumber"] != kAnyDevice):
                self.logger.debug("\tSkipping Trigger %s (%s), wrong device: %s" % (trigger.name, trigger.id, device.id))

            if trigger.pluginTypeId == "messageReceived":
                indigo.trigger.execute(trigger)

            elif trigger.pluginTypeId == "patternMatch":
                matchType= trigger.pluginProps["matchType"]
                field = trigger.pluginProps["matchField"]
                pattern = trigger.pluginProps["matchString"]
                self.logger.debug("\tChecking field %s for pattern '%s' using %s" % (field, pattern, matchType))

                if matchType == "regexMatch":
                    cPattern = re.compile(pattern)
                    match = cPattern.search(device.states[field])
                    if match:
                        regexMatch = match.group()
                        self.logger.debug("\tExecuting regexMatch Trigger %s (%d), match: %s" % (trigger.name, trigger.id, matchResult))
                        device.updateStateOnServer(key="matchResult", value=regexMatch)
                        indigo.trigger.execute(trigger)
                    else:
                        self.logger.debug("\tNo regexMatch Match for Trigger %s (%d)" % (trigger.name, trigger.id))

                elif matchType == "exactMatch":
                    if pattern == device.states[field]:
                        self.logger.debug("\tExecuting exactMatch Trigger %s (%d)" % (trigger.name, trigger.id))
                        device.updateStateOnServer(key="matchResult", value=pattern)
                        indigo.trigger.execute(trigger)
                    else:
                        self.logger.debug("\tNo exactMatch Match for Trigger %s (%d)" % (trigger.name, trigger.id))

                elif matchType == "simpleMatch":
                    if pattern in device.states[field]:
                        self.logger.debug("\tExecuting simpleMatch Trigger %s (%d)" % (trigger.name, trigger.id))
                        indigo.trigger.execute(trigger)
                        device.updateStateOnServer(key="matchResult", value=pattern)
                    else:
                        self.logger.debug("\tNo simpleMatch Match for Trigger %s (%d)" % (trigger.name, trigger.id))

                else:
                    self.logger.warning("\tUnknown Match Type %s (%d), %s" % (trigger.name, trigger.id, trigger.pluginTypeId))

            else:
                self.logger.warning("\tUnknown Trigger Type %s (%d), %s" % (trigger.name, trigger.id, trigger.pluginTypeId))



    ####################
    def validatePrefsConfigUi(self, valuesDict):
        self.logger.debug(u"validatePrefsConfigUi called")
        errorDict = indigo.Dict()

        accountSID = valuesDict['accountSID']
        if len(accountSID) < 30:
            errorDict['accountSID'] = u"Enter Account SID from Twilio Console Dashboard"

        authToken = valuesDict['authToken']
        if len(authToken) < 30:
            errorDict['authToken'] = u"Enter Auth Token from Twilio Console Dashboard"

        if len(errorDict) > 0:
            return (False, valuesDict, errorDict)
        return (True, valuesDict)

    ########################################
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            try:
                self.logLevel = int(valuesDict[u"logLevel"])
            except:
                self.logLevel = logging.INFO
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(u"logLevel = " + str(self.logLevel))

            self.accountSID = valuesDict.get('accountSID', False)
            self.authToken = valuesDict.get('authToken', False)
            if self.accountSID and self.authToken:
                self.twilioClient = Client(self.accountSID, self.authToken)
            else:
                self.logger.warning(u"accountSID and/or authToken not set")

            self.pollFrequency = float(self.pluginPrefs.get('pollFrequency', "10")) * 60.0
            self.logger.debug(u"pollFrequency = " + str(self.pollFrequency))
            self.next_poll = time.time()


    ########################################
    # Called for each enabled Device belonging to plugin
    #
    def deviceStartComm(self, device):
        self.logger.debug(u'Called deviceStartComm(self, device): %s (%s)' % (device.name, device.id))

        instanceVers = int(device.pluginProps.get('devVersCount', 0))
        self.logger.debug(device.name + u": Device Current Version = " + str(instanceVers))

        if instanceVers >= kCurDevVersCount:
            self.logger.debug(device.name + u": Device Version is up to date")

        elif instanceVers < kCurDevVersCount:
            newProps = device.pluginProps
            newProps["devVersCount"] = kCurDevVersCount
            newProps["address"] = device.pluginProps["twilioNumber"]
            device.replacePluginPropsOnServer(newProps)
            self.logger.debug(u"deviceStartComm: Updated " + device.name + " to version " + str(kCurDevVersCount))

        else:
            self.logger.warning(u"Unknown device version: " + str(instanceVers) + " for device " + device.name)

        
        device.stateListOrDisplayStateIdChanged()
 

    ########################################
    # Terminate communication with servers
    #
    def deviceStopComm(self, device):
        self.logger.debug(u'Called deviceStopComm(self, device): %s (%s)' % (device.name, device.id))


    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        errorsDict = indigo.Dict()
        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    ########################################
    def validateActionConfigUi(self, valuesDict, typeId, devId):
        errorsDict = indigo.Dict()
        try:
            pass
        except:
            pass
        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

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
            self.logger.debug(u"sendSMS message '" + message + "' to " + to + " using " + smsDevice.name)
            self.twilioClient.messages.create(to=to, from_=smsNumber, body=message)
            smsDevice.updateStateOnServer(key="numberStatus", value="Message Sent")
            smsDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(u"sendSMS twilioClient.messages.create error: %s" % e)
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
            self.logger.debug(u"sendMMS message '" + message + "' to " + to + " using " + mmsDevice.name + " with " + str(urlList))
            self.twilioClient.messages.create(to=to, from_=mmsNumber, body=message, media_url=urlList)
            mmsDevice.updateStateOnServer(key="numberStatus", value="Message Sent")
            mmsDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(u"sendMMS twilioClient.messages.create error: %s" % e)
            mmsDevice.updateStateOnServer(key="numberStatus", value="Create Failure")
            mmsDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
        else:
            broadcastDict = {'messageFrom': mmsNumber, 'messageTo': to, 'messageText': message}
            indigo.server.broadcastToSubscribers(u"messageSent", broadcastDict)

    ########################################

    def voiceCallAction(self, pluginAction):
        callDevice = indigo.devices[pluginAction.deviceId]
        callTo = pluginAction.props["callTo"]
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
        to = indigo.activePlugin.substitute(callTo)
        callNumber = callDevice.pluginProps['twilioNumber']
        callURL = "http://twimlets.com/holdmusic?Bucket=" + bucket
        try:
            self.logger.debug(u"voiceCall call to " + callTo + " using " + callDevice.name + " with " + callURL)
            self.twilioClient.calls.create(to=callTo, from_=callNumber, url=callURL)
            callDevice.updateStateOnServer(key="numberStatus", value="Message Sent")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(u"voiceCall twilioClient.calls.create error: %s" % e)
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
        callURL = "http://twimlets.com/message?" + urllib.quote("Message[0]=" + message,"=")
        try:
            self.logger.debug(u"voiceMessage call to " + to + " using " + callDevice.name + " with " + callURL)
            self.twilioClient.calls.create(to=to, from_=callNumber, url=callURL)
            callDevice.updateStateOnServer(key="numberStatus", value="Message Sent")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(u"voiceMessage twilioClient.calls.create error: %s" % e)
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
        callURL = "https://studio.twilio.com/v1/Flows/{}/Engagements".format(flowSID)
        auth = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(16))
        params = {
            "auth": auth, 
            "message": message
        }
        try:
            self.logger.debug(u"doFlow call to {} using {} with {}".format(to, callDevice.name, flowSID))
            self.twilioClient.studio.flows(flowSID).engagements.create(to=to, from_=callNumber, parameters = json.dumps(params))
            callDevice.updateStateOnServer(key="last_auth", value=auth)
            callDevice.updateStateOnServer(key="numberStatus", value="Flow Activated")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        except Exception as e:
            self.logger.exception(u"doFlow twilioClient.studio.flows error: %s" % e)
            callDevice.updateStateOnServer(key="numberStatus", value="Flow Failure")
            callDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

    ########################################

    def checkMessagesAction(self, pluginAction, twilioDevice):
        self.checkMessages(twilioDevice)

    def checkMessages(self, twilioDevice):

        deleteMsgs = twilioDevice.pluginProps.get('delete', False)
        lastMessageStamp =  datetime.strptime(self.pluginPrefs.get(u"lastMessageStamp", "2000-01-01 00:00:00"), '%Y-%m-%d %H:%M:%S')
        messageStamp = lastMessageStamp

        try:
            for message in self.twilioClient.messages.list():
                self.logger.debug(u"checkMessages: Message from %s, to: %s, direction: %s, date_sent: '%s'" % (message.from_, message.to, message.direction, message.date_sent))
                if message.date_sent and (message.date_sent.replace(tzinfo=pytz.UTC) > lastMessageStamp.replace(tzinfo=pytz.UTC)):
                    messageStamp = message.date_sent
                    if message.direction == "inbound":
                        stateList = [   {'key':'messageFrom', 'value':message.from_},
                                        {'key':'messageTo',   'value':message.to},
                                        {'key':'messageText', 'value':message.body} ]
                        twilioDevice.updateStatesOnServer(stateList)
                        self.triggerCheck(twilioDevice)
                        broadcastDict = {'messageFrom': message.from_, 'messageTo': message.to, 'messageText': message.body}
                        indigo.server.broadcastToSubscribers(u"messageReceived", broadcastDict)

                if deleteMsgs:
                    try:
                        self.twilioClient.messages(message.sid).delete()
                    except TwilioException as e:
                        if e[0:6] == "HTTP 4":
                            self.logger.warning(u"checkMessages: twilioClient.messages.delete() error: %s" % e)
                        else:
                            self.logger.exception(u"checkMessages: twilioClient.messages.delete() error: %s" % e)

        except Exception as e:
            self.logger.exception(u"checkMessages: twilioClient.messages.list error: %s" % e)
            twilioDevice.updateStateOnServer(key="numberStatus", value="Error")
            twilioDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

        else:
            self.pluginPrefs[u"lastMessageStamp"] = messageStamp.strftime('%Y-%m-%d %H:%M:%S')
            twilioDevice.updateStateOnServer(key="numberStatus", value="Success")
            twilioDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
            self.logger.debug(u"checkMessages: Done")

    ########################################
    # Menu Methods
    ########################################

    def checkAllMessages(self):
        for dev in indigo.devices.iter("self"):
            if (dev.deviceTypeId == "twilioNumber"):
                self.checkMessages(dev)


    def listNotifications(self):
        for notification in self.twilioClient.notifications.list():
            print notification.more_info
            self.logger.debug(u"listNotifications: Date: %s, Level: %s, Code: %s" % (notification.message_date, notification.log, notification.error_code))


    def updateWebhooks(self):

        webhook_url = self.webhook_info.get("http", None)
        if not webhook_url:
            return    
        
        number_list = self.twilioClient.incoming_phone_numbers.list()
        for number in number_list:
            try:            
                updated = number.update(sms_url=webhook_url, sms_method = "GET")
                self.logger.info(u"Updated Webhook URL for {} to {}".format(updated.phone_number, updated.sms_url))            
            except TwilioException as e:
                self.logger.exception(u"{}: phone_number.update error: {}".format(number.phone_number, e))


    def pickTwilioNumber(self, filter=None, valuesDict=None, typeId=0, targetId=0):
        retList =[(kAnyDevice, "Any")]
        for dev in indigo.devices.iter("self"):
            if (dev.deviceTypeId == "twilioNumber"):
                twilioDevice = indigo.devices[dev.id]
                twilioNumber = twilioDevice.pluginProps['twilioNumber']
                self.logger.debug("pickTwilioNumber, dev.id = %s, dev.name = %s, twilioNumber = %s" % (dev.id, dev.name, twilioNumber))
                retList.append((dev.id,dev.name))
        retList.sort(key=lambda tup: tup[1])
        return retList

    def pickTwilioContact(self, filter=None, valuesDict=None, typeId=0, targetId=0):
        retList =[(kOtherContact, "Non-Contact Number")]
        for dev in indigo.devices.iter("self"):
            if (dev.deviceTypeId == "twilioContact"):
                contactDevice = indigo.devices[dev.id]
                contactNumber = contactDevice.pluginProps['contactNumber']
                self.logger.debug("pickTwilioContact, dev.id = %s, dev.name = %s, contactNumber = %s" % (dev.id, dev.name, contactNumber))
                retList.append((dev.id,dev.name))
        retList.sort(key=lambda tup: tup[1])
        return retList
