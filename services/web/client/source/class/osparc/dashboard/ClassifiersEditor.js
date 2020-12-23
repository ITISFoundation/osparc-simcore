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
    "updateResourceClassifiers": "qx.event.type.Data"
  },

  members: {
    __studyData: null,
    __classifiersTree: null,

    __buildLayout: function() {
      this.__addRRIDSection();
      this.__addClassifiersTree();
      this.__addButtons();
    },

    __addRRIDSection: function() {
      const rridLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const logo = new qx.ui.basic.Image("osparc/rrid-logo.png").set({
        height: 22,
        width: 20,
        scale: true
      });
      rridLayout.add(logo);

      const linkLabel = new osparc.ui.basic.LinkLabel(this.tr("RRID:"), "https://scicrunch.org/resources").set({
        alignY: "middle"
      });
      rridLayout.add(linkLabel);

      const textField = new qx.ui.form.TextField().set({
        placeholder: "SCR_018997"
      });
      rridLayout.add(textField, {
        flex: 1
      });

      const addRRIDClassfierBtn = new osparc.ui.form.FetchButton(this.tr("Add Classifier"));
      addRRIDClassfierBtn.addListener("execute", () => {
        this.__addRRIDClassfier(textField.getValue(), addRRIDClassfierBtn);
      }, this);
      rridLayout.add(addRRIDClassfierBtn);

      this._add(rridLayout);
    },

    __addClassifiersTree: function() {
      const studyData = this.__studyData;
      const classifiers = studyData.classifiers && studyData.classifiers ? studyData.classifiers : [];
      const classifiersTree = this.__classifiersTree = new osparc.component.filter.ClassifiersFilter("classifiersEditor", "sideSearchFilter", classifiers);
      osparc.store.Store.getInstance().addListener("changeClassifiers", e => {
        classifiersTree.recreateTree();
      }, this);
      this._add(classifiersTree, {
        flex: 1
      });
    },

    __addButtons: function() {
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

    __addRRIDClassfier: function(rrid, btn) {
      rrid = rrid.replace("RRID:", "");
      const params = {
        url: {
          "rrid": rrid
        }
      };
      btn.setFetching(true);
      osparc.data.Resources.fetch("classifiers", "postRRID", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("RRID classifier successfuly added"), "INFO");
          osparc.store.Store.getInstance().getAllClassifiers(true);
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err, "ERROR");
        })
        .finally(() => {
          btn.setFetching(false);
        });
    },

    __saveClassifiers: function(saveBtn) {
      saveBtn.setFetching(true);

      if ("uuid" in this.__studyData) {
        this.__studyData["classifiers"] = this.__classifiersTree.getCheckedClassifierIDs();
        const params = {
          url: {
            "projectId": this.__studyData["uuid"]
          },
          data: this.__studyData
        };
        osparc.data.Resources.fetch("studies", "put", params)
          .then(() => {
            this.fireDataEvent("updateResourceClassifiers", this.__studyData["uuid"]);
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Classifiers successfully edited"));
            saveBtn.setFetching(false);
          })
          .catch(err => {
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing Classifiers"), "ERROR");
            console.error(err);
          });
      } else {
        const params = {
          url: osparc.data.Resources.getServiceUrl(
            this.__studyData["key"],
            this.__studyData["version"]
          ),
          data: {
            "classifiers": this.__classifiersTree.getCheckedClassifierIDs()
          }
        };
        osparc.data.Resources.fetch("services", "patch", params)
          .then(() => {
            this.fireDataEvent("updateResourceClassifiers", this.__studyData["key"]);
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
