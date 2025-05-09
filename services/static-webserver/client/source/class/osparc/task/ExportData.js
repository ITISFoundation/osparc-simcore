/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.task.ExportData", {
  extend: osparc.task.TaskUI,

  construct: function() {
    this.base(arguments);

    this.setIcon(this.self().ICON+"/14");
    this.setTitle(this.tr("Downloading files:"));
  },

  statics: {
    ICON: "@FontAwesome5Solid/download",

    exportDataTaskReceived: function(task, popUpProgressWindow = true) {
      const exportDataTaskUI = new osparc.task.ExportData();
      exportDataTaskUI.setTask(task);
      osparc.task.TasksContainer.getInstance().addTaskUI(exportDataTaskUI);

      if (popUpProgressWindow) {
        const progressWindow = new osparc.ui.window.Progress(
          qx.locale.Manager.tr("Downloading files"),
          osparc.task.ExportData+"/14",
          qx.locale.Manager.tr("Compressing files..."),
        );

        if (task.getAbortHref()) {
          const cancelButton = progressWindow.addCancelButton();
          cancelButton.setLabel(qx.locale.Manager.tr("Ignore"));
          const abortButton = new qx.ui.form.Button().set({
            label: qx.locale.Manager.tr("Cancel"),
            center: true,
            minWidth: 100,
          });
          abortButton.addListener("execute", () => task.abortRequested());
          progressWindow.addButton(abortButton);
          abortButton.set({
            appearance: "danger-button",
          });
        }

        task.addListener("updateReceived", e => {
          const data = e.getData();
          if (data["task_progress"]) {
            if ("message" in data["task_progress"] && data["task_progress"]["message"]) {
              progressWindow.setMessage(data["task_progress"]["message"]);
            }
            progressWindow.setProgress(osparc.data.PollTask.extractProgress(data) * 100);
          }
        });

        task.addListener("resultReceived", () => progressWindow.close());
        task.addListener("taskAborted", () => progressWindow.close());
        task.addListener("pollingError", () => progressWindow.close());

        progressWindow.open();
      }

      task.addListener("resultReceived", e => {
        const taskData = e.getData();
        if (taskData["result"]) {
          const params = {
            url: {
              locationId: 0,
              fileUuid: encodeURIComponent(taskData["result"]),
            }
          };
          osparc.data.Resources.fetch("storageLink", "getOne", params)
            .then(data => {
              if (data && data.link) {
                const fileName = taskData["result"].split("/").pop();
                const progressCb = null;
                const loadedCb = () => {
                  const deleteParams = {
                    url: {
                      taskId: task.getTaskId(),
                    }
                  };
                  osparc.data.Resources.fetch("tasks", "delete", deleteParams);
                }
                osparc.utils.Utils.downloadLink(data.link, "GET", fileName, progressCb, loadedCb);
              }
            })
        }
      });
      task.addListener("taskAborted", () => {
        osparc.FlashMessenger.logAs(qx.locale.Manager.tr("Download cancelled"), "WARNING");
      });
      task.addListener("pollingError", e => {
        const err = e.getData();
        osparc.FlashMessenger.logError(err);
      });
    }
  },
});
