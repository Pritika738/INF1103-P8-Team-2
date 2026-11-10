"""
screens package

Re-exports every page function so the entry point can keep doing a
single `from screens import *`. Each screen lives in its own module
for readability; nothing here holds logic.
"""

from .auth_screens import *
from .dashboard import *
from .upload import *
from .history import *
from .trends import *
from .vitals import *
from .profile import *
from .settings import *
from .consultation import *