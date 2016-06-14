#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import sys
import time
from datetime import datetime
import urllib

from twilio.rest import TwilioRestClient 
from twilio import TwilioRestException
from ghpu import GitHubPluginUpdater

kCurDevVersCount = 0		# current version of plugin devices			

kAnyDevice	= "ANYDEVICE"

################################################################################
class Plugin(indigo.PluginBase):
					
	########################################
	# Main Plugin methods
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		
		self.debug = self.pluginPrefs.get(u"showDebugInfo", False)
		self.debugLog(u"Debugging enabled")

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def startup(self):
		indigo.server.log(u"Starting Twilio")
		
		self.triggers = { }

		self.updater = GitHubPluginUpdater(self)
		self.updateFrequency = self.pluginPrefs.get('updateFrequency', 24)
		if self.updateFrequency > 0:
			self.next_update_check = time.time()

		self.pollFrequency = self.pluginPrefs.get('pollFrequency', 10)
		if self.pollFrequency > 0:
			self.next_poll = time.time()

		self.accountSID = self.pluginPrefs.get('accountSID', False)
		self.authToken = self.pluginPrefs.get('authToken', False)
		if self.accountSID and self.authToken:
			self.twilioClient = TwilioRestClient(self.accountSID, self.authToken) 


	def shutdown(self):
		indigo.server.log(u"Shutting down Twilio")


	def runConcurrentThread(self):
		
		try:
			while True:
											
				if self.updateFrequency > 0:
					if time.time() > self.next_update_check:
						self.next_update_check = time.time() + float(self.pluginPrefs['updateFrequency']) * 60.0 * 60.0
						self.updater.checkForUpdate()

				if self.twilioClient:
					if self.pollFrequency > 0:
						if time.time() > self.next_poll:
							self.next_poll = time.time() + float(self.pluginPrefs['pollFrequency']) * 60.0					
							for dev in indigo.devices.iter("self"):
								if (dev.deviceTypeId == "twilioNumber"): 
									self.checkMessages(dev)
					
				self.sleep(1.0) 
								
		except self.stopThread:
			pass	  
	
	####################

	def triggerStartProcessing(self, trigger):
		self.debugLog("Adding Trigger %s (%d) - %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
		assert trigger.id not in self.triggers
		self.triggers[trigger.id] = trigger
 
	def triggerStopProcessing(self, trigger):
		self.debugLog("Removing Trigger %s (%d)" % (trigger.name, trigger.id))
		assert trigger.id in self.triggers
		del self.triggers[trigger.id] 
		
	def triggerCheck(self, device):

		for triggerId, trigger in sorted(self.triggers.iteritems()):
			self.debugLog("\tChecking Trigger %s (%s), Type: %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
			
			if (trigger.pluginProps["twilioNumber"] != str(device.id)) and (trigger.pluginProps["twilioNumber"] != kAnyDevice):
				self.debugLog("\t\tSkipping Trigger %s (%s), wrong device: %s" % (trigger.name, trigger.id, device.id))

			elif trigger.pluginTypeId != "patternMatch":
				self.debugLog("\tUnknown Trigger Type %s (%d), %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
			
			else:
				matchType= trigger.pluginProps["matchType"]
				field = trigger.pluginProps["matchField"]
				pattern = trigger.pluginProps["matchString"]
				self.debugLog("\tChecking field %s for pattern '%s' using %s" % (field, pattern, matchType))
				
				if matchType == "regexMatch":
					cPattern = re.compile(pattern)
					match = cPattern.search(device.states[field])
					if match:
						regexMatch = match.group()
						self.debugLog("\tExecuting regexMatch Trigger %s (%d), match: %s" % (trigger.name, trigger.id, regexMatch))
						device.updateStateOnServer(key="regexMatch", value=regexMatch)
						indigo.trigger.execute(trigger)
					else:
						self.debugLog("\tNo regexMatch Match for Trigger %s (%d)" % (trigger.name, trigger.id))
						
				elif matchType == "exactMatch":
					if pattern == device.states[field]:
						self.debugLog("\tExecuting exactMatch Trigger %s (%d)" % (trigger.name, trigger.id))
						indigo.trigger.execute(trigger)
					else:
						self.debugLog("\tNo exactMatch Match for Trigger %s (%d)" % (trigger.name, trigger.id))
						
				elif matchType == "simpleMatch":
					if pattern in device.states[field]:
						self.debugLog("\tExecuting simpleMatch Trigger %s (%d)" % (trigger.name, trigger.id))
						indigo.trigger.execute(trigger)
					else:
						self.debugLog("\tNo simpleMatch Match for Trigger %s (%d)" % (trigger.name, trigger.id))
						
				else:
					self.debugLog("\tUnknown Match Type %s (%d), %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
			
	
	####################
	def validatePrefsConfigUi(self, valuesDict):
		self.debugLog(u"validatePrefsConfigUi called")
		errorDict = indigo.Dict()

		updateFrequency = int(valuesDict['updateFrequency'])
		if (updateFrequency < 0) or (updateFrequency > 24):
			errorDict['updateFrequency'] = u"Update frequency is invalid - enter a valid number (between 0 and 24)"

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
			self.debug = valuesDict.get("showDebugInfo", False)
			if self.debug:
				self.debugLog(u"Debug logging enabled")
			else:
				self.debugLog(u"Debug logging disabled")

			self.accountSID = valuesDict.get('accountSID', False)
			self.authToken = valuesDict.get('authToken', False)
			if self.accountSID and self.authToken:
				self.twilioClient = TwilioRestClient(self.accountSID, self.authToken) 

	########################################
	# Called for each enabled Device belonging to plugin
	# Verify connectivity to servers and start polling IMAP/POP servers here
	#
	def deviceStartComm(self, device):
		self.debugLog(u'Called deviceStartComm(self, device): %s (%s)' % (device.name, device.id))
						
		instanceVers = int(device.pluginProps.get('devVersCount', 0))
		self.debugLog(device.name + u": Device Current Version = " + str(instanceVers))

		if instanceVers >= kCurDevVersCount:
			self.debugLog(device.name + u": Device Version is up to date")
			
		elif instanceVers < kCurDevVersCount:
			newProps = device.pluginProps

		else:
			self.errorLog(u"Unknown device version: " + str(instanceVers) + " for device " + device.name)					


	########################################
	# Terminate communication with servers
	#
	def deviceStopComm(self, device):
		self.debugLog(u'Called deviceStopComm(self, device): %s (%s)' % (device.name, device.id))
		
 
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
		smsTo = pluginAction.props["smsTo"]
		smsMessage = pluginAction.props["smsMessage"]
		self.sendSMS(smsDevice, smsTo, smsMessage)

	def sendSMS(self, smsDevice, smsTo, smsMessage):
		smsNumber = smsDevice.pluginProps['twilioNumber']
		fullMessage = indigo.activePlugin.substitute(smsMessage)
		
		try:
			self.debugLog(u"sendSMS message '" + fullMessage + "' to " + smsTo + " using " + smsDevice.name)
			self.twilioClient.messages.create(to=smsTo, from_=smsNumber, body=fullMessage) 
		except TwilioRestException as e:
			self.debugLog(u"sendSMS twilioClient.messages.create error: %s" % e)

	########################################

	def voiceCallAction(self, pluginAction):
		callDevice = indigo.devices[pluginAction.deviceId]
		callTo = pluginAction.props["callTo"]
		bucket = pluginAction.props["bucket"]
		self.voiceCall(callDevice, callTo, bucket)

	def voiceCall(self, callDevice, callTo, bucket):
		callNumber = callDevice.pluginProps['twilioNumber']
		callURL = "http://twimlets.com/holdmusic?Bucket=" + bucket
		try:
			self.debugLog(u"voiceCall call to " + callTo + " using " + callDevice.name + " with " + callURL)
			self.twilioClient.calls.create(to=callTo, from_=callNumber, url=callURL)
		except TwilioRestException as e:
			self.debugLog(u"voiceCall twilioClient.calls.create error: %s" % e)

	########################################

	def voiceMessageAction(self, pluginAction):
		callDevice = indigo.devices[pluginAction.deviceId]
		callTo = pluginAction.props["callTo"]
		messageText = pluginAction.props["messageText"]
		self.voiceMessage(callDevice, callTo, messageText)

	def voiceMessage(self, callDevice, callTo, messageText):
		callNumber = callDevice.pluginProps['twilioNumber']
		callURL = "http://twimlets.com/message?" + urllib.quote("Message[0]=" + messageText,"=")
		try:
			self.debugLog(u"voiceMessage call to " + callTo + " using " + callDevice.name + " with " + callURL)
			self.twilioClient.calls.create(to=callTo, from_=callNumber, url=callURL)
		except TwilioRestException as e:
			self.debugLog(u"voiceMessage twilioClient.calls.create error: %s" % e)

	########################################

	def checkMessagesAction(self, pluginAction):
		twilioDevice = indigo.devices[pluginAction.deviceId]
		self.checkMessages(twilioDevice)
	
	def checkAllMessages(self):
		for dev in indigo.devices.iter("self"):
			self.checkMessages(dev)

	def checkMessages(self, twilioDevice):
		smsNumber = twilioDevice.pluginProps['twilioNumber']
		deleteMsgs = twilioDevice.pluginProps['delete']
		lastMessageStamp =	datetime.strptime(self.pluginPrefs.get(u"lastMessageStamp", "2000-01-01 00:00:00"), '%Y-%m-%d %H:%M:%S')
		messageStamp = lastMessageStamp
		self.debugLog(u"checkMessages: lastMessageStamp: %s" % str(lastMessageStamp))
		
		try:
			for message in self.twilioClient.messages.list():
				self.debugLog(u"checkMessages: Message from %s, to: %s, direction: %s, date_sent: '%s'" % (message.from_, message.to, message.direction, message.date_sent))
				if message.date_sent > lastMessageStamp:
					if message.date_sent > messageStamp:
						messageStamp = message.date_sent
						self.debugLog(u"checkMessages: new messageStamp: %s" % str(messageStamp))
					if message.direction == "inbound":
						twilioDevice.updateStateOnServer(key="messageFrom", value=message.from_)					
						twilioDevice.updateStateOnServer(key="messageTo", value=message.to)					
						twilioDevice.updateStateOnServer(key="messageText", value=message.body)
						self.triggerCheck(twilioDevice)
					
				if deleteMsgs:
					try:
						self.twilioClient.messages.delete(message.sid)
					except TwilioRestException as e:
						self.debugLog(u"checkMessages twilioClient.messages.delete error: %s" % e)

			self.pluginPrefs[u"lastMessageStamp"] = messageStamp.strftime('%Y-%m-%d %H:%M:%S')
			self.debugLog(u"checkMessages: lastMessageStamp: %s" % self.pluginPrefs[u"lastMessageStamp"])
			
		except TwilioRestException as e:
			self.debugLog(u"checkMessages twilioClient.messages.list error: %s" % e)
					
	########################################
	# Menu Methods
	########################################

	def toggleDebugging(self):
		self.debug = not self.debug
		self.pluginPrefs["debugEnabled"] = self.debug
		indigo.server.log("Debug set to: " + str(self.debug))
		
	def checkForUpdates(self):
		self.updater.checkForUpdate()

	def updatePlugin(self):
		self.updater.update()

	def forceUpdate(self):
		self.updater.update(currentVersion='0.0.0')

		
	def pickTwilioNumber(self, filter=None, valuesDict=None, typeId=0, targetId=0):
		retList =[(kAnyDevice, "Any")]
		for dev in indigo.devices.iter("self"):
			if (dev.deviceTypeId == "twilioNumber"): 
				retList.append((dev.id,dev.name))
		retList.sort(key=lambda tup: tup[1])
		return retList


	########################################
	# ConfigUI methods
	########################################


	def validateActionConfigUi(self, valuesDict, typeId, actionId):
		errorDict = indigo.Dict()

		if len(errorDict) > 0:
			return (False, valuesDict, errorDict)
		else:
			return (True, valuesDict)
	

