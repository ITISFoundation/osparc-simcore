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

  events: {
    "syncStudyEditor": "qx.event.type.Data"
  },

  members: {
    __stack: null,
    __dashboard: null,
    __loadingPage: null,
    __studyEditor: null,

    setStack: function(stack) {
      this.__stack = stack;
    },

    addDashboard: function(dashboard) {
      this.__dashboard = dashboard;
      this.__stack.add(dashboard);
    },

    addLoadingPage: function(loadingPage) {
      this.__loadingPage = loadingPage;
      this.__stack.add(loadingPage);
    },

    addStudyEditor: function(studyEditor) {
      this.__studyEditor = studyEditor;
      this.__stack.add(studyEditor);
    },

    showDashboard: function() {
      this.__stack.setSelection([this.__dashboard]);
    },

    showLoadingPage: function() {
      this.__stack.setSelection([this.__loadingPage]);
    },

    showStudyEditor: function() {
      this.__stack.setSelection([this.__studyEditor]);
    },

    replaceStudyEditor: function(studyEditor) {
      if (this.__studyEditor) {
        this.__stack.remove(this.__studyEditor);
      }
      this.addStudyEditor(studyEditor);
    },

    setLoadingPageHeader: function(msg) {
      this.__loadingPage.setHeader(msg);
    },

    startStudy: function(studyId) {
      this.setLoadingPageHeader(qx.locale.Manager.tr("Loading ") + osparc.product.Utils.getStudyAlias());
      this.showLoadingPage();

      const params = {
        url: {
          "studyId": studyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          if (!studyData) {
            const msg = qx.locale.Manager.tr("Study not found");
            throw new Error(msg);
          }
          const pageContext = osparc.data.model.Study.getUiMode(studyData) || "workbench";
          this.loadStudy(studyData, pageContext);
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          this.showDashboard();
          return;
        });
    },

    loadStudy: function(studyData, pageContext) {
      let locked = false;
      let lockedBy = false;
      if ("state" in studyData && "locked" in studyData["state"]) {
        locked = studyData["state"]["locked"]["value"];
        lockedBy = studyData["state"]["locked"]["owner"];
      }
      if (locked && lockedBy["user_id"] !== osparc.auth.Data.getInstance().getUserId()) {
        const msg = qx.locale.Manager.tr("Study is already open by ") + lockedBy["first_name"];
        throw new Error(msg);
      }
      const store = osparc.store.Store.getInstance();
      store.getInaccessibleServices(studyData)
        .then(inaccessibleServices => {
          if (inaccessibleServices.length) {
            const msg = osparc.utils.Study.getInaccessibleServicesMsg(inaccessibleServices);
            throw new Error(msg);
          }
          this.showStudyEditor();
          this.__studyEditor.setStudyData(studyData)
            .then(() => this.fireDataEvent("syncStudyEditor", pageContext));
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          this.showDashboard();
          return;
        });
    }
  }
});
