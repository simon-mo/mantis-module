from mantis.controllers.bangbang import BangBang
from mantis.controllers.no_action import DoNothingController
from mantis.controllers.pid import PIDController

registry = {
    "pid": PIDController,
    "bangbang": BangBang,
    "do_nothing": DoNothingController
}