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

qx.Class.define("osparc.metadata.ClassifiersEditor", {
  extend: qx.ui.core.Widget,

  construct: function(studyData) {
    this.base(arguments);

    if (osparc.utils.Resources.isService(studyData)) {
      this.__studyData = osparc.utils.Utils.deepCloneObject(studyData);
    } else {
      this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);
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

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "rrid": {
          control = this.__createRRIDSection();
          break;
        }
        case "classifiers": {
          control = this.__createClassifiersTree();
          break;
        }
        case "buttons": {
          control = this.__createButtons();
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._add(this.getChildControl("rrid"));
      this._add(this.getChildControl("classifiers"), {
        flex: 1
      });
      this._add(this.getChildControl("buttons"));
    },

    __createRRIDSection: function() {
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

      return rridLayout;
    },

    __createClassifiersTree: function() {
      const studyData = this.__studyData;
      const classifiers = studyData.classifiers && studyData.classifiers ? studyData.classifiers : [];
      const classifiersTree = this.__classifiersTree = new osparc.filter.ClassifiersFilter("classifiersEditor", "searchBarFilter", classifiers);
      osparc.store.Store.getInstance().addListener("changeClassifiers", e => {
        classifiersTree.recreateTree();
      }, this);
      return classifiersTree;
    },

    __createButtons: function() {
      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignX: "right"
      }));
      const saveBtn = new osparc.ui.form.FetchButton(this.tr("Save"));
      saveBtn.addListener("execute", () => {
        this.__saveClassifiers(saveBtn);
      }, this);
      buttons.add(saveBtn);
      return buttons;
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
          osparc.FlashMessenger.getInstance().logAs(this.tr("RRID classifier successfully added"), "INFO");
          osparc.store.Store.getInstance().getAllClassifiers(true);
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(err, "ERROR");
        })
        .finally(() => {
          btn.setFetching(false);
        });
    },

    __saveClassifiers: function(saveBtn) {
      saveBtn.setFetching(true);

      if (osparc.utils.Resources.isStudy(this._serializedData) || osparc.utils.Resources.isTemplate(this._serializedData)) {
        this.__studyData["classifiers"] = this.__classifiersTree.getCheckedClassifierIDs();
        const params = {
          url: {
            "studyId": this.__studyData["uuid"]
          },
          data: this.__studyData
        };
        osparc.data.Resources.fetch("studies", "put", params)
          .then(updatedStudy => {
            osparc.FlashMessenger.getInstance().logAs(this.tr("Classifiers successfully edited"));
            saveBtn.setFetching(false);
            this.fireDataEvent("updateClassifiers", updatedStudy);
          })
          .catch(err => {
            osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing Classifiers"), "ERROR");
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
          .then(updatedService => {
            osparc.FlashMessenger.getInstance().logAs(this.tr("Classifiers successfully edited"));
            saveBtn.setFetching(false);
            this.fireDataEvent("updateClassifiers", updatedService);
          })
          .catch(err => {
            osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing Classifiers"), "ERROR");
            console.error(err);
          });
      }
    }
  }
});
