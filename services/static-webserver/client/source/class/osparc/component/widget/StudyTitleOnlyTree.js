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

qx.Class.define("osparc.component.widget.StudyTitleOnlyTree", {
  extend: osparc.component.widget.NodesTree,

  construct: function() {
    this.base(arguments, null, "label", "children");

    this.set({
      hideRoot: false
    });
  },

  members: {
    // override
    populateTree: function() {
      const data = this.__getStudyModelData();
      const newModel = qx.data.marshal.Json.createModel(data, true);
      this.setModel(newModel);
      const study = this.getStudy();
      this.setDelegate({
        ...this._getDelegate(study),
        createItem: () => {
          const studyTreeItem = new osparc.component.widget.NodeTreeItem();
          studyTreeItem.addListener("renameNode", e => this._openItemRenamer(e.getData()));
          studyTreeItem.addListener("infoNode", () => this.__openStudyInfo());
          return studyTreeItem;
        }
      });
    },

    __getStudyModelData: function() {
      const study = this.getStudy();
      const data = {
        label: study.getName(),
        children: [],
        sortingValue: 0,
        id: study.getUuid(),
        study
      };
      return data;
    },

    __openStudyInfo: function() {
      const studyDetails = new osparc.studycard.Large(this.getStudy());
      const title = this.tr("Study Information");
      const width = 500;
      const height = 500;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
    },

    selectStudyItem: function() {
      this.setSelection(new qx.data.Array([this.getModel()]));
      this.fireDataEvent("changeSelectedNode", this.getModel().getId());
    }
  }
});
