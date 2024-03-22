/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Andrei Neagu (gitHK)

************************************************************************ */

/**
  * @asset(schedulerWorker.js)
  */

/**
 * Singleton class to be used as a drop-in replacement for`setInterval` and `clearInterval`.
 * Depending on browser and OS, `setInterval` might not be called if the  window is
 * not visible on the screen.
 */


qx.Class.define("osparc.utils.WebWorkerScheduler", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.__registeredCallbacks = {};
    this.__schedulerWorker = new Worker("resource/osparc/schedulerWorker.js");
    this.__schedulerWorker.onmessage = event => {
      const { id, event: workerEvent } = event.data;

      if (workerEvent === "tick") {
        if (id in this.__registeredCallbacks) {
          const { callback } = this.__registeredCallbacks[id];
          callback();
        }
      } else {
        console.log("Received unsupported event from worker", workerEvent)
      }
    };
  },

  members: {
    __schedulerWorker: null,
    __registeredCallbacks: null,

    setInterval: function(callback, interval) {
      const id = osparc.utils.Utils.uuidV4();
      this.__registeredCallbacks[id] = {
        callback,
        interval,
      };
      this.__schedulerWorker.postMessage({
        command: "scheduleInterval",
        id: id,
        interval: interval
      });
      return id;
    },

    clearInterval: function(id) {
      if (id in this.__registeredCallbacks) {
        this.__schedulerWorker.postMessage({
          command: "clearInterval",
          id: id
        });
        delete this.__registeredCallbacks[id];
      }
    },
  }
});
