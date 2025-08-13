from llmage.llmclient import get_llm, inference, get_llmcatelogs, \
	get_llms_by_catelog
from ahserver.serverenv import ServerEnv

def load_llmage():
	env = ServerEnv()
	env.get_llm = get_llm
	env.inference = inference
	env.get_llms_by_catelog = get_llms_by_catelog
	env.get_llmcatelogs = get_llmcatelogs

