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
 * Widget for creating a template from a study
 * - Creates a copy of study data
 * - Using the ShareWith widget allows to publish the template
 */

qx.Class.define("osparc.component.export.SaveAsTemplate", {
  extend: qx.ui.core.Widget,

  /**
   * @param studyId {String} Study Id
   * @param studyData {Object} Object containing part or the entire serialized Study Data
   */
  construct: function(studyId, studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__studyId = studyId;
    this.__formData = osparc.utils.Utils.deepCloneObject(studyData);

    this.__buildLayout();

    this.setHeaderText(this.tr("Make Template accessible to"));
    this.setButtonText(this.tr("Publish"));
  },

  statics: {
    createWindow: function(winText, shareResourceWidget) {
      const window = new qx.ui.window.Window(winText).set({
        appearance: "service-window",
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 10,
        width: 400,
        height: 300,
        showMaximize: false,
        showMinimize: false,
        modal: true
      });
      window.add(shareResourceWidget);
      window.center();
      return window;
    }
  },

  properties: {
    headerText: {
      check: "String",
      init: "",
      event: "changeHeaderText"
    },

    buttonText: {
      check: "String",
      init: "",
      event: "changeButtonText"
    }
  },

  events: {
    "finished": "qx.event.type.Data"
  },

  members: {
    __studyId: null,
    __shareWith: null,
    __formData: null,

    createWindow: function() {
      return this.self().createWindow(this.tr("Save as Template"), this);
    },

    __buildLayout: function() {
      const shareWith = this.__shareWith = new osparc.component.export.ShareWith();
      this.bind("headerText", shareWith, "legend");
      this._add(shareWith, {
        flex: 1
      });

      const shareResourceBtn = new osparc.ui.form.FetchButton().set({
        allowGrowX: false,
        alignX: "right"
      });
      this.bind("buttonText", shareResourceBtn, "label");
      shareResourceBtn.addListener("execute", () => {
        this.__shareResource(shareResourceBtn);
      }, this);
      shareWith.bind("ready", shareResourceBtn, "enabled");
      this._add(shareResourceBtn);
    },

    __shareResource: function(btn) {
      btn.setFetching(true);

      const selectedGroupIDs = this.__shareWith.getSelectedGroups();
      selectedGroupIDs.forEach(gid => {
        this.__formData["accessRights"][gid] = {
          "read": true,
          "write": false,
          "delete": false
        };
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
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Study successfully saved as template."), "INFO");
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while saving as template."), "ERROR");
        })
        .finally(() => {
          btn.setFetching(false);
        });
    }
  }
});
