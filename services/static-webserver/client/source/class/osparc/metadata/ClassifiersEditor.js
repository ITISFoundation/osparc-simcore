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

  construct: function(resourceData) {
    this.base(arguments);

    if (osparc.utils.Resources.isService(resourceData)) {
      this.__resourceData = osparc.utils.Utils.deepCloneObject(resourceData);
    } else {
      this.__resourceData = osparc.data.model.Study.deepCloneStudyObject(resourceData);
    }

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
  },

  events: {
    "updateClassifiers": "qx.event.type.Data"
  },

  members: {
    __resourceData: null,
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

      const addRRIDClassifierBtn = new osparc.ui.form.FetchButton(this.tr("Add Classifier"));
      addRRIDClassifierBtn.addListener("execute", () => {
        this.__addRRIDClassifier(textField.getValue(), addRRIDClassifierBtn);
      }, this);
      rridLayout.add(addRRIDClassifierBtn);

      return rridLayout;
    },

    __createClassifiersTree: function() {
      const resourceData = this.__resourceData;
      const classifiers = resourceData.classifiers && resourceData.classifiers ? resourceData.classifiers : [];
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

    __addRRIDClassifier: function(rrid, btn) {
      rrid = rrid.replace("RRID:", "");
      const params = {
        url: {
          "rrid": rrid
        }
      };
      btn.setFetching(true);
      osparc.data.Resources.fetch("classifiers", "postRRID", params)
        .then(() => {
          osparc.FlashMessenger.logAs(this.tr("RRID classifier successfully added"), "INFO");
          osparc.store.Store.getInstance().getAllClassifiers(true);
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
        })
        .finally(() => {
          btn.setFetching(false);
        });
    },

    __saveClassifiers: function(saveBtn) {
      saveBtn.setFetching(true);

      const newClassifiers = this.__classifiersTree.getCheckedClassifierIDs();
      if (osparc.utils.Resources.isStudy(this.__resourceData) || osparc.utils.Resources.isTemplate(this.__resourceData)) {
        osparc.store.Study.getInstance().patchStudyData(this.__resourceData, "classifiers", newClassifiers)
          .then(() => {
            osparc.FlashMessenger.logAs(this.tr("Classifiers successfully edited"));
            saveBtn.setFetching(false);
            this.fireDataEvent("updateClassifiers", this.__resourceData);
          })
          .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while editing classifiers")));
      } else {
        const serviceDataCopy = osparc.utils.Utils.deepCloneObject(this.__resourceData);
        osparc.store.Services.patchServiceData(serviceDataCopy, "classifiers", newClassifiers)
          .then(() => {
            osparc.FlashMessenger.logAs(this.tr("Classifiers successfully edited"));
            saveBtn.setFetching(false);
            this.fireDataEvent("updateClassifiers", serviceDataCopy);
          })
          .catch(err => osparc.FlashMessenger.logError(err, this.tr("Something went wrong while editing classifiers")));
      }
    }
  }
});
