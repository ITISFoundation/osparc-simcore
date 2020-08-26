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

/**
 * Built-in service used for selecting MULTIPLE files from storage and make it available in the workflow
 *
 *   It consists of a widget containing a FilesTree, Add button and Select button:
 * - FilesTree will be populated with data provided by storage service (simcore.S3 and datcore)
 * - Add button will open a dialogue where the selected file will be upload to S3
 * - Select button puts the file in the output of the FilePicker node so that connected nodes can access it.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let filePicker = new osparc.file.FilePicker2(node);
 *   this.getRoot().add(filePicker);
 * </pre>
 */

qx.Class.define("osparc.file.FilePicker2", {
  extend: osparc.component.node.BaseNodeView,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    */
  construct: function(node) {
    this.base(arguments);

    this.set({
      node
    });
  },

  members: {
    __filePicker: null,

    __buildMyLayout: function() {
      const filePicker = this.__filePicker = new osparc.file.FilePicker(this.getNode());
      filePicker.buildLayout();
      filePicker.init();

      this._mainView.add(filePicker, {
        flex: 1
      });

      const filesTree = filePicker.getFilesTree();
      filesTree.set({
        selectionMode: "multi"
      });
    },

    // overridden
    isSettingsGroupShowable: function() {
      return false;
    },

    // overridden
    _addSettings: function() {
      return;
    },

    // overridden
    _addIFrame: function() {
      this.__buildMyLayout();
      this.__init();
    },

    // overridden
    _openEditAccessLevel: function() {
      return;
    },

    // overridden
    _applyNode: function(node) {
      return;
    }
  }
});
