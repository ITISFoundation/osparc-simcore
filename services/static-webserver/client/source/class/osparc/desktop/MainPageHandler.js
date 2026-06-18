/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.MainPageHandler", {
  extend: qx.core.Object,
  type: "singleton",

  members: {
    __stack: null,
    __loadingPage: null,
    __dashboard: null,
    __studyEditor: null,

    setStack: function(stack) {
      this.__stack = stack;
    },

    addLoadingPage: function(loadingPage) {
      this.__loadingPage = loadingPage;
      this.__stack.add(loadingPage);
    },

    addDashboard: function(dashboard) {
      this.__dashboard = dashboard;
      this.__stack.add(dashboard);
    },

    addStudyEditor: function(studyEditor) {
      this.__studyEditor = studyEditor;
      this.__stack.add(studyEditor);
    },

    showLoadingPage: function() {
      this.__stack.setSelection([this.__loadingPage]);
    },

    showDashboard: function() {
      this.__stack.setSelection([this.__dashboard]);
    },

    showStudyEditor: function() {
      this.__stack.setSelection([this.__studyEditor]);
    },

    setLoadingPageHeader: function(msg) {
      this.__loadingPage.setHeader(msg);
    },

    startStudy: function(studyId) {
      const store = osparc.store.Store.getInstance();
      const dispatchStudyId = store.getCurrentDispatchStudyId();
      if (dispatchStudyId) {
        store.setCurrentStudyId(null);
        store.setCurrentDispatchStudyId(null);
        this.dispatchStudy(dispatchStudyId);
        return;
      }

      this.setLoadingPageHeader(qx.locale.Manager.tr("Loading ") + osparc.product.Utils.getStudyAlias());
      this.showLoadingPage();

      osparc.store.Study.getInstance().getOne(studyId)
        .then(studyData => {
          if (!studyData) {
            const msg = qx.locale.Manager.tr("Project not found");
            throw new Error(msg);
          }
          return this.loadStudy(studyData); // return so errors propagate
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          this.showDashboard();
          return;
        });
    },

    dispatchStudy: function(studyId) {
      this.setLoadingPageHeader(qx.locale.Manager.tr("Preparing ") + osparc.product.Utils.getStudyAlias());
      this.showLoadingPage();
      this.__loadingPage.setMessages([
        qx.locale.Manager.tr("Starting dispatch task...")
      ]);

      const params = {
        url: {
          studyId,
        }
      };
      const options = {
        pollTask: true,
      };

      const pollPromise = osparc.data.Resources.fetch("studies", "postDispatchStudy", params, options);
      const pollTasks = osparc.store.PollTasks.getInstance();
      const interval = 1000;
      pollTasks.createPollingTask(pollPromise, interval)
        .then(task => {
          task.addListener("updateReceived", e => {
            const updateData = e.getData();
            if ("task_progress" in updateData) {
              const taskProgress = updateData["task_progress"];
              const message = taskProgress["message"];
              if (message) {
                this.__loadingPage.setMessages([message]);
              }
            }
          }, this);

          task.addListener("resultReceived", e => {
            const resultData = e.getData();
            const projectId = resultData ? resultData["project_id"] : null;
            if (!projectId) {
              throw new Error(qx.locale.Manager.tr("Missing project id in dispatch result"));
            }
            osparc.store.Store.getInstance().setCurrentStudyId(projectId);
            this.__loadingPage.setMessages([]);
            this.startStudy(projectId);
          }, this);

          task.addListener("pollingError", e => {
            const err = e.getData();
            osparc.FlashMessenger.logError(err);
            this.showDashboard();
          }, this);
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          this.showDashboard();
        });
    },

    loadStudy: function(studyData) {
      const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      // check if it's locked
      let locked = false;
      let lockedBy = [];
      if ("state" in studyData) {
        const state = studyData["state"];
        locked = osparc.study.Utils.state.isProjectLocked(state);
        const currentUserGroupIds = osparc.study.Utils.state.getCurrentGroupIds(state);
        lockedBy = currentUserGroupIds.filter(gid => gid !== osparc.store.Groups.getInstance().getMyGroupId());
      }
      if (locked && lockedBy.length) {
        const msg = `${studyAlias} ${qx.locale.Manager.tr("is already open by another user.")}`;
        throw new Error(msg);
      }

      // check if there is any linked node missing
      if (osparc.study.Utils.isAnyLinkedNodeMissing(studyData)) {
        const msg = `${qx.locale.Manager.tr("We found an issue with some links.")}<br>${qx.locale.Manager.tr("They will be removed.")}`;
        throw new Error(msg);
      }

      this.setLoadingPageHeader(qx.locale.Manager.tr("Loading ") + studyData.name);
      this.showLoadingPage();

      return osparc.store.Services.getStudyServicesMetadata(studyData)
        .finally(() => {
          const inaccessibleServices = osparc.store.Services.getInaccessibleServices(studyData["workbench"]);
          if (inaccessibleServices.length) {
            const msg = osparc.store.Services.getInaccessibleServicesMsg(inaccessibleServices, studyData["workbench"]);
            osparc.FlashMessenger.logError(msg);
            this.showDashboard();
            return;
          }
          this.showStudyEditor();
          this.__studyEditor.setStudyData(studyData);
        });
    }
  }
});
