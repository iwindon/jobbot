import json
import logging

import azure.functions as func

from jobbot import pipeline

app = func.FunctionApp()


@app.timer_trigger(schedule="0 0 12 * * *", arg_name="timer", run_on_startup=False)  # 12:00 UTC daily (8am ET)
def daily_search(timer: func.TimerRequest) -> None:
    logging.info("Job search result: %s", pipeline.run())


@app.route(route="run", auth_level=func.AuthLevel.FUNCTION)
def run_now(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(pipeline.run()), mimetype="application/json")
