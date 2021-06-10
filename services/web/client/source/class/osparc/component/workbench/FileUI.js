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

/**
 * File-like window that is used to represent a selected file in the WorkbenchUI.
 */

qx.Class.define("osparc.component.workbench.FileUI", {
  extend: osparc.component.workbench.NodeUI,

  /**
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(node) {
    this.base(arguments, node);

    this.set({
      width: this.self(arguments).FILEUI_WIDTH,
      maxWidth: this.self(arguments).FILEUI_WIDTH,
      minWidth: this.self(arguments).FILEUI_WIDTH
    });

    this.__creatFileLayout();
  },

  statics: {
    FILEUI_WIDTH: 100
  },

  members: {
    __creatFileLayout: function() {
      this.__createNodeLayout();

      const chipContainer = this.getChildControl("chips");
      chipContainer.exclude();

      if (this.__progressBar) {
        this.__progressBar.exclude();
      }
    },

    populateFileLayout: function() {
      // this.populateNodeLayout();
      const node = this.getNode();
      node.bind("label", this, "caption");

      const fileImage = new osparc.ui.basic.Thumbnail("@FontAwesome5Solid/file-alt/45").set({
        padding: 8
      });
      this.__inputOutputLayout.addAt(fileImage, 1, {
        flex: 1
      });

      const metaData = node.getMetaData();
      this.__createUIPorts(false, metaData && metaData.outputs);
    }
  }
});
