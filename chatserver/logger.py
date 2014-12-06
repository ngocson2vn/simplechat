class Logger:
	def __init__(self):
		self.log_file = '/tmp/chatserver.log'
		self.stream = open(self.log_file, 'a')
		self.closed = False

	def log(self, message):
		self.stream.write(message + "\n")
		self.stream.flush()

	def close(self):
		if not self.closed:
			self.stream.close()
			self.closed = True