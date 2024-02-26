from inspect import *
import traceback
import yaml
import cdefw_global

class IfwDumper(yaml.Dumper):
	def increase_indent(self, flow=False, indentless=False):
		return super(IfwDumper, self).increase_indent(flow, False)

class IFWError(Exception):
	def __init__(self, msg='', arg=None, halt=False, nname=""):
		if not nname:
			nname = cdefw_global.get_node_name()
		self.node_name = nname
		self.msg = msg
		self.arg = arg
		self.halt = halt
		self.filename, self.lineno, self.function, self.code_context, self.index = getframeinfo(currentframe().f_back)
		exception_list = traceback.format_stack()
		exception_list = exception_list[:-2]
		exception_list.extend(traceback.format_tb(sys.exc_info()[2]))
		exception_list.extend(traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1]))
		self.stacktrace = exception_str = "Traceback (most recent call last):\n"
		self.stacktrace = "\n".join(exception_list)

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		output = {'IFWError': {'node-name': self.node_name,
				  'msg': self.msg, 'arg': self.arg,
				  'file name': self.filename,
				  'line number': self.lineno,
				  'function': self.function,
				  'stacktrace': self.stacktrace}}
		try:
			#y = yaml.dump(output, Dumper=IfwDumper, indent=2, sort_keys=False, default_style='', default_flow_style=False)
			y = yaml.dump(output, Dumper=IfwDumper, default_style='', default_flow_style=False)
		except Exception as e:
			print(type(e), e)
		return y

	def populate(self, node_name, msg, arg, halt, filename, lineno, function, code_context, index, stacktrace):
		self.node_name = node_name
		self.msg = msg
		self.arg = arg
		self.halt = halt
		self.filename = filename
		self.lineno = lineno
		self.function = function
		self.code_context = code_context
		self.index = index
		self.stacktrace = stacktrace

	def print_exception_info(self):
		print("Exception at: ", self.filename,":", self.lineno, ":", self.function)

	def print_error_msg(self):
		print(self.msg)

	def get_arg(self):
		return self.arg

class IFWCommError(IFWError):
	def __init__(self, msg='', arg=None, halt=False, nname=None):
		super().__init__(msg, arg, halt, nname)

class IFWAgentNotFound(IFWError):
	def __init__(self, msg='', arg=None, halt=False, nname=None):
		super().__init__(msg, arg, halt, nname)

class IFWInternalError(IFWError):
	def __init__(self, msg='', arg=None, halt=False, nname=None):
		super().__init__(msg, arg, halt, nname)

class IFWRemoteError(IFWError):
	def __init__(self, msg='', arg=None, halt=False, nname=cdefw_global.get_node_name()):
		super().__init__(msg, arg, halt, nname)

class IFWReserveError(IFWError):
	def __init__(self, msg='', arg=None, halt=False, nname=cdefw_global.get_node_name()):
		super().__init__(msg, arg, halt, nname)

class IFWOutOfResources(IFWError):
	def __init__(self, msg='', arg=None, halt=False, nname=cdefw_global.get_node_name()):
		super().__init__(msg, arg, halt, nname)

def defw_error_representer(dumper, data):
	mapping = {'node-name': data.node_name, 'msg': data.msg, 'arg': data.arg, 'halt': data.halt, 'filename': data.filename,
		   'lineno': data.lineno, 'function': data.function, 'code_context': data.code_context,
		   'index': data.index, 'stacktrace': data.stacktrace}
	return dumper.represent_mapping(u'!IFWError', mapping)

def defw_error_constructor(loader, node):
	value = loader.construct_mapping(node)
	defw_ex = IFWError()
	defw_ex.populate(value['node-name'], value['msg'], value['arg'], value['halt'], value['filename'], value['lineno'],
			 value['function'], value['code_context'], value['index'], value['stacktrace'])
	return defw_ex

yaml.add_representer(IFWError, defw_error_representer)
yaml.add_constructor(u'!IFWError', defw_error_constructor)