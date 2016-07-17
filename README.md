# Twilio

Plugin for the Indigo Home Automation system.

This plugin uses the Twilio service to send and receive SMS messages.

The twilio Python library is required.  To install, enter the following at a Terminal prompt.  You will need to enter your administrator password.

	sudo pip install twilio


### Broadcast Messages

    PluginID: com.flyingdiver.indigoplugin.twilio
    MessageType: messageReceived 
    Returns dictionary:
    {
    	'messageFrom':  	<text string>,
		'messageTo': 		<text string>,
		'messageText': 		<text string>
	}