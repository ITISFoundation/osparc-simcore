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

  construct: function(taskData, interval = 2000) {
    this.base(arguments);

    this.setPollInterval(interval);

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

      this.__retries = 3;
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
      init: 2000
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

  statics: {
    extractPathname: function(href) {
      try {
        // For the long running tasks, only the pathname is relevant to the frontend
        const url = new URL(href);
        return url.pathname;
      } catch (_) {
        return href;
      }
    },

    extractProgress: function(updateData) {
      if ("task_progress" in updateData) {
        const taskProgress = updateData["task_progress"];
        const percent = taskProgress["percent"] ? parseFloat(taskProgress["percent"].toFixed(3)) : taskProgress["percent"];
        return percent;
      }
      return 0;
    },
  },

  members: {
    __retries: null,
    __aborting: null,

    __pollTaskState: function() {
      const statusPath = this.self().extractPathname(this.getStatusHref());
      fetch(statusPath)
        .then(resp => {
          if (this.__aborting || this.getDone()) {
            return null;
          }
          if (resp.status === 200) {
            return resp.json();
          }
          const errMsg = qx.locale.Manager.tr("Unsuccessful polling status");
          const err = new Error(errMsg);
          this.fireDataEvent("pollingError", err);
          throw err;
        })
        .then(data => {
          if (data === null) {
            return;
          }
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
          if (this.__retries > 0) {
            this.__retries--;
            this.__pollTaskState();
            return;
          }
          this.fireDataEvent("pollingError", err);
          throw err;
        });
    },

    __fetchResults: function() {
      if (this.isDone()) {
        const resultPath = this.self().extractPathname(this.getResultHref());
        fetch(resultPath)
          .then(res => res.json())
          .then(result => {
            if ("error" in result && result["error"]) {
              throw new Error(result["error"]);
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
      const abortHref = this.getAbortHref();
      if (abortHref) {
        this.__aborting = true;
        const abortPath = this.self().extractPathname(abortHref);
        fetch(abortPath, {
          method: "DELETE"
        })
          .catch(err => osparc.FlashMessenger.logError(err))
          .finally(() => this.fireEvent("taskAborted"));
      }
    }
  }
});
