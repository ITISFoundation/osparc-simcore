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

      this.__pollTaskState();
    }
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

    done: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeDone"
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
          return null;
        })
        .then(data => {
          const response = data["data"];
          if (response["done"] === true) {
            this.setDone(true);
          } else {
            setTimeout(() => this.__pollTaskState(), this.getPollInterval());
          }
        })
        .catch(err => console.error(err));
    },

    fetchResult: function() {
      return fetch(this.getResultHref())
        .then(res => res.json())
        .then(result => {
          if ("error" in result && result["error"]) {
            throw new Error(result["error"]);
          }
          if ("data" in result && result["data"]) {
            return result["data"];
          }
          throw new Error("Missing result data");
        })
        .catch(err => console.error(err));
    }
  }
});
