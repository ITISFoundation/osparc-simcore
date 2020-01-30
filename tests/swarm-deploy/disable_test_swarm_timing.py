from docker_utils import assert_swarm_deployed
from tenacity import Retrying
from timeit import default_timer


async def test_up_times(osparc_deployer_maker):
    deployer = osparc_deployer_maker()

    times = {}
    def _msg(f, t):
        return f"Time elapsed from '{f}'->'{t}' [secs] : {times[t]-times[f]}"

    times['start'] = default_timer()
    try:
        stack_configs = next(deployer)

        times['after-make-up'] = default_timer()

        for attempt in Retrying():
            with attempt:
                assert_swarm_deployed()

        times['deployed'] = default_timer()

        print(_msg("start", "after-make-up"))
        print(_msg("after-make-up", "deployed"))
        # NOTE: prints like:
        #
        # Time elapsed from 'start'->'after-make-up' [secs] : 23.960341501049697
        # Time elapsed from 'after-make-up'->'deployed' [secs] : 59.16437579714693
        #

    finally:
        times['started-down'] = default_timer()
        try:
            next(deployer)
        except:
            pass
        finally:
            times['down'] = default_timer()
