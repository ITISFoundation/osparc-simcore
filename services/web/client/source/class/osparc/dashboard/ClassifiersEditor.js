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

qx.Class.define("osparc.dashboard.ClassifiersEditor", {
  extend: qx.ui.core.Widget,

  construct: function(studyData, isStudy = true) {
    this.base(arguments);

    if (isStudy) {
      this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);
    } else {
      this.__studyData = osparc.utils.Utils.deepCloneObject(studyData);
    }

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
  },

  events: {
    "updateClassifiers": "qx.event.type.Data"
  },

  members: {
    __studyData: null,
    __classifiersTree: null,

    __buildLayout: function() {
      const studyData = this.__studyData;
      const classifiers = studyData.classifiers && studyData.classifiers ? studyData.classifiers : [];
      const classifiersTree = this.__classifiersTree = new osparc.component.filter.ClassifiersFilter("classifiersEditor", "sideSearchFilter", classifiers);
      this._add(classifiersTree, {
        flex: 1
      });

      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignX: "right"
      }));
      const saveBtn = new osparc.ui.form.FetchButton(this.tr("Save"));
      saveBtn.addListener("execute", () => {
        this.__saveClassifiers(saveBtn);
      }, this);
      buttons.add(saveBtn);
      this._add(buttons);
    },

    __saveClassifiers: function(saveBtn) {
      saveBtn.setFetching(true);

      this.__studyData["classifiers"] = this.__classifiersTree.getCheckedClassifierIDs();
      if ("uuid" in this.__studyData) {
        const params = {
          url: {
            "projectId": this.__studyData["uuid"]
          },
          data: this.__studyData
        };
        osparc.data.Resources.fetch("studies", "put", params)
          .then(() => {
            this.fireDataEvent("updateClassifiers", this.__studyData["uuid"]);
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Classifiers successfully edited"));
            saveBtn.setFetching(false);
          })
          .catch(err => {
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing Classifiers"), "ERROR");
            console.error(err);
          });
      } else {
        const params = {
          url: {
            "serviceKey": this.__studyData["key"],
            "serviceVersion": this.__studyData["version"]
          },
          data: this.__studyData
        };
        osparc.data.Resources.fetch("services", "put", params)
          .then(() => {
            this.fireDataEvent("updateClassifiers", this.__studyData["key"]);
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Classifiers successfully edited"));
            saveBtn.setFetching(false);
          })
          .catch(err => {
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing Classifiers"), "ERROR");
            console.error(err);
          });
      }
    }
  }
});
