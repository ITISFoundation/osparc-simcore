/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @ignore(fetch)
 */

qx.Class.define("osparc.data.PollTask", {
  extend: qx.core.Object,

  construct: function(taskData, interval) {
    this.base(arguments);

    interval ? this.setPollInterval(interval) : this.initPollInterval();

    if (taskData && "task_id" in taskData) {
      this.set({
        taskId: taskData["task_id"],
        statusHref: taskData["status_href"],
        resultHref: taskData["result_href"]
      });

      if ("abort_href" in taskData) {
        this.set({
          abortHref: taskData["abort_href"]
        });
      }

      this.__pollTaskState();
    }
  },

  events: {
    "updateReceived": "qx.event.type.Data",
    "resultReceived": "qx.event.type.Data",
    "taskAborted": "qx.event.type.Event",
    "pollingError": "qx.event.type.Data"
  },

  properties: {
    pollInterval: {
      check: "Number",
      nullable: false,
      init: 1000
    },

    taskId: {
      check: "String",
      nullable: false
    },

    statusHref: {
      check: "String",
      nullable: false
    },

    resultHref: {
      check: "String",
      nullable: false
    },

    abortHref: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeAbortHref"
    },

    done: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeDone",
      apply: "__fetchResults"
    }
  },

  members: {
    __result: null,

    __pollTaskState: function() {
      fetch(this.getStatusHref())
        .then(resp => {
          if (resp.status === 200) {
            return resp.json();
          }
          const errMsg = this.tr("Failed polling status");
          this.fireDataEvent("pollingError", errMsg);
          throw new Error(errMsg);
        })
        .then(data => {
          const response = data["data"];
          const done = response["done"];
          this.setDone(done);
          if (done === false) {
            this.fireDataEvent("updateReceived", response);
            // keep polling
            setTimeout(() => this.__pollTaskState(), this.getPollInterval());
          }
        })
        .catch(err => {
          this.fireDataEvent("pollingError", err);
          throw err;
        });
    },

    __fetchResults: function() {
      if (this.isDone()) {
        fetch(this.getResultHref())
          .then(res => res.json())
          .then(result => {
            if ("error" in result && result["error"]) {
              throw new Error(result["error"]["message"]);
            }
            if ("data" in result && result["data"]) {
              const resultData = result["data"];
              this.fireDataEvent("resultReceived", resultData);
              return;
            }
            throw new Error("Missing result data");
          })
          .catch(err => {
            this.fireDataEvent("pollingError", err);
            throw err;
          });
      }
    },

    abortRequested: function() {
      fetch(this.getAbortHref(), {
        method: "DELETE"
      })
        .then(() => this.fireEvent("taskAborted"))
        .catch(err => {
          throw err;
        });
    }
  }
});
