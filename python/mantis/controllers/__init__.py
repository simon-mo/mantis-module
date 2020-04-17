from mantis.controllers.bangbang import BangBang
from mantis.controllers.debug import DoNothingController, RandomAddAndDelete
from mantis.controllers.pid import PIDController

registry = {
    "pid": PIDController,
    "bangbang": BangBang,
    "do_nothing": DoNothingController,
    "random": RandomAddAndDelete,
}
