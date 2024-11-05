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

qx.Class.define("osparc.widget.StudyTitleOnlyTree", {
  extend: osparc.widget.NodesTree,

  construct: function() {
    this.base(arguments, null, "label", "children");

    this.set({
      hideRoot: false
    });
  },

  members: {
    // override
    populateTree: function() {
      const study = this.getStudy();
      const newModel = osparc.widget.NodesTree.createStudyModel(study);
      this.setModel(newModel);
      this.setDelegate({
        ...this._getDelegate(study),
        createItem: () => {
          const studyTreeItem = new osparc.widget.NodeTreeItem();
          studyTreeItem.addListener("renameNode", e => this._openItemRenamer(e.getData()));
          studyTreeItem.addListener("infoNode", () => this.__openStudyInfo());
          return studyTreeItem;
        }
      });
    },

    __openStudyInfo: function() {
      const studyDetails = new osparc.info.StudyLarge(this.getStudy());
      const title = this.tr("Study Information");
      const width = osparc.info.CardLarge.WIDTH;
      const height = osparc.info.CardLarge.HEIGHT;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height).set({
        maxHeight: height
      });
    },

    selectStudyItem: function() {
      this.setSelection(new qx.data.Array([this.getModel()]));
      this.fireDataEvent("changeSelectedNode", this.getModel().getId());
    }
  }
});
