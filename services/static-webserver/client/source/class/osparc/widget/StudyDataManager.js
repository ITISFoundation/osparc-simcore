/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that contains FilesTree showing:
 * - data generated by the node
 * and a FileLabelWithActions for letting the user download and/or remove files.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let dataManager = new osparc.widget.StudyDataManager(null, nodeId);
 *   this.getRoot().add(dataManager);
 * </pre>
 */

qx.Class.define("osparc.widget.StudyDataManager", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyId {String} StudyId
    * @param nodeId {String} NodeId
    */
  construct: function(studyId, nodeId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.setStudyId(studyId);

    if (nodeId) {
      this.setNodeId(nodeId);
    }

    this.__buildLayout();
    this.__reloadTree();
  },

  statics: {
    popUpInWindow: function(studyId, nodeId, title) {
      const studyDataManager = new osparc.widget.StudyDataManager(studyId, nodeId);
      if (!title) {
        title = osparc.product.Utils.getStudyAlias({firstUpperCase: true}) + qx.locale.Manager.tr(" Files");
      }
      return osparc.ui.window.Window.popUpInWindow(studyDataManager, title, osparc.dashboard.ResourceDetails.WIDTH, osparc.dashboard.ResourceDetails.HEIGHT);
    },
  },

  properties: {
    studyId: {
      check: "String",
      init: null,
      nullable: false
    },

    nodeId: {
      check: "String",
      init: null,
      nullable: false
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tree-folder-view":
          control = new osparc.file.TreeFolderView();
          this._add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const treeFolderView = this.getChildControl("tree-folder-view");
      treeFolderView.getChildControl("folder-tree").setBackgroundColor("window-popup-background");

      const selectedFileLayout = treeFolderView.getChildControl("folder-viewer").getChildControl("selected-file-layout");
      selectedFileLayout.addListener("pathsDeleted", e => treeFolderView.pathsDeleted(e.getData()), this);
    },

    __reloadTree: function() {
      const treeFolderView = this.getChildControl("tree-folder-view");

      const foldersTree = treeFolderView.getChildControl("folder-tree");
      foldersTree.resetCache();
      if (this.getNodeId()) {
        foldersTree.populateNodeTree(this.getStudyId(), this.getNodeId());
        treeFolderView.requestSize(this.getStudyId(), this.getNodeId());
      } else if (this.getStudyId()) {
        foldersTree.populateStudyTree(this.getStudyId());
        treeFolderView.requestSize(this.getStudyId());
      }

      const folderViewer = treeFolderView.getChildControl("folder-viewer");
      folderViewer.resetFolder();
    },
  }
});
