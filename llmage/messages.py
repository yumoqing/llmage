from appPublic.myTE import MyTemplateEngine

def default_sysmessage():
	return """{
		"role":"system",
		"content":"{{content}}"
	}"""

def default_usrmessage():
	return """{
		"role":"user",
		"content":"{{prompt}}"
	}"""

def default_llmmessage():
	return """{
		"role":"assisant",
		"content":"{{content}}"
	}"""

class BaseMessages:
	def __init__(self, request, llmid, sys_message, usr_message, llm_message):
		self.request = request
		self.llmid = llmid
		self.sys_message = sys_message
		self.usr_message = usr_message
		self.llm_message = llm_message
		self.te = MyTemplateEngine([])
		
	async def append_meessages(self, msg_format, **kw):
		m = self.te.renders(msg_format, kw)
		msgs = await self.get_messages()
		msgs.append(m)
		await self.set_message(msgs)
		return msgs
	
	async def append_usr_messages(self, **kw):
		return await self.append_messages(self.usr_message, **kw)
	
	async def append_sys_messages(self, **kw):
		return await self.append_messages(self.sys_message, **kw)
	
	async def append_llm_messages(self, **kw):
		return await self.append_messages(self.llm_message, **kw)
	
	async def get_messages(self):
		return []
	
	async def set_messages(self, msgs):
		pass

class SessionMessages(BaseMessages):
	async def get_messages(self):
		env = self.request._run_ns
		s = await env.get_session()
		userid = await env.get_user()
		mk = f'{self.llmid}_{userid}_msgs'
		msgs = s[mk]
		if not msgs:
			msgs = []
		return msgs

	async def set_messages(self, msgs):
        env = self.request._run_ns
        s = await env.get_session()
        userid = await env.get_user()
        mk = f'{self.llmid}_{userid}_msgs'
		s[mk] = msgs
		
