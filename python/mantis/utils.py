class LogEvery:
    def __init__(self, every):
        self.every = every
        self.count = 0

    def log(self, msg):
        self.count += 1
        if (self.count % self.every) == 0:
            print("[{}] {}".format(self.count, msg))
