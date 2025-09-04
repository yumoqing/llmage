from llmage.llmclient import (
	b64media,
	get_llm, 
	inference, 
	get_llmcatelogs,
	get_llms_by_catelog,
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
	env.b64media = b64media
	env.inference = inference
	env.get_llms_by_catelog = get_llms_by_catelog
	env.get_llmcatelogs = get_llmcatelogs
	env.default_sysmessage = default_sysmessage
	env.default_usrmessage = default_usrmessage
	env.default_llmmessage = default_llmmessage
	env.SessageMessages = SessionMessages
	env.BaseMessages = BaseMessages

