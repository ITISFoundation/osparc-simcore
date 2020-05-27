/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.export.Permissions", {
  extend: qx.ui.core.Widget,

  construct: function(studyId) {
    this.base(arguments);

    this.__studyId = studyId;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  statics: {
    createPermissionsWindow: function(winText, shareStudyWidget) {
      const window = new qx.ui.window.Window(winText).set({
        appearance: "service-window",
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 0,
        width: 400,
        height: 300,
        showMaximize: false,
        showMinimize: false,
        modal: true
      });
      window.add(shareStudyWidget);
      window.center();
      return window;
    }
  },

  events: {
    "finished": "qx.event.type.Data"
  },

  members: {
    __studyId: null,
    __shareWith: null,

    popUpWindow: function(winText) {
      const window = this.self().createPermissionsWindow(winText, this);
      this.addListener("finished", e => {
        const template = e.getData();
        if (template) {
          window.close();
        }
      }, this);
      window.open();
    },

    __buildLayout: function() {
      const shareWith = this.__shareWith = new osparc.component.export.ShareWith(this.tr("Share with"));
      this._add(shareWith, {
        flex: 1
      });

      const shareStudyBtn = new osparc.ui.form.FetchButton(this.tr("Share")).set({
        allowGrowX: false,
        alignX: "right"
      });
      shareStudyBtn.addListener("execute", () => {
        this.__shareStudy(shareStudyBtn);
      }, this);
      shareWith.bind("ready", shareStudyBtn, "enabled");
      this._add(shareStudyBtn);
    },

    __shareStudy: function(btn) {
      btn.setFetching(true);

      const selectedGroupIDs = this.__shareWith.getSelectedGroups();
      selectedGroupIDs.forEach(selectedGroupID => {
        this.__formData["accessRights"][selectedGroupID] = "rwx";
      });

      const params = {
        url: {
          "study_id": this.__studyId
        },
        data: this.__formData
      };
      osparc.data.Resources.fetch("templates", "postToTemplate", params)
        .then(template => {
          this.fireDataEvent("finished", template);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Study successfully shared."), "INFO");
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while sharing the study."), "ERROR");
        })
        .finally(() => {
          btn.setFetching(false);
        });
    }
  }
});
