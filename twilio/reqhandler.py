####################
import cherrypy
from indigopy.basereqhandler import BaseRequestHandler

####################
def PluginName():
	return u"Twilio Ping"

def PluginDescription():
	return u"This is the Twilio-Indigo Ping Plugin."

def ShowOnControlPageList():
	return False		# if True, then above name/description is shown on the Control Page list index
	
####################
class TwilioRequestHandler(BaseRequestHandler):

	def __init__(self, logFunc, debugLogFunc):
		BaseRequestHandler.__init__(self, logFunc, debugLogFunc)

	def ping(self, **params):
		cherrypy.server.indigoDb.VariableSetValue(cherrypy.server.indigoConn, "twilio_ping", "true")
		return
		
	ping.exposed = True
