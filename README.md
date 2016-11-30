# Twilio

Plugin for the Indigo Home Automation system.

This plugin uses the Twilio service to send and receive SMS messages.

The twilio Python library is required.  To install, enter the following at a Terminal prompt.  You will need to enter your administrator password.

	sudo pip install twilio
	
If you get an error saying pip is not installed, then do:

	sudo easy_install pip
	sudo pip install twilio


### Immediate Notifications

I've figured out how to process incoming SMS messages via Twilio without polling. In my testing, Indigo was getting the SMS content about 3 seconds after the SMS was sent to the Twilio number.

This method requires that your Indigo installation is accessible via HTTP. I did my testing using the Indigo Reflector. You may be able to get this to work with direct connections using port mapping, but I don't do that so I might not be able to help. This also requires that you have your Indigo remote login credentials (username and password) stored on the Twilio servers. I deemed this acceptable since I can use HTTPS to connect from Twilio to the reflector, and the reflector uses an encrypted connection to Indigo.

First, you need to install a Indigo Web Server (IWS) plugin. The Twilio plugin includes a simple IWS plugin. After downloading the new plugin, copy the "twilio" folder to your /Library/Application Support/Perceptive Automation/Indigo X/IndigoWebServer/plugins directory. 

See http://wiki.indigodomo.com/doku.php?id=indigo\_6\_documentation:iws\_plugin\_guide for more information. You will need to restart the Indigo server to enable the plugin.

Create a variable called "twilio\_ping", set it to "False". Then set up a trigger for that variable changing to "True". In the actions for the trigger, execute the Twilio "Check for Messages" action, and then set the twilio_ping variable to False (or anything other than True, really).

Next, go to your Twilo phone number dashboard: https://www.twilio.com/console/phone-numbers/dashboard. Click on the Twilio number you want notifications for. Under Messaging, make sure it's configured for Webhooks/TwiML. For inbound messages, put something like 

https://\<user>:\<password>@\<reflector>.goprism.com/twilio/ping

in the URL field with "HTTP GET" selected. Put in your Indigo remote access username and password, and your reflector subdomain name.

Now, anytime an inbound SMS is received by the Twilio servers, that URL will be fetched. That will cause the ping method in the twilio IWS plugin to be called. Which will set the twilio_ping variable to true. Trigger on change for that variable. Done.

### Broadcast Messages

    MessageType: messageReceived 
    Returns dictionary:
    {
    	'messageFrom':  	<text string>,
		'messageTo': 		<text string>,
		'messageText': 		<text string>
	}
	
    MessageType: messageSent 
    Returns dictionary:
    {
    	'messageFrom':  	<text string>,
		'messageTo': 		<text string>,
		'messageText': 		<text string>
	}
	
**PluginID**: com.flyingdiver.indigoplugin.twilio
