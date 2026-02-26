import asyncio
from viam.module.module import Module
from models.hackathon_greenhouse_demo import HackathonGreenhouseDemo

# TODO fix this import
from models.stevebriskin:scd4x:scd4x import Scd4x

if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())

    # call readings method from sensor module
