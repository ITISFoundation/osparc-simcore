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

  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    const classifiers = studyData.classifiers && studyData.classifiers.classifierIDs ? studyData.classifiers.classifierIDs : [];
    const classifiersTree = new osparc.component.filter.ClassifiersFilter("classifiersEditor", "exploreBrowser", classifiers);
    this._add(classifiersTree, {
      flex: 1
    });

    const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
      alignX: "right"
    }));
    const saveBtn = new osparc.ui.form.FetchButton(this.tr("Save"));
    saveBtn.addListener("execute", () => {
      this.__saveClassifiers(classifiersTree, saveBtn);
    }, this);
    buttons.add(saveBtn);
    this._add(buttons);
  },

  statics: {
    popUpInWindow: function(title, classifiersEditor, width = 400, height = 400) {
      const win = new osparc.ui.window.Window(title).set({
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 10,
        width,
        height,
        showMaximize: false,
        showMinimize: false,
        modal: true,
        clickAwayClose: true
      });
      win.add(classifiersEditor);
      win.center();
      win.open();
      return win;
    }
  },

  events: {
    "updateClassifiers": "qx.event.type.Event"
  },

  members: {
    __saveClassifiers: function(classifiersTree, saveBtn) {
      saveBtn.setFetching(true);
      console.log(classifiersTree.getChecked());
      saveBtn.setFetching(false);
    }
  }
});
