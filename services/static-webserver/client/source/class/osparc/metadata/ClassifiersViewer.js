/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.metadata.ClassifiersViewer", {
  extend: qx.ui.core.Widget,

  construct: function(studyData) {
    this.base(arguments);

    let studyDataCopy = null;
    if (osparc.utils.Resources.isService(studyData)) {
      studyDataCopy = osparc.utils.Utils.deepCloneObject(studyData);
    } else {
      studyDataCopy = osparc.data.model.Study.deepCloneStudyObject(studyData);
    }

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__createClassifiersTree(studyDataCopy);
  },

  members: {
    __createClassifiersTree: function(studyData) {
      const selectedClassifiers = studyData.classifiers && studyData.classifiers ? studyData.classifiers : [];
      osparc.utils.Classifiers.getClassifiersAsTree(false, selectedClassifiers)
        .then(classifiers => {
          this._removeAll();
          let control = null;
          if (classifiers && classifiers.children.length) {
            control = new osparc.ui.tree.ClassifiersTree(classifiers);
          } else {
            control = new qx.ui.basic.Label(this.tr("No Classifiers assigned"));
          }
          this._add(control, {
            flex: 1
          });
        });
    }
  }
});
