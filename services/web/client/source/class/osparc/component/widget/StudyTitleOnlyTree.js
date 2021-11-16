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

  members: {
    populateTree: function() {
      this.base(arguments);
      this.getModel().getChildren().removeAll();
      this.setDelegate({
        ...this.getDelegate(),
        createItem: () => {
          const studyTreeItem = new osparc.component.widget.NodeTreeItem();
          studyTreeItem.addListener("renameNode", e => this.__openItemRenamer(e.getData()));
          studyTreeItem.addListener("infoNode", e => this.__openStudyInfo());
          return studyTreeItem;
        }
      });
    },

    __openStudyInfo: function() {
      const studyDetails = new osparc.studycard.Large(this.getStudy());
      const title = this.tr("Study Details");
      const width = 500;
      const height = 500;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
    },

    selectStudyItem: function() {
      this.setSelection(new qx.data.Array([this.getModel()]));
      this.fireDataEvent("nodeSelected", this.getModel().getNodeId());
    }
  }
});
