from appPublic.base64_to_file import hex2base64
from appPublic.registerfunction import RegisterFunction
from llmage.jimeng import jimeng_auth_headers
from llmage.keling import keling_token

from llmage.llmclient import (
	b64media2url,
	get_llm, 
	inference, 
	get_llmcatelogs,
	get_llms_by_catelog
)
from llmage.messages import (
	BaseMessages,
	SessionMessages,
	default_sysmessage,
	default_usrmessage,
	default_llmmessage
)
from ahserver.serverenv import ServerEnv

def load_llmage():
	env = ServerEnv()
	env.get_llm = get_llm
	env.b64media2url = b64media2url
	env.hex2base64 = hex2base64
	env.inference = inference
	env.get_llms_by_catelog = get_llms_by_catelog
	env.get_llmcatelogs = get_llmcatelogs
	env.default_sysmessage = default_sysmessage
	env.default_usrmessage = default_usrmessage
	env.default_llmmessage = default_llmmessage
	env.SessageMessages = SessionMessages
	env.BaseMessages = BaseMessages
	env.keling_token = keling_token
	
	rf = RegisterFunction()
	rf.register('jimeng_auth_headers', jimeng_auth_headers)
