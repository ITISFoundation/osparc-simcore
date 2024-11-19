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
          this.loadStudy(studyData);
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          this.showDashboard();
          return;
        });
    },

    loadStudy: function(studyData) {
      const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      // check if it's locked
      let locked = false;
      let lockedBy = false;
      if ("state" in studyData && "locked" in studyData["state"]) {
        locked = studyData["state"]["locked"]["value"];
        lockedBy = studyData["state"]["locked"]["owner"];
      }
      if (locked && lockedBy["user_id"] !== osparc.auth.Data.getInstance().getUserId()) {
        const msg = `${studyAlias} ${qx.locale.Manager.tr("is already open by")} ${
          "first_name" in lockedBy && lockedBy["first_name"] != null ?
            lockedBy["first_name"] :
            qx.locale.Manager.tr("another user.")
        }`;
        throw new Error(msg);
      }

      // check if it's corrupt
      if (osparc.data.model.Study.isCorrupt(studyData)) {
        const msg = `${qx.locale.Manager.tr("We encountered an issue with the")} ${studyAlias} <br>${qx.locale.Manager.tr("Please contact support.")}`;
        throw new Error(msg);
      }

      this.setLoadingPageHeader(qx.locale.Manager.tr("Loading ") + studyData.name);
      this.showLoadingPage();
      const inaccessibleServices = osparc.study.Utils.getInaccessibleServices(studyData["workbench"])
      if (inaccessibleServices.length) {
        const msg = osparc.study.Utils.getInaccessibleServicesMsg(inaccessibleServices, studyData["workbench"]);
        osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        this.showDashboard();
        return;
      }
      this.showStudyEditor();
      this.__studyEditor.setStudyData(studyData);
    }
  }
});
