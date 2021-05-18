import pytest
from simcore_service_director_v2.modules.scheduler import Scheduler

# 1. setup database
# 2. setup tables
# 3. init scheduler, it should be empty
# 4. create a project, set some pipeline, tasks
# 5. based on the task states, the scheduler should schedule,
# or stop, or mark as failed, aborted.


#####################333
# Rationale
#
# 1. each time the Play button is pressed, a new comp_run entry is inserted
# 2. ideally, on play a snapshot of the workbench should be created, such that the scheduler can schedule
# 3. each time a task is completed, it should return its results, retrieves them, and updates the databases instead of the sidecar
# 4. each time completes, the scheduler starts the next one or aborts it in case of failure or cancellation
#


def test_scheduler_initialize_with_correct_state():
    Scheduler()
